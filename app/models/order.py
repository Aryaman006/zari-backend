from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.address import Address
    from app.models.coupon import Coupon
    from app.models.order_item import OrderItem
    from app.models.payment import Payment
    from app.models.shipment import Shipment
    from app.models.invoice import Invoice


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "orders"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    address_id: Mapped[str] = mapped_column(
        ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=False
    )
    coupon_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True
    )

    # Financials
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    discount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    shipping_charge: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)  # razorpay | cod
    payment_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orders")
    address: Mapped["Address"] = relationship("Address", back_populates="orders")
    coupon: Mapped[Optional["Coupon"]] = relationship("Coupon", back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    payment: Mapped[Optional["Payment"]] = relationship(
        "Payment", back_populates="order", uselist=False
    )
    shipment: Mapped[Optional["Shipment"]] = relationship(
        "Shipment", back_populates="order", uselist=False
    )
    invoice: Mapped[Optional["Invoice"]] = relationship(
        "Invoice", back_populates="order", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Order id={self.id} status={self.status} total={self.total}>"
