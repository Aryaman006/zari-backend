from typing import List, Optional
from pydantic import BaseModel
from app.schemas.product import ProductVariantResponse, ProductImageResponse


class CartItemResponse(BaseModel):
    id: str
    variant_id: str
    quantity: int
    unit_price: float
    total_price: float
    product_id: str
    product_name: str
    product_slug: str
    size: Optional[str]
    color: Optional[str]
    sku: str
    primary_image: Optional[str]
    stock_qty: int
    created_at: str

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    items: List[CartItemResponse]
    subtotal: float
    item_count: int


class AddToCartRequest(BaseModel):
    variant_id: str
    quantity: int = 1


class UpdateCartItemRequest(BaseModel):
    quantity: int


class WishlistItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    product_slug: str
    base_price: float
    sale_price: Optional[float]
    primary_image: Optional[str]
    in_stock: bool
    created_at: str

    model_config = {"from_attributes": True}


class CouponApplyRequest(BaseModel):
    code: str


class CouponApplyResponse(BaseModel):
    valid: bool
    code: str
    discount_amount: float
    message: Optional[str] = None
