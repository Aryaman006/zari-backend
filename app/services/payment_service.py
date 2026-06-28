"""
Razorpay payment service — handles order creation, payment verification,
webhook processing, and COD order flow.
"""
import hashlib
import hmac
import logging
from typing import Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.order import Order
from app.models.payment import Payment
from app.repositories.order_repository import OrderRepository
from app.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.order_repo = OrderRepository(session)

    async def create_razorpay_order(self, order: Order) -> dict:
        """
        Create a Razorpay order for the given internal order.
        Returns Razorpay order details needed by the frontend SDK.
        """
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise RuntimeError("Razorpay is not configured.")

        # Amount in paise (Razorpay requires integer paise)
        amount_paise = int(order.total * 100)

        url = "https://api.razorpay.com/v1/orders"
        payload = {
            "amount": amount_paise,
            "currency": settings.RAZORPAY_CURRENCY,
            "receipt": f"order_{order.id[:8]}",
            "notes": {
                "order_id": order.id,
                "customer_email": order.user.email if order.user else "",
            },
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
                    timeout=15.0,
                )
            except Exception as e:
                logger.error(f"Error connecting to Razorpay: {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to connect to payment gateway."
                )

        if response.status_code not in (200, 201):
            logger.error(f"Razorpay order API failed with status {response.status_code}: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment gateway returned an error during order creation."
            )

        rz_order = response.json()

        # Create payment record
        payment = Payment(
            order_id=order.id,
            provider="razorpay",
            razorpay_order_id=rz_order["id"],
            amount=order.total,
            currency=settings.RAZORPAY_CURRENCY,
            status="pending",
        )
        self.session.add(payment)
        await self.session.flush()

        return {
            "razorpay_order_id": rz_order["id"],
            "amount": amount_paise,
            "currency": settings.RAZORPAY_CURRENCY,
            "order_id": order.id,
            "key_id": settings.RAZORPAY_KEY_ID,
        }

    async def verify_payment(
        self,
        order_id: str,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> Order:
        """
        Verify Razorpay payment signature and mark order as paid.
        This is the PRIMARY payment confirmation path.
        """
        if not settings.RAZORPAY_KEY_SECRET:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Payment service is not configured.",
            )
        # Verify HMAC signature
        expected_sig = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, razorpay_signature):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment signature verification failed.",
            )

        order = await self.order_repo.get_by_id_with_relations(order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

        if order.payment_status == "paid":
            return order  # Idempotent

        # Update payment record
        if order.payment:
            await self.order_repo.session.execute(
                __import__("sqlalchemy", fromlist=["update"]).update(Payment)
                .where(Payment.order_id == order_id)
                .values(
                    razorpay_payment_id=razorpay_payment_id,
                    razorpay_signature=razorpay_signature,
                    status="paid",
                )
            )

        # Update order status
        await self.order_repo.update_instance(
            order,
            payment_status="paid",
            status="confirmed",
        )

        return order

    async def process_webhook(self, payload: dict, raw_body: bytes, signature: str) -> None:
        """
        Process Razorpay webhook events.
        Called as a background task after signature verification.
        """
        event = payload.get("event")
        logger.info(f"Processing Razorpay webhook: {event}")

        if event == "payment.captured":
            payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            rz_order_id = payment_entity.get("order_id")
            rz_payment_id = payment_entity.get("id")
            method = payment_entity.get("method")

            # Find our order by Razorpay order ID
            from sqlalchemy import select
            result = await self.session.execute(
                select(Payment).where(Payment.razorpay_order_id == rz_order_id)
            )
            payment = result.scalar_one_or_none()
            if payment:
                payment.razorpay_payment_id = rz_payment_id
                payment.method = method
                payment.status = "paid"
                payment.webhook_payload = payload

                # Update order
                order = await self.order_repo.get_by_id_with_relations(payment.order_id)
                if order and order.payment_status != "paid":
                    await self.order_repo.update_instance(
                        order, payment_status="paid", status="confirmed"
                    )

        elif event == "refund.processed":
            payment_entity = payload.get("payload", {}).get("refund", {}).get("entity", {})
            rz_payment_id = payment_entity.get("payment_id")
            from sqlalchemy import select
            result = await self.session.execute(
                select(Payment).where(Payment.razorpay_payment_id == rz_payment_id)
            )
            payment = result.scalar_one_or_none()
            if payment:
                payment.status = "refunded"
                order = await self.order_repo.get_by_id_with_relations(payment.order_id)
                if order:
                    await self.order_repo.update_instance(
                        order, payment_status="refunded", status="refunded"
                    )

    @staticmethod
    def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
        """Verify Razorpay webhook signature."""
        if not settings.RAZORPAY_WEBHOOK_SECRET:
            # Webhook secret not configured — skip verification in development
            logger.warning(
                "RAZORPAY_WEBHOOK_SECRET not configured. "
                "Webhook signature verification skipped (development mode)."
            )
            return settings.APP_ENV == "development"  # Allow in dev, block in prod

        expected = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)
