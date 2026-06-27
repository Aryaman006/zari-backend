"""
Manual Shipping Provider — Admin manually enters tracking info.
This is the default provider for small businesses that manage
their own logistics or use local couriers.
"""
from datetime import datetime, timezone
from typing import Any

from app.shipping.base import ShippingProvider, ShipmentResult, TrackingResult, TrackingEvent


class ManualProvider(ShippingProvider):
    """
    Manual shipping provider.

    The admin manually:
    - Creates the shipment (enters tracking number + URL)
    - Updates tracking status through the admin dashboard
    - Marks as delivered manually

    No API integration required. Perfect for:
    - India Post
    - Local courier services
    - Self-delivery
    - Testing/development
    """

    @property
    def slug(self) -> str:
        return "manual"

    @property
    def display_name(self) -> str:
        return "Manual (Admin Managed)"

    async def create_shipment(self, order: Any, config: dict) -> ShipmentResult:
        """
        For manual provider, the 'shipment' is created immediately as a placeholder.
        Admin will later fill in the actual tracking number via the admin dashboard.
        """
        return ShipmentResult(
            success=True,
            tracking_number=config.get("tracking_number"),  # May be None initially
            tracking_url=config.get("tracking_url"),
            provider_shipment_id=f"MANUAL-{order.id[:8].upper()}",
            provider_response={"type": "manual", "order_id": order.id},
        )

    async def track_shipment(self, tracking_number: str, config: dict) -> TrackingResult:
        """
        Manual tracking — return whatever the admin has last entered.
        No external API call needed.
        """
        return TrackingResult(
            success=True,
            current_status="in_transit",
            tracking_number=tracking_number,
            events=[
                TrackingEvent(
                    timestamp=datetime.now(timezone.utc),
                    status="in_transit",
                    description="Package is in transit. Contact support for updates.",
                )
            ],
        )

    async def cancel_shipment(self, tracking_number: str, config: dict) -> bool:
        """
        Manual cancellation — just return True. Admin handles the physical process.
        """
        return True
