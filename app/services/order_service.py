"""
Order service — manages order creation from cart, status transitions,
coupon application, and inventory deduction.
"""
import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.config import settings
from app.models.cart import CartItem
from app.models.coupon import Coupon
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.repositories.order_repository import OrderRepository
from app.repositories.user_repository import UserRepository
from app.schemas.order import CreateOrderRequest

logger = logging.getLogger(__name__)


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.order_repo = OrderRepository(session)

    async def create_order(self, user_id: str, data: CreateOrderRequest) -> Order:
        """
        Create a new order from the user's cart.
        Steps:
        1. Load cart items
        2. Validate stock availability
        3. Apply coupon if provided
        4. Calculate totals with GST
        5. Create Order + OrderItems
        6. Deduct stock
        7. Clear cart
        """
        from sqlalchemy.orm import selectinload

        # Load cart items with full product/variant info
        result = await self.session.execute(
            select(CartItem)
            .where(CartItem.user_id == user_id)
            .options(
                selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
                .selectinload(Product.images)
            )
        )
        cart_items = result.scalars().all()


        if not cart_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your cart is empty.",
            )

        # Validate stock
        for item in cart_items:
            variant = item.variant
            if not variant or not variant.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"A product in your cart is no longer available.",
                )
            if variant.stock_qty < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Insufficient stock for '{variant.product.name}' "
                           f"(Size: {variant.size}, Color: {variant.color}). "
                           f"Only {variant.stock_qty} left.",
                )

        # Validate payment method
        if data.payment_method not in ("razorpay", "cod"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment method.",
            )

        # COD limit check
        subtotal = sum(
            float(item.variant.price_override or item.variant.product.sale_price or item.variant.product.base_price) * item.quantity
            for item in cart_items
        )
        if data.payment_method == "cod":
            if not settings.COD_ENABLED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cash on Delivery is not available.",
                )
            if subtotal > settings.COD_MAX_AMOUNT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cash on Delivery is available for orders up to ₹{settings.COD_MAX_AMOUNT:,.0f}.",
                )

        # Apply coupon
        discount = 0.0
        coupon: Optional[Coupon] = None
        if data.coupon_code:
            coupon = await self._validate_coupon(data.coupon_code, subtotal)
            discount = self._calculate_discount(coupon, subtotal)

        # Calculate GST
        taxable = subtotal - discount
        cgst = taxable * settings.CGST_RATE
        sgst = taxable * settings.SGST_RATE
        tax_amount = cgst + sgst
        shipping_charge = 0.0  # Free shipping (can be made dynamic later)
        total = taxable + tax_amount + shipping_charge

        # Validate address belongs to user
        from app.models.address import Address
        addr_result = await self.session.execute(
            select(Address).where(
                Address.id == data.address_id,
                Address.user_id == user_id,
            )
        )
        address = addr_result.scalar_one_or_none()
        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found.",
            )

        # Create Order
        order = Order(
            user_id=user_id,
            address_id=data.address_id,
            coupon_id=coupon.id if coupon else None,
            subtotal=subtotal,
            discount=discount,
            shipping_charge=shipping_charge,
            tax_amount=tax_amount,
            total=total,
            status="pending",
            payment_method=data.payment_method,
            payment_status="pending",
            notes=data.notes,
        )
        self.session.add(order)
        await self.session.flush()

        # Create OrderItems + deduct stock
        for item in cart_items:
            variant = item.variant
            product = variant.product
            effective_price = float(
                variant.price_override or product.sale_price or product.base_price
            )

            # Product snapshot — preserves info at time of purchase
            snapshot = {
                "product_id": product.id,
                "product_name": product.name,
                "variant_id": variant.id,
                "size": variant.size,
                "color": variant.color,
                "sku": variant.sku,
                "image_url": next(
                    (img.url for img in product.images if img.is_primary),
                    product.images[0].url if product.images else None,
                ),
            }

            order_item = OrderItem(
                order_id=order.id,
                variant_id=variant.id,
                product_snapshot=snapshot,
                quantity=item.quantity,
                unit_price=effective_price,
                total_price=effective_price * item.quantity,
            )
            self.session.add(order_item)

            # Deduct stock
            await self.session.execute(
                update(ProductVariant)
                .where(ProductVariant.id == variant.id)
                .values(stock_qty=ProductVariant.stock_qty - item.quantity)
            )

        # Increment coupon usage
        if coupon:
            await self.session.execute(
                update(Coupon)
                .where(Coupon.id == coupon.id)
                .values(used_count=Coupon.used_count + 1)
            )

        # Clear cart
        await self.session.execute(
            __import__("sqlalchemy", fromlist=["delete"]).delete(CartItem)
            .where(CartItem.user_id == user_id)
        )

        await self.session.flush()
        return await self.order_repo.get_by_id_with_relations(order.id)

    async def update_order_status(
        self, order_id: str, new_status: str, notes: Optional[str] = None
    ) -> Order:
        """Admin: update order status."""
        order = await self.order_repo.get_by_id_with_relations(order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

        updates = {"status": new_status}
        if notes:
            updates["notes"] = notes
        await self.order_repo.update_instance(order, **updates)
        return await self.order_repo.get_by_id_with_relations(order_id)

    async def _validate_coupon(self, code: str, subtotal: float) -> Coupon:
        """Validate coupon code and return the Coupon model."""
        from datetime import datetime, timezone
        result = await self.session.execute(
            select(Coupon).where(Coupon.code == code.upper(), Coupon.is_active == True)
        )
        coupon = result.scalar_one_or_none()

        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Coupon '{code}' is invalid or has expired.",
            )
        if coupon.expires_at and coupon.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This coupon has expired.",
            )
        if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This coupon has reached its usage limit.",
            )
        if coupon.min_order_amount and subtotal < float(coupon.min_order_amount):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This coupon requires a minimum order of ₹{coupon.min_order_amount:,.0f}.",
            )
        return coupon

    def _calculate_discount(self, coupon: Coupon, subtotal: float) -> float:
        """Calculate discount amount from coupon."""
        if coupon.type == "percent":
            discount = subtotal * (float(coupon.value) / 100)
            if coupon.max_discount:
                discount = min(discount, float(coupon.max_discount))
        else:  # flat
            discount = min(float(coupon.value), subtotal)
        return round(discount, 2)
