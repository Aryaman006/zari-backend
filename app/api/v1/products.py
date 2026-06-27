from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status, Body
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.dependencies import DbSession, CurrentAdmin
from app.models.category import Category
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.product_image import ProductImage
from app.repositories.product_repository import ProductRepository
from app.schemas.product import (
    CategoryCreate, CategoryUpdate, CategoryResponse,
    ProductCreate, ProductUpdate, ProductResponse,
    ProductVariantCreate, ProductVariantUpdate, ProductVariantResponse,
    ProductImageResponse,
)
from app.schemas.common import PaginatedResponse, MessageResponse, PresignedUrlResponse
from app.services.storage_service import storage_service
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products — Public"])
admin_router = APIRouter(prefix="/admin/products", tags=["Admin — Products"])
category_router = APIRouter(prefix="/categories", tags=["Categories — Public"])
admin_category_router = APIRouter(prefix="/admin/categories", tags=["Admin — Categories"])


# ── PUBLIC PRODUCT ROUTES ─────────────────────────────────────────────────────

@router.get("")
async def list_products(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[str] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort_by: str = Query("created_at", enum=["created_at", "base_price", "name"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    featured: Optional[bool] = None,
):
    """List products with full filtering, search, and pagination."""
    repo = ProductRepository(db)
    offset = (page - 1) * page_size
    products, total = await repo.list_products(
        category_id=category_id,
        search=search,
        is_featured=featured,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=page_size,
        offset=offset,
    )
    return {
        "data": [_serialize_product(p) for p in products],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/featured")
async def get_featured_products(db: DbSession, limit: int = Query(8, le=20)):
    """Get featured products for the homepage."""
    repo = ProductRepository(db)
    products, _ = await repo.list_products(is_featured=True, limit=limit)
    return [_serialize_product(p) for p in products]


@router.get("/{slug}")
async def get_product(slug: str, db: DbSession):
    """Get a single product by slug with all variants and images."""
    repo = ProductRepository(db)
    product = await repo.get_by_slug(slug)
    if not product or not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return _serialize_product(product)


# ── PUBLIC CATEGORY ROUTES ────────────────────────────────────────────────────

@category_router.get("")
async def list_categories(db: DbSession, parent_only: bool = True):
    """List all active categories. Use parent_only=false for full tree."""
    
    query = select(Category).where(Category.is_active == True)
    if parent_only:
        query = query.where(Category.parent_id == None)
    query = query.options(selectinload(Category.children))
    result = await db.execute(query.order_by(Category.name))
    cats = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "description": c.description,
            "image_url": c.image_url,
            "parent_id": c.parent_id,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
            "children": [
                {"id": ch.id, "name": ch.name, "slug": ch.slug, "is_active": ch.is_active}
                for ch in c.children
            ] if c.children else [],
        }
        for c in cats
    ]


@category_router.get("/{slug}/products")
async def get_category_products(
    slug: str,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get products by category slug."""
    cat_result = await db.execute(select(Category).where(Category.slug == slug, Category.is_active == True))
    category = cat_result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")

    repo = ProductRepository(db)
    offset = (page - 1) * page_size
    products, total = await repo.list_products(category_id=category.id, limit=page_size, offset=offset)
    return {
        "data": [_serialize_product(p) for p in products],
        "total": total, "page": page, "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# ── ADMIN PRODUCT ROUTES ──────────────────────────────────────────────────────

@admin_router.get("")
async def admin_list_products(
    db: DbSession, _: CurrentAdmin,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None, is_active: Optional[bool] = None,
):
    repo = ProductRepository(db)
    offset = (page - 1) * page_size
    products, total = await repo.list_products(search=search, is_active=is_active, limit=page_size, offset=offset)
    return {
        "data": [_serialize_product(p) for p in products],
        "total": total, "page": page, "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@admin_router.post("", status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, db: DbSession, _: CurrentAdmin):
    service = ProductService(db)
    product = await service.create_product(data)
    return _serialize_product(product)


@admin_router.get("/{product_id}")
async def admin_get_product(product_id: str, db: DbSession, _: CurrentAdmin):
    repo = ProductRepository(db)
    product = await repo.get_by_id_with_relations(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return _serialize_product(product)


@admin_router.put("/{product_id}")
async def update_product(product_id: str, data: ProductUpdate, db: DbSession, _: CurrentAdmin):
    service = ProductService(db)
    product = await service.update_product(product_id, data)
    return _serialize_product(product)


@admin_router.delete("/{product_id}", response_model=MessageResponse)
async def delete_product(product_id: str, db: DbSession, _: CurrentAdmin):
    service = ProductService(db)
    await service.delete_product(product_id)
    return {"message": "Product deleted successfully."}


@admin_router.post("/{product_id}/variants", response_model=ProductVariantResponse, status_code=201)
async def add_variant(product_id: str, data: ProductVariantCreate, db: DbSession, _: CurrentAdmin):
    service = ProductService(db)
    return await service.add_variant(product_id, data)


@admin_router.put("/{product_id}/variants/{variant_id}", response_model=ProductVariantResponse)
async def update_variant(product_id: str, variant_id: str, data: ProductVariantUpdate, db: DbSession, _: CurrentAdmin):
    service = ProductService(db)
    return await service.update_variant(product_id, variant_id, data)


@admin_router.delete("/{product_id}/variants/{variant_id}", response_model=MessageResponse)
async def delete_variant(product_id: str, variant_id: str, db: DbSession, _: CurrentAdmin):
    service = ProductService(db)
    await service.delete_variant(product_id, variant_id)
    return {"message": "Variant deleted."}


@admin_router.post("/{product_id}/images/upload-url", response_model=PresignedUrlResponse)
async def get_image_upload_url(product_id: str, filename: str, db: DbSession, _: CurrentAdmin):
    """Get a presigned URL to upload a product image directly to R2."""
    result = await storage_service.generate_upload_url(
        folder=f"products/{product_id}", filename=filename
    )
    return result


@admin_router.post("/{product_id}/images", response_model=ProductImageResponse, status_code=201)
async def add_image(
    product_id: str,
    r2_key: str,
    url: str,
    alt_text: Optional[str] = None,
    is_primary: bool = False,
    db: DbSession = None,
    _: CurrentAdmin = None,
):
    service = ProductService(db)
    return await service.add_image(product_id, r2_key, url, alt_text, is_primary)


@admin_router.delete("/{product_id}/images/{image_id}", response_model=MessageResponse)
async def delete_image(product_id: str, image_id: str, db: DbSession, _: CurrentAdmin):
    service = ProductService(db)
    await service.delete_image(product_id, image_id)
    return {"message": "Image deleted."}


@admin_router.put("/{product_id}/images/reorder", response_model=MessageResponse)
async def reorder_images(
    product_id: str,
    image_ids: list[str] = Body(...),
    db: DbSession = None,
    _: CurrentAdmin = None,
):
    from sqlalchemy import update
    for index, img_id in enumerate(image_ids):
        await db.execute(
            update(ProductImage)
            .where(ProductImage.id == img_id, ProductImage.product_id == product_id)
            .values(display_order=index)
        )
    await db.flush()
    return {"message": "Images reordered successfully."}


# ── ADMIN CATEGORY ROUTES ─────────────────────────────────────────────────────

@admin_category_router.get("", response_model=list[CategoryResponse])
async def admin_list_categories(db: DbSession, _: CurrentAdmin):
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Category).options(selectinload(Category.children)).order_by(Category.name)
    )
    return result.scalars().all()


@admin_category_router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(data: CategoryCreate, db: DbSession, _: CurrentAdmin):
    from app.services.product_service import ProductService
    service = ProductService(db)
    return await service.create_category(data)


@admin_category_router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: str, data: CategoryUpdate, db: DbSession, _: CurrentAdmin):
    from app.services.product_service import ProductService
    service = ProductService(db)
    return await service.update_category(category_id, data)


@admin_category_router.delete("/{category_id}", response_model=MessageResponse)
async def delete_category(category_id: str, db: DbSession, _: CurrentAdmin):
    cat = await db.get(Category, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")
    await db.delete(cat)
    return {"message": "Category deleted."}


# ── SERIALIZER ────────────────────────────────────────────────────────────────

def _serialize_product(p: Product) -> dict:
    primary_image = next((img.url for img in p.images if img.is_primary), None)
    if not primary_image and p.images:
        primary_image = p.images[0].url
    in_stock = any(v.stock_qty > 0 and v.is_active for v in p.variants)
    discount_pct = None
    if p.sale_price and p.base_price and p.base_price > 0:
        discount_pct = round(((float(p.base_price) - float(p.sale_price)) / float(p.base_price)) * 100)

    # Serialize category eagerly (avoids DetachedInstanceError after session close)
    category_dict = None
    if p.category is not None:
        cat = p.category
        category_dict = {
            "id": cat.id,
            "name": cat.name,
            "slug": cat.slug,
            "description": cat.description,
            "image_url": cat.image_url,
            "parent_id": cat.parent_id,
            "is_active": cat.is_active,
            "created_at": cat.created_at.isoformat(),
            "updated_at": cat.updated_at.isoformat(),
        }

    # Serialize images
    images_list = [
        {
            "id": img.id,
            "url": img.url,
            "alt_text": img.alt_text,
            "display_order": img.display_order,
            "is_primary": img.is_primary,
        }
        for img in p.images
    ]

    # Serialize variants
    variants_list = [
        {
            "id": v.id,
            "product_id": v.product_id,
            "size": v.size,
            "color": v.color,
            "color_hex": v.color_hex,
            "sku": v.sku,
            "price_override": float(v.price_override) if v.price_override else None,
            "stock_qty": v.stock_qty,
            "is_active": v.is_active,
            "created_at": v.created_at.isoformat(),
            "updated_at": v.updated_at.isoformat(),
        }
        for v in p.variants
    ]

    return {
        "id": p.id,
        "name": p.name,
        "slug": p.slug,
        "description": p.description,
        "short_description": p.short_description,
        "category_id": p.category_id,
        "is_active": p.is_active,
        "is_featured": p.is_featured,
        "meta_title": p.meta_title,
        "meta_description": p.meta_description,
        "tags": p.tags,
        "brand": p.brand,
        "base_price": float(p.base_price),
        "sale_price": float(p.sale_price) if p.sale_price else None,
        "category": category_dict,
        "images": images_list,
        "variants": variants_list,
        "primary_image": primary_image,
        "in_stock": in_stock,
        "discount_percent": discount_pct,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }

