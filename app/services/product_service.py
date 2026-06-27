"""Product service — handles product/category/variant/image CRUD with slug generation."""
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.product_image import ProductImage
from app.models.category import Category
from app.repositories.product_repository import ProductRepository
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductVariantCreate, ProductVariantUpdate,
    CategoryCreate, CategoryUpdate,
)
from app.services.storage_service import storage_service


def _slugify(text: str) -> str:
    import re
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ProductRepository(session)

    async def create_product(self, data: ProductCreate) -> Product:
        base_slug = _slugify(data.name)
        slug = base_slug
        counter = 1
        while await self.repo.slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        product = Product(
            name=data.name,
            slug=slug,
            description=data.description,
            short_description=data.short_description,
            category_id=data.category_id,
            base_price=data.base_price,
            sale_price=data.sale_price,
            is_active=data.is_active,
            is_featured=data.is_featured,
            meta_title=data.meta_title or data.name[:60],
            meta_description=data.meta_description,
            tags=data.tags,
            brand=data.brand,
        )
        self.session.add(product)
        await self.session.flush()

        if data.variants:
            for v in data.variants:
                variant = ProductVariant(product_id=product.id, **v.model_dump())
                self.session.add(variant)

        await self.session.flush()
        return await self.repo.get_by_id_with_relations(product.id)

    async def update_product(self, product_id: str, data: ProductUpdate) -> Product:
        product = await self.repo.get_by_id_with_relations(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found.")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)

        await self.session.flush()
        return await self.repo.get_by_id_with_relations(product_id)

    async def delete_product(self, product_id: str) -> None:
        product = await self.session.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found.")
        # Soft delete
        product.is_active = False
        await self.session.flush()

    async def add_variant(self, product_id: str, data: ProductVariantCreate) -> ProductVariant:
        product = await self.session.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found.")
        variant = ProductVariant(product_id=product_id, **data.model_dump())
        self.session.add(variant)
        await self.session.flush()
        await self.session.refresh(variant)
        return variant

    async def update_variant(self, product_id: str, variant_id: str, data: ProductVariantUpdate) -> ProductVariant:
        result = await self.session.execute(
            select(ProductVariant).where(
                ProductVariant.id == variant_id, ProductVariant.product_id == product_id
            )
        )
        variant = result.scalar_one_or_none()
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found.")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(variant, key, value)
        await self.session.flush()
        return variant

    async def delete_variant(self, product_id: str, variant_id: str) -> None:
        result = await self.session.execute(
            select(ProductVariant).where(
                ProductVariant.id == variant_id, ProductVariant.product_id == product_id
            )
        )
        variant = result.scalar_one_or_none()
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found.")
        await self.session.delete(variant)
        await self.session.flush()

    async def add_image(self, product_id: str, r2_key: str, url: str, alt_text: Optional[str], is_primary: bool) -> ProductImage:
        if is_primary:
            # Unset any existing primary
            from sqlalchemy import update
            await self.session.execute(
                update(ProductImage)
                .where(ProductImage.product_id == product_id)
                .values(is_primary=False)
            )
        result = await self.session.execute(
            select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.display_order.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        order = (last.display_order + 1) if last else 0
        image = ProductImage(product_id=product_id, r2_key=r2_key, url=url, alt_text=alt_text, is_primary=is_primary, display_order=order)
        self.session.add(image)
        await self.session.flush()
        await self.session.refresh(image)
        return image

    async def delete_image(self, product_id: str, image_id: str) -> None:
        result = await self.session.execute(
            select(ProductImage).where(ProductImage.id == image_id, ProductImage.product_id == product_id)
        )
        image = result.scalar_one_or_none()
        if not image:
            raise HTTPException(status_code=404, detail="Image not found.")
        if image.r2_key:
            try:
                await storage_service.delete_object(image.r2_key)
            except Exception:
                pass
        await self.session.delete(image)

    async def create_category(self, data: CategoryCreate) -> Category:
        slug = _slugify(data.name)
        cat = Category(slug=slug, **data.model_dump())
        self.session.add(cat)
        await self.session.flush()
        await self.session.refresh(cat)
        
        # Eagerly load children to prevent serialization errors
        from sqlalchemy.orm import selectinload
        result = await self.session.execute(
            select(Category)
            .options(selectinload(Category.children))
            .where(Category.id == cat.id)
        )
        return result.scalar_one()

    async def update_category(self, category_id: str, data: CategoryUpdate) -> Category:
        cat = await self.session.get(Category, category_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found.")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(cat, key, value)
        await self.session.flush()
        
        # Eagerly load children to prevent serialization errors
        from sqlalchemy.orm import selectinload
        result = await self.session.execute(
            select(Category)
            .options(selectinload(Category.children))
            .where(Category.id == category_id)
        )
        return result.scalar_one()
