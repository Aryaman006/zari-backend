"""Admin-specific routes: dashboard, customers, coupons, shipping, inventory."""
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Body, HTTPException, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.core.dependencies import DbSession, CurrentAdmin
from app.models.user import User
from app.models.order import Order
from app.models.coupon import Coupon
from app.models.product_variant import ProductVariant
from app.models.shipment import Shipment
from app.models.shipping_provider import ShippingProvider
from app.schemas.common import PaginatedResponse, MessageResponse
from app.shipping.factory import get_provider, list_available_providers

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@router.get("/dashboard/stats")
async def get_dashboard_stats(db: DbSession, _: CurrentAdmin, period_days: int = 30):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=period_days)
    prev_since = since - timedelta(days=period_days)

    # Revenue
    rev_result = await db.execute(select(func.sum(Order.total)).where(
        Order.payment_status == "paid", Order.created_at >= since))
    revenue = float(rev_result.scalar_one() or 0)

    prev_rev_result = await db.execute(select(func.sum(Order.total)).where(
        Order.payment_status == "paid", Order.created_at >= prev_since, Order.created_at < since))
    prev_revenue = float(prev_rev_result.scalar_one() or 0)

    # Orders
    orders_result = await db.execute(select(func.count()).select_from(Order).where(Order.created_at >= since))
    orders_count = orders_result.scalar_one()
    prev_orders = (await db.execute(select(func.count()).select_from(Order).where(
        Order.created_at >= prev_since, Order.created_at < since))).scalar_one()

    # Customers
    customers_result = await db.execute(select(func.count()).select_from(User).where(
        User.role == "customer", User.created_at >= since))
    customers_count = customers_result.scalar_one()
    prev_customers = (await db.execute(select(func.count()).select_from(User).where(
        User.role == "customer", User.created_at >= prev_since, User.created_at < since))).scalar_one()

    # Low stock
    low_stock = (await db.execute(select(func.count()).select_from(ProductVariant).where(
        ProductVariant.stock_qty <= 5, ProductVariant.is_active == True))).scalar_one()

    # Active products count
    from app.models.product import Product
    products_count = (await db.execute(select(func.count()).select_from(Product).where(
        Product.is_active == True))).scalar_one()

    def growth(current, prev):
        if prev == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - prev) / prev) * 100, 1)

    return {
        "total_revenue": revenue, "revenue_growth": growth(revenue, prev_revenue),
        "total_orders": orders_count, "orders_growth": growth(orders_count, prev_orders),
        "total_customers": customers_count, "customers_growth": growth(customers_count, prev_customers),
        "low_stock_count": low_stock,
        "total_products": products_count,
    }


@router.get("/dashboard/revenue-chart")
async def get_revenue_chart(db: DbSession, _: CurrentAdmin, days: int = 30):
    """Daily revenue for the last N days."""
    from sqlalchemy import cast, Date, text
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date_trunc("day", Order.created_at).label("date"),
            func.sum(Order.total).label("revenue"),
            func.count(Order.id).label("orders"),
        )
        .where(Order.payment_status == "paid", Order.created_at >= since)
        .group_by("date").order_by("date")
    )
    return [{"date": str(row.date.date()), "revenue": float(row.revenue), "orders": row.orders}
            for row in result.all()]


@router.get("/dashboard/top-products")
async def get_top_products(db: DbSession, _: CurrentAdmin, limit: int = 5):
    from app.models.order_item import OrderItem
    from app.models.product_variant import ProductVariant
    from app.models.product import Product
    result = await db.execute(
        select(
            OrderItem.variant_id,
            Product.name.label("product_name"),
            ProductVariant.size,
            ProductVariant.color,
            ProductVariant.sku,
            func.sum(OrderItem.quantity).label("total_sold"),
            func.sum(OrderItem.total_price).label("total_revenue"),
        )
        .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(OrderItem.order_id.in_(
            select(Order.id).where(Order.payment_status == "paid")
        ))
        .group_by(OrderItem.variant_id, Product.name, ProductVariant.size, ProductVariant.color, ProductVariant.sku)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(limit)
    )
    return [
        {
            "variant_id": row.variant_id,
            "product_name": row.product_name,
            "size": row.size,
            "color": row.color,
            "sku": row.sku,
            "total_sold": int(row.total_sold),
            "total_revenue": float(row.total_revenue),
        }
        for row in result.all()
    ]



