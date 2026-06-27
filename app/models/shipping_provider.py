from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.shipment import Shipment


class ShippingProvider(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "shipping_providers"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Encrypted config stored as JSONB (API keys, etc.)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    shipments: Mapped[List["Shipment"]] = relationship("Shipment", back_populates="provider")

    def __repr__(self) -> str:
        return f"<ShippingProvider slug={self.slug} active={self.is_active}>"
