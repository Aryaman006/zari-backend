"""Cart, Wishlist, Profile, and Address routes for authenticated customers."""
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from app.core.dependencies import DbSession, CurrentUser
from app.models.cart import CartItem
from app.models.wishlist import WishlistItem
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.address import Address
from app.models.user import User
from app.schemas.cart import (
    CartResponse, CartItemResponse, AddToCartRequest,
    UpdateCartItemRequest, WishlistItemResponse, CouponApplyRequest, CouponApplyResponse,
)
from app.schemas.order import AddressResponse, AddressRequest
from app.schemas.auth import UserResponse
from app.schemas.common import MessageResponse
from app.services.order_service import OrderService

router = APIRouter(prefix="/customer", tags=["Customer"])


class UpdateProfileRequest(BaseModel):
    first_name: str
    last_name: str
    phone: Optional[str] = None


# ── CART ──────────────────────────────────────────────────────────────────────

@router.get("/cart", response_model=CartResponse)
async def get_cart(db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(CartItem)
        .where(CartItem.user_id == current_user.id)
        .options(
            selectinload(CartItem.variant).selectinload(ProductVariant.product).selectinload(Product.images)
        )
    )
    items = result.scalars().all()
    cart_items = [_serialize_cart_item(item) for item in items]
    subtotal = sum(item["total_price"] for item in cart_items)
    return {"items": cart_items, "subtotal": subtotal, "item_count": len(items)}