# ── CUSTOMERS ─────────────────────────────────────────────────────────────────

@router.get("/customers")
async def list_customers(
    db: DbSession, _: CurrentAdmin,
    page: int = 1, page_size: int = 20,
    search: Optional[str] = None,
):
    from app.repositories.user_repository import UserRepository
    repo = UserRepository(db)
    offset = (page - 1) * page_size
    users, total = await repo.get_customers(search=search, limit=page_size, offset=offset)
    return {
        "data": [{"id": u.id, "email": u.email, "first_name": u.first_name,
                  "last_name": u.last_name, "phone": u.phone, "is_verified": u.is_verified,
                  "is_active": u.is_active, "created_at": u.created_at.isoformat()} for u in users],
        "total": total, "page": page, "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/customers/{user_id}")
async def get_customer(user_id: str, db: DbSession, _: CurrentAdmin):
    user = await db.get(User, user_id)
    if not user or user.role != "customer":
        raise HTTPException(status_code=404, detail="Customer not found.")
    order_count = (await db.execute(select(func.count()).select_from(Order).where(Order.user_id == user_id))).scalar_one()
    total_spent = (await db.execute(select(func.sum(Order.total)).where(
        Order.user_id == user_id, Order.payment_status == "paid"))).scalar_one() or 0
    return {
        "id": user.id, "email": user.email, "first_name": user.first_name,
        "last_name": user.last_name, "phone": user.phone,
        "is_verified": user.is_verified, "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "order_count": order_count, "total_spent": float(total_spent),
    }


# ── COUPONS ───────────────────────────────────────────────────────────────────

@router.get("/coupons")
async def list_coupons(db: DbSession, _: CurrentAdmin):
    result = await db.execute(select(Coupon).order_by(Coupon.created_at.desc()))
    coupons = result.scalars().all()
    return [{"id": c.id, "code": c.code, "type": c.type, "value": float(c.value),
             "min_order_amount": float(c.min_order_amount) if c.min_order_amount else None,
             "max_discount": float(c.max_discount) if c.max_discount else None,
             "usage_limit": c.usage_limit, "used_count": c.used_count,
             "expires_at": c.expires_at.isoformat() if c.expires_at else None,
             "is_active": c.is_active, "created_at": c.created_at.isoformat()} for c in coupons]


