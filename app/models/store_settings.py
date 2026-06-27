"""
StoreSettings model — key/value store for runtime business configuration.

Replaces the previous uploads/store_settings.json file approach, which was
incompatible with production deployments on Render (ephemeral filesystem).

Keys stored here (matching what the admin settings page saves):
  BUSINESS_NAME, EMAIL_FROM, STORE_PHONE, BUSINESS_ADDRESS,
  RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET,
  RESEND_API_KEY, RESEND_FROM_EMAIL, RAZORPAY_CURRENCY,
  CGST_RATE, SGST_RATE

Values are stored as JSON strings (e.g., floats become "0.09").
"""
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class StoreSetting(Base, TimestampMixin):
    """Runtime store configuration persisted in the database."""

    __tablename__ = "store_settings"

    # The setting key (e.g. "BUSINESS_NAME")
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    # The setting value stored as a JSON-encoded string
    value: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<StoreSetting key={self.key!r}>"
