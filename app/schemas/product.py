from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel


# ── Category Schemas ──────────────────────────────────────────────────────────

class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_id: Optional[str] = None
    is_active: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_id: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_id: Optional[str] = None
    is_active: bool
    children: Optional[List["CategoryResponse"]] = []
    product_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Allow self-reference
CategoryResponse.model_rebuild()


# ── Product Variant Schemas ───────────────────────────────────────────────────

class ProductVariantBase(BaseModel):
    size: Optional[str] = None
    color: Optional[str] = None
    color_hex: Optional[str] = None
    sku: str
    price_override: Optional[float] = None
    stock_qty: int = 0
    is_active: bool = True


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantUpdate(BaseModel):
    size: Optional[str] = None
    color: Optional[str] = None
    color_hex: Optional[str] = None
    price_override: Optional[float] = None
    stock_qty: Optional[int] = None
    is_active: Optional[bool] = None


class ProductVariantResponse(ProductVariantBase):
    id: str
    product_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Product Image Schemas ─────────────────────────────────────────────────────

class ProductImageResponse(BaseModel):
    id: str
    url: str
    alt_text: Optional[str]
    display_order: int
    is_primary: bool

    model_config = {"from_attributes": True}


# ── Product Schemas ───────────────────────────────────────────────────────────

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    category_id: str
    base_price: float
    sale_price: Optional[float] = None
    is_active: bool = True
    is_featured: bool = False
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    tags: Optional[List[str]] = None
    brand: Optional[str] = None


class ProductCreate(ProductBase):
    variants: Optional[List[ProductVariantCreate]] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    category_id: Optional[str] = None
    base_price: Optional[float] = None
    sale_price: Optional[float] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    tags: Optional[List[str]] = None
    brand: Optional[str] = None


class ProductResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    category_id: str
    category: Optional[CategoryResponse] = None
    base_price: float
    sale_price: Optional[float] = None
    is_active: bool
    is_featured: bool
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    tags: Optional[List[str]] = None
    brand: Optional[str] = None
    images: List[ProductImageResponse] = []
    variants: List[ProductVariantResponse] = []
    primary_image: Optional[str] = None
    in_stock: bool = False
    discount_percent: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
