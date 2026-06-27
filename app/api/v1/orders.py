from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import select

from app.core.dependencies import DbSession, CurrentUser, CurrentAdmin
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.schemas.order import (
    CreateOrderRequest, OrderResponse, UpdateOrderStatusRequest,
    CreateRazorpayOrderResponse, PaymentVerifyRequest, InvoiceDownloadResponse,
)
from app.schemas.common import PaginatedResponse, MessageResponse
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/orders", tags=["Orders"])
payment_router = APIRouter(prefix="/payments", tags=["Payments"])
admin_order_router = APIRouter(prefix="/admin/orders", tags=["Admin — Orders"])
invoice_router = APIRouter(prefix="/invoices", tags=["Invoices"])


# ── CUSTOMER ORDER ROUTES ─────────────────────────────────────────────────────

@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    data: CreateOrderRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create an order from the current user's cart."""
    service = OrderService(db)
    order = await service.create_order(current_user.id, data)

    # Auto-confirm COD orders and generate invoice
    if order.payment_method == "cod":
        await service.order_repo.update_instance(order, status="confirmed", payment_status="pending")
        background_tasks.add_task(_generate_invoice_bg, order.id)
        background_tasks.add_task(
            _send_order_confirmation_bg, current_user.id, order.id, float(order.total)
        )

    return order


@router.get("", response_model=PaginatedResponse[OrderResponse])
async def get_my_orders(
    db: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 10,
):
    """Get the authenticated user's order history."""
    repo = OrderRepository(db)
    offset = (page - 1) * page_size
    orders, total = await repo.get_user_orders(current_user.id, limit=page_size, offset=offset)
    return {
        "data": list(orders), "total": total, "page": page,
        "page_size": page_size, "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, db: DbSession, current_user: CurrentUser):
    """Get a specific order by ID (must belong to current user)."""
    repo = OrderRepository(db)
    order = await repo.get_by_id_with_relations(order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


# ── PAYMENT ROUTES ────────────────────────────────────────────────────────────

@payment_router.post("/create-razorpay-order", response_model=CreateRazorpayOrderResponse)
async def create_razorpay_order(order_id: str, db: DbSession, current_user: CurrentUser):
    """Create a Razorpay order for payment. Call after creating the internal order."""
    repo = OrderRepository(db)
    order = await repo.get_by_id_with_relations(order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.payment_method != "razorpay":
        raise HTTPException(status_code=400, detail="This order does not use Razorpay.")

    payment_service = PaymentService(db)
    return await payment_service.create_razorpay_order(order)


@payment_router.post("/verify", response_model=OrderResponse)
async def verify_payment(
    data: PaymentVerifyRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
):
    """Verify Razorpay payment signature and confirm the order."""
    payment_service = PaymentService(db)
    order = await payment_service.verify_payment(
        order_id=data.order_id,
        razorpay_order_id=data.razorpay_order_id,
        razorpay_payment_id=data.razorpay_payment_id,
        razorpay_signature=data.razorpay_signature,
    )
    # Generate invoice + send confirmation in background
    background_tasks.add_task(_generate_invoice_bg, order.id)
    background_tasks.add_task(
        _send_order_confirmation_bg, current_user.id, order.id, float(order.total)
    )
    return order


@payment_router.post("/webhook")
async def razorpay_webhook(request: Request, background_tasks: BackgroundTasks, db: DbSession):
    """
    Razorpay webhook endpoint — backup payment confirmation.
    IMPORTANT: This endpoint must receive the raw body for signature verification.
    """
    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")

    if not PaymentService.verify_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    import json
    payload = json.loads(raw_body)

    # Process in background to respond quickly to Razorpay
    background_tasks.add_task(_process_webhook_bg, payload, raw_body, signature)
    return {"status": "ok"}


# ── INVOICE ROUTES ────────────────────────────────────────────────────────────

@invoice_router.get("/{order_id}/download", response_model=InvoiceDownloadResponse)
async def get_invoice_download_url(order_id: str, db: DbSession, current_user: CurrentUser):
    """
    Get a presigned download URL for an order's invoice PDF.

    Business rule: Invoices are only accessible AFTER the order has been delivered.
    This prevents customers from accessing billing documents before fulfilment is complete.
    """
    repo = OrderRepository(db)
    order = await repo.get_by_id_with_relations(order_id)
    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found.")

    # ── Delivery gate ─────────────────────────────────────────────────────────
    if order.status != "delivered":
        raise HTTPException(
            status_code=403,
            detail="Your invoice will be available once your order has been delivered.",
        )

    if not order.invoice:
        raise HTTPException(status_code=404, detail="Invoice not yet generated for this order.")

    invoice_service = InvoiceService(db)
    download_url = await invoice_service.get_download_url(order.invoice)
    return {
        "download_url": download_url,
        "invoice_number": order.invoice.invoice_number,
        "expires_in": 3600,
    }


# ── ADMIN ORDER ROUTES ────────────────────────────────────────────────────────

@admin_order_router.get("", response_model=PaginatedResponse[OrderResponse])
async def admin_list_orders(
    db: DbSession, _: CurrentAdmin,
    page: int = 1, page_size: int = 20,
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    search: Optional[str] = None,
):
    repo = OrderRepository(db)
    offset = (page - 1) * page_size
    orders, total = await repo.list_all_orders(
        status=status, payment_status=payment_status, search=search, limit=page_size, offset=offset
    )
    return {
        "data": list(orders), "total": total, "page": page,
        "page_size": page_size, "total_pages": (total + page_size - 1) // page_size,
    }


@admin_order_router.get("/{order_id}", response_model=OrderResponse)
async def admin_get_order(order_id: str, db: DbSession, _: CurrentAdmin):
    repo = OrderRepository(db)
    order = await repo.get_by_id_with_relations(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


@admin_order_router.put("/{order_id}/status", response_model=OrderResponse)
async def admin_update_order_status(
    order_id: str, data: UpdateOrderStatusRequest, db: DbSession, _: CurrentAdmin
):
    service = OrderService(db)
    return await service.update_order_status(order_id, data.status, data.notes)


@admin_order_router.post("/{order_id}/generate-invoice", response_model=InvoiceDownloadResponse)
async def admin_generate_invoice(order_id: str, db: DbSession, _: CurrentAdmin):
    """Manually trigger invoice generation for an order."""
    invoice_service = InvoiceService(db)
    invoice = await invoice_service.generate_invoice(order_id)
    download_url = await invoice_service.get_download_url(invoice)
    return {"download_url": download_url, "invoice_number": invoice.invoice_number, "expires_in": 3600}


# ── BACKGROUND TASKS ──────────────────────────────────────────────────────────

async def _generate_invoice_bg(order_id: str):
    """Background task: generate invoice after payment."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        try:
            service = InvoiceService(session)
            await service.generate_invoice(order_id)
            await session.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Invoice generation failed for {order_id}: {e}")


async def _send_order_confirmation_bg(user_id: str, order_id: str, total: float):
    """Background task: send order confirmation email."""
    from app.core.database import AsyncSessionLocal
    from app.repositories.user_repository import UserRepository
    from app.services.email_service import EmailService
    async with AsyncSessionLocal() as session:
        try:
            user = await UserRepository(session).get_by_id(user_id)
            if user:
                await EmailService().send_order_confirmation_email(user, order_id, total)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Order confirmation email failed for {order_id}: {e}")


async def _process_webhook_bg(payload: dict, raw_body: bytes, signature: str):
    """Background task: process Razorpay webhook."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        try:
            service = PaymentService(session)
            await service.process_webhook(payload, raw_body, signature)
            await session.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Webhook processing failed: {e}")
