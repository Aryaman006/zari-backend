from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.cart import CartItem
    from app.models.order_item import OrderItem


class ProductVariant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "product_variants"

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    color_hex: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    price_override: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="variants")
    cart_items: Mapped[List["CartItem"]] = relationship("CartItem", back_populates="variant")
    order_items: Mapped[List["OrderItem"]] = relationship(
        "OrderItem", back_populates="variant"
    )

    def __repr__(self) -> str:
        return f"<ProductVariant sku={self.sku} size={self.size} color={self.color}>"