@router.post("/coupons", status_code=201)
async def create_coupon(
    code: str, type: str, value: float, db: DbSession, _: CurrentAdmin,
    min_order_amount: Optional[float] = None, max_discount: Optional[float] = None,
    usage_limit: Optional[int] = None, expires_at: Optional[str] = None,
):
    existing = (await db.execute(select(Coupon).where(Coupon.code == code.upper()))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Coupon code already exists.")
    exp_dt = datetime.fromisoformat(expires_at) if expires_at else None
    coupon = Coupon(code=code.upper(), type=type, value=value, min_order_amount=min_order_amount,
                    max_discount=max_discount, usage_limit=usage_limit, expires_at=exp_dt)
    db.add(coupon)
    await db.flush()
    await db.refresh(coupon)
    return {"id": coupon.id, "code": coupon.code, "message": "Coupon created."}


@router.put("/coupons/{coupon_id}/toggle", response_model=MessageResponse)
async def toggle_coupon(coupon_id: str, db: DbSession, _: CurrentAdmin):
    coupon = await db.get(Coupon, coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found.")
    coupon.is_active = not coupon.is_active
    await db.flush()
    return {"message": f"Coupon {'activated' if coupon.is_active else 'deactivated'}."}


@router.delete("/coupons/{coupon_id}", response_model=MessageResponse)
async def delete_coupon(coupon_id: str, db: DbSession, _: CurrentAdmin):
    coupon = await db.get(Coupon, coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found.")
    await db.delete(coupon)
    return {"message": "Coupon deleted."}


# ── SHIPPING MANAGEMENT ───────────────────────────────────────────────────────

@router.get("/shipping/providers")
async def list_shipping_providers(db: DbSession, _: CurrentAdmin):
    result = await db.execute(select(ShippingProvider).order_by(ShippingProvider.name))
    providers = result.scalars().all()
    return [{"id": p.id, "name": p.name, "slug": p.slug, "is_active": p.is_active,
             "is_configured": p.is_configured, "description": p.description} for p in providers]


@router.post("/shipping/providers/{provider_id}/activate", response_model=MessageResponse)
async def activate_shipping_provider(provider_id: str, db: DbSession, _: CurrentAdmin):
    """Set a provider as the active one (deactivates all others)."""
    from sqlalchemy import update
    await db.execute(update(ShippingProvider).values(is_active=False))
    provider = await db.get(ShippingProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found.")
    provider.is_active = True
    await db.flush()
    return {"message": f"'{provider.name}' is now the active shipping provider."}


@router.post("/shipping/providers/{provider_id}/configure", response_model=MessageResponse)
async def configure_shipping_provider(
    provider_id: str, config: dict = Body(...), db: DbSession = None, _: CurrentAdmin = None
):
    provider = await db.get(ShippingProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found.")
    provider.config = config
    provider.is_configured = True
    await db.flush()
    return {"message": f"Provider '{provider.name}' configured successfully."}


@router.post("/shipping/shipments/{order_id}", response_model=dict)
async def create_shipment(order_id: str, db: DbSession, _: CurrentAdmin,
                          tracking_number: Optional[str] = None, tracking_url: Optional[str] = None, notes: Optional[str] = None):
    """Create shipment for an order using the active shipping provider."""
    from sqlalchemy.orm import selectinload
    from app.repositories.order_repository import OrderRepository
    order = await OrderRepository(db).get_by_id_with_relations(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    # Get active provider
    active_provider = (await db.execute(
        select(ShippingProvider).where(ShippingProvider.is_active == True)
    )).scalar_one_or_none()
    if not active_provider:
        raise HTTPException(status_code=400, detail="No active shipping provider configured.")

    provider_impl = get_provider(active_provider.slug)
    if not provider_impl:
        raise HTTPException(status_code=500, detail=f"Provider '{active_provider.slug}' is not implemented.")

    config = active_provider.config or {}
    if tracking_number:
        config["tracking_number"] = tracking_number
    if tracking_url:
        config["tracking_url"] = tracking_url

    result = await provider_impl.create_shipment(order, config)
    if not result.success:
        raise HTTPException(status_code=500, detail=f"Shipment creation failed: {result.error_message}")

    shipment = Shipment(
        order_id=order_id, provider_id=active_provider.id,
        tracking_number=result.tracking_number or tracking_number,
        tracking_url=result.tracking_url or tracking_url,
        status="created", notes=notes,
        provider_response=result.provider_response,
    )
    db.add(shipment)
    from sqlalchemy import update
    await db.execute(update(Order).where(Order.id == order_id).values(status="processing"))
    await db.flush()
    await db.refresh(shipment)
    return {"id": shipment.id, "tracking_number": shipment.tracking_number, "status": shipment.status}


@router.put("/shipping/shipments/{shipment_id}", response_model=dict)
async def update_shipment(
    shipment_id: str, db: DbSession, _: CurrentAdmin,
    tracking_number: Optional[str] = None, tracking_url: Optional[str] = None,
    status: Optional[str] = None, notes: Optional[str] = None,
):
    shipment = await db.get(Shipment, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    if tracking_number:
        shipment.tracking_number = tracking_number
    if tracking_url:
        shipment.tracking_url = tracking_url
    if status:
        shipment.status = status
        if status == "shipped":
            shipment.shipped_at = datetime.now(timezone.utc)
            from sqlalchemy import update
            await db.execute(update(Order).where(Order.id == shipment.order_id).values(status="shipped"))
        elif status == "delivered":
            shipment.delivered_at = datetime.now(timezone.utc)
            from sqlalchemy import update
            await db.execute(update(Order).where(Order.id == shipment.order_id).values(status="delivered"))
    if notes:
        shipment.notes = notes
    await db.flush()
    return {"id": shipment.id, "tracking_number": shipment.tracking_number, "status": shipment.status}


# ── INVENTORY ─────────────────────────────────────────────────────────────────

@router.get("/inventory")
async def get_inventory(
    db: DbSession,
    _: CurrentAdmin,
    low_stock: bool = False,
    out_of_stock: bool = False,
    low_stock_only: bool = False,  # backwards-compatible alias
    search: Optional[str] = None,
    limit: int = 100,
):
    """Get inventory with stats header. Supports low_stock, out_of_stock, and search filters."""
    from app.models.product import Product

    base_q = (
        select(ProductVariant, Product.name.label("product_name"), Product.slug)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(ProductVariant.is_active == True, Product.is_active == True)
    )

    if search:
        base_q = base_q.where(or_(Product.name.ilike(f"%{search}%"), ProductVariant.sku.ilike(f"%{search}%")))

    # Count stats before applying stock filter
    all_result = await db.execute(base_q)
    all_rows = all_result.all()
    low_count = sum(1 for r in all_rows if 0 < r.ProductVariant.stock_qty <= 10)
    out_count = sum(1 for r in all_rows if r.ProductVariant.stock_qty == 0)

    # Apply stock filter
    filtered_q = base_q
    if low_stock or low_stock_only:
        filtered_q = filtered_q.where(ProductVariant.stock_qty > 0, ProductVariant.stock_qty <= 10)
    elif out_of_stock:
        filtered_q = filtered_q.where(ProductVariant.stock_qty == 0)

    result = await db.execute(filtered_q.order_by(ProductVariant.stock_qty.asc()).limit(limit))
    rows = result.all()

    items = [
        {
            "variant_id": r.ProductVariant.id,
            "sku": r.ProductVariant.sku,
            "product_name": r.product_name,
            "product_slug": r.slug,
            "size": r.ProductVariant.size,
            "color": r.ProductVariant.color,
            "stock_qty": r.ProductVariant.stock_qty,
            "price_override": float(r.ProductVariant.price_override) if r.ProductVariant.price_override else None,
        }
        for r in rows
    ]

    return {
        "data": items,
        "stats": {
            "total": len(all_rows),
            "low_stock": low_count,
            "out_of_stock": out_count,
        },
    }


@router.put("/inventory/{variant_id}", response_model=MessageResponse)
async def update_stock(variant_id: str, stock_qty: int, db: DbSession, _: CurrentAdmin):
    variant = await db.get(ProductVariant, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found.")
    variant.stock_qty = stock_qty
    await db.flush()
    return {"message": f"Stock updated to {stock_qty}."}


# ── COUPON UPDATE ─────────────────────────────────────────────────────────────

@router.put("/coupons/{coupon_id}", response_model=MessageResponse)
async def update_coupon(
    coupon_id: str,
    db: DbSession,
    _: CurrentAdmin,
    code: str = Body(...),
    type: str = Body(...),
    value: float = Body(...),
    min_order_amount: Optional[float] = Body(None),
    max_discount: Optional[float] = Body(None),
    usage_limit: Optional[int] = Body(None),
    expires_at: Optional[str] = Body(None),
):
    coupon = await db.get(Coupon, coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found.")
    
    # Check duplicate code if code changed
    if code.upper() != coupon.code:
        existing = (await db.execute(select(Coupon).where(Coupon.code == code.upper()))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Coupon code already exists.")
            
    coupon.code = code.upper()
    coupon.type = type
    coupon.value = value
    coupon.min_order_amount = min_order_amount
    coupon.max_discount = max_discount
    coupon.usage_limit = usage_limit
    coupon.expires_at = datetime.fromisoformat(expires_at) if expires_at else None
    await db.flush()
    return {"message": "Coupon updated."}


# ── SETTINGS ──────────────────────────────────────────────────────────────────

async def _load_setting(db, key: str, default):
    """Load a single setting from DB, falling back to default."""
    from app.models.store_settings import StoreSetting
    import json
    row = await db.get(StoreSetting, key)
    if row is None:
        return default
    try:
        return json.loads(row.value)
    except (ValueError, TypeError):
        return row.value


async def _save_setting(db, key: str, value) -> None:
    """Upsert a single setting to DB."""
    from app.models.store_settings import StoreSetting
    import json
    serialized = json.dumps(value)
    existing = await db.get(StoreSetting, key)
    if existing:
        existing.value = serialized
    else:
        db.add(StoreSetting(key=key, value=serialized))


@router.get("/settings")
async def get_settings(db: DbSession, _: CurrentAdmin):
    """
    Return current store settings. Values are loaded from the DB first,
    falling back to the environment/.env defaults.
    """
    from app.core.config import settings
    return {
        "store_name":               await _load_setting(db, "BUSINESS_NAME",          settings.BUSINESS_NAME),
        "store_email":              await _load_setting(db, "EMAIL_FROM",              settings.EMAIL_FROM),
        "store_phone":              await _load_setting(db, "STORE_PHONE",             settings.STORE_PHONE),
        "store_address":            await _load_setting(db, "BUSINESS_ADDRESS",        settings.BUSINESS_ADDRESS),
        "razorpay_key_id":          await _load_setting(db, "RAZORPAY_KEY_ID",         settings.RAZORPAY_KEY_ID or ""),
        "razorpay_key_secret":      await _load_setting(db, "RAZORPAY_KEY_SECRET",     settings.RAZORPAY_KEY_SECRET or ""),
        "razorpay_webhook_secret":  await _load_setting(db, "RAZORPAY_WEBHOOK_SECRET", settings.RAZORPAY_WEBHOOK_SECRET or ""),
        "resend_api_key":           await _load_setting(db, "RESEND_API_KEY",          settings.RESEND_API_KEY or ""),
        "resend_from_email":        await _load_setting(db, "RESEND_FROM_EMAIL",       settings.RESEND_FROM_EMAIL or ""),
        "currency":                 await _load_setting(db, "RAZORPAY_CURRENCY",       settings.RAZORPAY_CURRENCY),
        "cgst_rate":                await _load_setting(db, "CGST_RATE",               settings.CGST_RATE),
        "sgst_rate":                await _load_setting(db, "SGST_RATE",               settings.SGST_RATE),
    }


@router.put("/settings", response_model=MessageResponse)
async def update_settings(
    db: DbSession,
    _: CurrentAdmin,
    store_name: str = Body(...),
    store_email: str = Body(...),
    store_phone: str = Body(...),
    store_address: str = Body(...),
    razorpay_key_id: Optional[str] = Body(None),
    razorpay_key_secret: Optional[str] = Body(None),
    razorpay_webhook_secret: Optional[str] = Body(None),
    resend_api_key: Optional[str] = Body(None),
    resend_from_email: Optional[str] = Body(None),
    currency: str = Body("INR"),
    cgst_rate: float = Body(0.09),
    sgst_rate: float = Body(0.09),
):
    """
    Persist store settings to the database and update the in-memory
    settings singleton for the current process.
    """
    from app.core.config import settings

    # Map of DB key → value to persist
    updates = {
        "BUSINESS_NAME":          store_name,
        "EMAIL_FROM":             store_email,
        "STORE_PHONE":            store_phone,
        "BUSINESS_ADDRESS":       store_address,
        "RAZORPAY_KEY_ID":        razorpay_key_id,
        "RAZORPAY_KEY_SECRET":    razorpay_key_secret,
        "RAZORPAY_WEBHOOK_SECRET": razorpay_webhook_secret,
        "RESEND_API_KEY":         resend_api_key,
        "RESEND_FROM_EMAIL":      resend_from_email,
        "RAZORPAY_CURRENCY":      currency,
        "CGST_RATE":              cgst_rate,
        "SGST_RATE":              sgst_rate,
    }

    # Persist each setting to the DB
    for key, value in updates.items():
        await _save_setting(db, key, value)

    # Also apply to in-memory settings so the running process uses new values
    settings.BUSINESS_NAME = store_name
    settings.EMAIL_FROM = store_email
    settings.STORE_PHONE = store_phone
    settings.BUSINESS_ADDRESS = store_address
    if razorpay_key_id is not None:
        settings.RAZORPAY_KEY_ID = razorpay_key_id
    if razorpay_key_secret is not None:
        settings.RAZORPAY_KEY_SECRET = razorpay_key_secret
    if razorpay_webhook_secret is not None:
        settings.RAZORPAY_WEBHOOK_SECRET = razorpay_webhook_secret
    if resend_api_key is not None:
        settings.RESEND_API_KEY = resend_api_key
    if resend_from_email is not None:
        settings.RESEND_FROM_EMAIL = resend_from_email
    settings.RAZORPAY_CURRENCY = currency
    settings.CGST_RATE = cgst_rate
    settings.SGST_RATE = sgst_rate

    return {"message": "Settings updated successfully."}

