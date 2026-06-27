from typing import Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, field_validator


class AddressRequest(BaseModel):
    name: str
    phone: str
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    pincode: str
    country: str = "India"
    is_default: bool = False


class AddressResponse(BaseModel):
    id: str
    name: str
    phone: str
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    pincode: str
    country: str
    is_default: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OrderItemResponse(BaseModel):
    id: str
    variant_id: Optional[str] = None
    product_snapshot: Any
    quantity: int
    unit_price: float
    total_price: float

    model_config = {"from_attributes": True}


class PaymentResponse(BaseModel):
    id: str
    provider: str
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    amount: float
    currency: str
    status: str
    method: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShipmentResponse(BaseModel):
    id: str
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    status: str
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    r2_url: Optional[str] = None
    generated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: str
    user_id: str
    address: AddressResponse
    coupon_id: Optional[str] = None
    items: List[OrderItemResponse] = []
    payment: Optional[PaymentResponse] = None
    shipment: Optional[ShipmentResponse] = None
    invoice: Optional[InvoiceResponse] = None
    subtotal: float
    discount: float
    shipping_charge: float
    tax_amount: float
    total: float
    status: str
    payment_method: str
    payment_status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateOrderRequest(BaseModel):
    address_id: str
    payment_method: str  # 'razorpay' | 'cod'
    coupon_code: Optional[str] = None
    notes: Optional[str] = None


class UpdateOrderStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class CreateRazorpayOrderResponse(BaseModel):
    razorpay_order_id: str
    amount: int  # In paise
    currency: str
    order_id: str  # Our internal order ID
    key_id: str


class PaymentVerifyRequest(BaseModel):
    order_id: str  # Our internal order ID
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class InvoiceDownloadResponse(BaseModel):
    download_url: str
    invoice_number: str
    expires_in: int  # seconds
