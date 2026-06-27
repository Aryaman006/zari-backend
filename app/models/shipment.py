from typing import TYPE_CHECKING, Optional
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.shipping_provider import ShippingProvider


class Shipment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "shipments"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    provider_id: Mapped[str] = mapped_column(
        ForeignKey("shipping_providers.id", ondelete="RESTRICT"), nullable=False
    )
    tracking_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    tracking_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="shipment")
    provider: Mapped["ShippingProvider"] = relationship(
        "ShippingProvider", back_populates="shipments"
    )

    def __repr__(self) -> str:
        return f"<Shipment order_id={self.order_id} tracking={self.tracking_number}>"
