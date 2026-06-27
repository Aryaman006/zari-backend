"""
Delhivery Shipping Provider — Extension Point

To implement:
1. Register at https://www.delhivery.com/
2. Obtain API token from Delhivery control tower
3. Implement the three methods using Delhivery's REST API:
   https://apigateway.delhivery.com/api/

Config keys expected:
    - api_token: Delhivery API token
    - client_name: Your registered client name
    - pickup_location: Pickup warehouse name
"""
from typing import Any

from app.shipping.base import ShippingProvider, ShipmentResult, TrackingResult


class DelhiveryProvider(ShippingProvider):
    """
    Delhivery shipping provider.
    STATUS: Stub — Not yet implemented.
    """

    DELHIVERY_API_BASE = "https://track.delhivery.com"

    @property
    def slug(self) -> str:
        return "delhivery"

    @property
    def display_name(self) -> str:
        return "Delhivery"

    async def create_shipment(self, order: Any, config: dict) -> ShipmentResult:
        """
        TODO: Create a Delhivery shipment.

        POST {DELHIVERY_API_BASE}/api/cmu/create.json
        Format: multipart/form-data with JSON shipment data
        AWB assignment happens via separate API call after creation.
        """
        raise NotImplementedError("DelhiveryProvider.create_shipment() not yet implemented.")

    async def track_shipment(self, tracking_number: str, config: dict) -> TrackingResult:
        """
        TODO: Track shipment via waybill number.

        GET {DELHIVERY_API_BASE}/api/v1/packages/json/?waybill={waybill}
        """
        raise NotImplementedError("DelhiveryProvider.track_shipment() not yet implemented.")

    async def cancel_shipment(self, tracking_number: str, config: dict) -> bool:
        """
        TODO: Cancel a Delhivery shipment.

        POST {DELHIVERY_API_BASE}/api/p/edit
        Body: { "waybill": ..., "cancellation": true }
        """
        raise NotImplementedError("DelhiveryProvider.cancel_shipment() not yet implemented.")
