from typing import TYPE_CHECKING, Optional
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.order import Order


class Invoice(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "invoices"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    r2_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    r2_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped["Order"] = relationship("Order", back_populates="invoice")

    def __repr__(self) -> str:
        return f"<Invoice number={self.invoice_number} order_id={self.order_id}>"
