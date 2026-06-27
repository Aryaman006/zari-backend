"""
Shiprocket Shipping Provider — Extension Point

To implement:
1. Sign up at https://app.shiprocket.in/
2. Obtain API credentials (email + password for OAuth)
3. Install: pip install requests
4. Implement the three methods below following the Shiprocket V1 API docs:
   https://apidocs.shiprocket.in/

Config keys expected (stored in shipping_providers.config):
    - email: Shiprocket account email
    - password: Shiprocket account password
    - pickup_location: Pickup location name configured in Shiprocket dashboard
"""
from typing import Any

from app.shipping.base import ShippingProvider, ShipmentResult, TrackingResult


class ShiprocketProvider(ShippingProvider):
    """
    Shiprocket shipping provider.
    STATUS: Stub — Not yet implemented.
    """

    SHIPROCKET_API_BASE = "https://apiv2.shiprocket.in/v1/external"

    @property
    def slug(self) -> str:
        return "shiprocket"

    @property
    def display_name(self) -> str:
        return "Shiprocket"

    async def _get_auth_token(self, config: dict) -> str:
        """
        Authenticate with Shiprocket API.

        TODO: Implement OAuth token fetch.
        POST {SHIPROCKET_API_BASE}/auth/login
        Body: { "email": ..., "password": ... }
        Returns: token from response["token"]

        Consider caching the token (valid for 24h) using Redis or in-memory cache.
        """
        raise NotImplementedError(
            "ShiprocketProvider is not yet implemented. "
            "See the docstring in this file for implementation instructions."
        )

    async def create_shipment(self, order: Any, config: dict) -> ShipmentResult:
        """
        TODO: Create a Shiprocket order.

        POST {SHIPROCKET_API_BASE}/orders/create/adhoc
        Required fields: order_id, order_date, pickup_location, billing_*,
                         shipping_*, order_items, payment_method, sub_total, length,
                         breadth, height, weight

        On success: AWB number is the tracking number.
        """
        raise NotImplementedError("ShiprocketProvider.create_shipment() not yet implemented.")

    async def track_shipment(self, tracking_number: str, config: dict) -> TrackingResult:
        """
        TODO: Track shipment via AWB number.

        GET {SHIPROCKET_API_BASE}/courier/track/awb/{awb_number}
        """
        raise NotImplementedError("ShiprocketProvider.track_shipment() not yet implemented.")

    async def cancel_shipment(self, tracking_number: str, config: dict) -> bool:
        """
        TODO: Cancel a Shiprocket order.

        POST {SHIPROCKET_API_BASE}/orders/cancel
        Body: { "ids": [order_id] }
        """
        raise NotImplementedError("ShiprocketProvider.cancel_shipment() not yet implemented.")
