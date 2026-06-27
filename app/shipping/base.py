"""
Abstract base class defining the ShippingProvider interface.
All shipping providers MUST implement these three methods.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class ShipmentResult:
    """Result returned by create_shipment()."""
    success: bool
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    provider_shipment_id: Optional[str] = None
    provider_response: Optional[dict] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class TrackingEvent:
    timestamp: datetime
    status: str
    location: Optional[str] = None
    description: Optional[str] = None


@dataclass
class TrackingResult:
    """Result returned by track_shipment()."""
    success: bool
    current_status: Optional[str] = None
    tracking_number: Optional[str] = None
    events: list[TrackingEvent] = field(default_factory=list)
    estimated_delivery: Optional[datetime] = None
    error_message: Optional[str] = None


class ShippingProvider(ABC):
    """
    Abstract interface for all shipping providers.

    To add a new provider:
    1. Create a new class in this package (e.g., `shiprocket.py`)
    2. Inherit from `ShippingProvider`
    3. Implement `create_shipment`, `track_shipment`, and `cancel_shipment`
    4. Register in `factory.py` PROVIDER_REGISTRY
    5. Add provider via admin dashboard — no code restart needed
    """

    @property
    @abstractmethod
    def slug(self) -> str:
        """Unique identifier for this provider (e.g., 'shiprocket')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name for admin display."""
        ...

    @abstractmethod
    async def create_shipment(
        self,
        order: Any,  # Order model — using Any to avoid circular imports
        config: dict,
    ) -> ShipmentResult:
        """
        Create a shipment for the given order.

        Args:
            order: The Order model instance (with related data loaded)
            config: Provider-specific configuration dict from the DB

        Returns:
            ShipmentResult with tracking info or error details
        """
        ...

    @abstractmethod
    async def track_shipment(
        self,
        tracking_number: str,
        config: dict,
    ) -> TrackingResult:
        """
        Fetch current tracking status for a shipment.

        Args:
            tracking_number: The shipment tracking number
            config: Provider-specific configuration dict from the DB

        Returns:
            TrackingResult with current status and event history
        """
        ...

    @abstractmethod
    async def cancel_shipment(
        self,
        tracking_number: str,
        config: dict,
    ) -> bool:
        """
        Cancel a shipment.

        Args:
            tracking_number: The shipment to cancel
            config: Provider-specific configuration dict from the DB

        Returns:
            True if cancelled successfully, False otherwise
        """
        ...