@router.post("/cart", response_model=CartItemResponse, status_code=201)
async def add_to_cart(data: AddToCartRequest, db: DbSession, current_user: CurrentUser):
    # Check variant exists and has stock
    variant = await db.get(ProductVariant, data.variant_id)
    if not variant or not variant.is_active:
        raise HTTPException(status_code=404, detail="Product variant not found.")
    if variant.stock_qty < data.quantity:
        raise HTTPException(status_code=409, detail=f"Only {variant.stock_qty} items left in stock.")

    # Check if already in cart
    existing_result = await db.execute(
        select(CartItem).where(CartItem.user_id == current_user.id, CartItem.variant_id == data.variant_id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        new_qty = existing.quantity + data.quantity
        if variant.stock_qty < new_qty:
            raise HTTPException(status_code=409, detail=f"Only {variant.stock_qty} items available.")
        existing.quantity = new_qty
        await db.flush()
        cart_item = existing
    else:
        cart_item = CartItem(user_id=current_user.id, variant_id=data.variant_id, quantity=data.quantity)
        db.add(cart_item)
        await db.flush()

    # Reload with relations
    result = await db.execute(
        select(CartItem).where(CartItem.id == cart_item.id)
        .options(selectinload(CartItem.variant).selectinload(ProductVariant.product).selectinload(Product.images))
    )
    return _serialize_cart_item(result.scalar_one())


@router.put("/cart/{item_id}", response_model=CartItemResponse)
async def update_cart_item(item_id: str, data: UpdateCartItemRequest, db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == current_user.id)
        .options(selectinload(CartItem.variant).selectinload(ProductVariant.product).selectinload(Product.images))
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found.")
    if data.quantity <= 0:
        await db.delete(item)
        return {"message": "Item removed"}
    if item.variant.stock_qty < data.quantity:
        raise HTTPException(status_code=409, detail=f"Only {item.variant.stock_qty} items available.")
    item.quantity = data.quantity
    await db.flush()
    return _serialize_cart_item(item)


@router.delete("/cart/{item_id}", response_model=MessageResponse)
async def remove_from_cart(item_id: str, db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found.")
    await db.delete(item)
    return {"message": "Item removed from cart."}


@router.delete("/cart", response_model=MessageResponse)
async def clear_cart(db: DbSession, current_user: CurrentUser):
    await db.execute(delete(CartItem).where(CartItem.user_id == current_user.id))
    return {"message": "Cart cleared."}


@router.post("/cart/apply-coupon", response_model=CouponApplyResponse)
async def apply_coupon(data: CouponApplyRequest, db: DbSession, current_user: CurrentUser):
    """Validate a coupon code and return the discount amount."""
    from sqlalchemy import select
    from app.models.coupon import Coupon
    result = await db.execute(
        select(CartItem).where(CartItem.user_id == current_user.id)
        .options(selectinload(CartItem.variant).selectinload(ProductVariant.product))
    )
    items = result.scalars().all()
    subtotal = sum(
        float(i.variant.price_override or i.variant.product.sale_price or i.variant.product.base_price) * i.quantity
        for i in items
    )
    try:
        service = OrderService(db)
        coupon = await service._validate_coupon(data.code, subtotal)
        discount = service._calculate_discount(coupon, subtotal)
        return {"valid": True, "code": coupon.code, "discount_amount": discount}
    except HTTPException as e:
        return {"valid": False, "code": data.code, "discount_amount": 0, "message": e.detail}


# ── WISHLIST ──────────────────────────────────────────────────────────────────

@router.get("/wishlist", response_model=list[WishlistItemResponse])
async def get_wishlist(db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(WishlistItem)
        .where(WishlistItem.user_id == current_user.id)
        .options(
            selectinload(WishlistItem.product).selectinload(Product.images),
            selectinload(WishlistItem.product).selectinload(Product.variants),
        )
    )
    return [_serialize_wishlist_item(item) for item in result.scalars().all()]


@router.post("/wishlist/{product_id}", response_model=WishlistItemResponse, status_code=201)
async def add_to_wishlist(product_id: str, db: DbSession, current_user: CurrentUser):
    product = await db.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found.")
    existing = (await db.execute(
        select(WishlistItem).where(WishlistItem.user_id == current_user.id, WishlistItem.product_id == product_id)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Product already in wishlist.")
    item = WishlistItem(user_id=current_user.id, product_id=product_id)
    db.add(item)
    await db.flush()
    result = await db.execute(
        select(WishlistItem).where(WishlistItem.id == item.id)
        .options(
            selectinload(WishlistItem.product).selectinload(Product.images),
            selectinload(WishlistItem.product).selectinload(Product.variants),
        )
    )
    return _serialize_wishlist_item(result.scalar_one())


@router.delete("/wishlist/{product_id}", response_model=MessageResponse)
async def remove_from_wishlist(product_id: str, db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(WishlistItem).where(WishlistItem.user_id == current_user.id, WishlistItem.product_id == product_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not in wishlist.")
    await db.delete(item)
    return {"message": "Removed from wishlist."}


# ── PROFILE ───────────────────────────────────────────────────────────────────

@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: CurrentUser):
    return current_user


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    data: UpdateProfileRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    user = await db.get(User, current_user.id)
    user.first_name = data.first_name
    user.last_name = data.last_name
    user.phone = data.phone
    await db.flush()
    return user


# ── ADDRESSES ─────────────────────────────────────────────────────────────────

@router.get("/addresses", response_model=list[AddressResponse])
async def list_addresses(db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(Address).where(Address.user_id == current_user.id).order_by(Address.is_default.desc())
    )
    return result.scalars().all()


@router.post("/addresses", response_model=AddressResponse, status_code=201)
async def create_address(data: AddressRequest, db: DbSession, current_user: CurrentUser):
    if data.is_default:
        await db.execute(update(Address).where(Address.user_id == current_user.id).values(is_default=False))
    address = Address(user_id=current_user.id, **data.model_dump())
    db.add(address)
    await db.flush()
    await db.refresh(address)
    return address


@router.put("/addresses/{address_id}", response_model=AddressResponse)
async def update_address(address_id: str, data: AddressRequest, db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == current_user.id)
    )
    address = result.scalar_one_or_none()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found.")
    if data.is_default:
        await db.execute(update(Address).where(Address.user_id == current_user.id).values(is_default=False))
    for k, v in data.model_dump().items():
        setattr(address, k, v)
    await db.flush()
    return address


@router.delete("/addresses/{address_id}", response_model=MessageResponse)
async def delete_address(address_id: str, db: DbSession, current_user: CurrentUser):
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == current_user.id)
    )
    address = result.scalar_one_or_none()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found.")
    await db.delete(address)
    return {"message": "Address deleted."}


# ── SERIALIZERS ───────────────────────────────────────────────────────────────

def _serialize_cart_item(item: CartItem) -> dict:
    variant = item.variant
    product = variant.product
    price = float(variant.price_override or product.sale_price or product.base_price)
    primary = next((img.url for img in product.images if img.is_primary), None) or (product.images[0].url if product.images else None)
    return {
        "id": item.id, "variant_id": variant.id, "quantity": item.quantity,
        "unit_price": price, "total_price": price * item.quantity,
        "product_id": product.id, "product_name": product.name, "product_slug": product.slug,
        "size": variant.size, "color": variant.color, "sku": variant.sku,
        "primary_image": primary, "stock_qty": variant.stock_qty,
        "created_at": item.created_at.isoformat(),
    }


def _serialize_wishlist_item(item: WishlistItem) -> dict:
    product = item.product
    primary = next((img.url for img in product.images if img.is_primary), None) or (product.images[0].url if product.images else None)
    in_stock = any(v.stock_qty > 0 for v in product.variants)
    # Serialize variants
    variants = []
    for v in product.variants:
        variants.append({
            "id": v.id,
            "size": v.size,
            "color": v.color,
            "stock_qty": v.stock_qty,
            "is_active": v.is_active
        })
    return {
        "id": item.id, "product_id": product.id, "product_name": product.name,
        "product_slug": product.slug, "base_price": float(product.base_price),
        "sale_price": float(product.sale_price) if product.sale_price else None,
        "primary_image": primary, "in_stock": in_stock,
        "variants": variants,
        "created_at": item.created_at.isoformat(),
    }
