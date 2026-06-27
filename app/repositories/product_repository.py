from typing import Optional, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.product_image import ProductImage
from app.repositories.base_repository import BaseRepository


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: AsyncSession):
        super().__init__(Product, session)

    def _base_query_with_relations(self):
        return select(Product).options(
            selectinload(Product.images),
            selectinload(Product.variants),
            selectinload(Product.category),
        )

    async def get_by_slug(self, slug: str) -> Optional[Product]:
        result = await self.session.execute(
            self._base_query_with_relations().where(Product.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, product_id: str) -> Optional[Product]:
        result = await self.session.execute(
            self._base_query_with_relations().where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def list_products(
        self,
        category_id: Optional[str] = None,
        search: Optional[str] = None,
        is_featured: Optional[bool] = None,
        is_active: Optional[bool] = True,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Product], int]:
        conditions = []

        if is_active is not None:
            conditions.append(Product.is_active == is_active)
        if category_id:
            conditions.append(Product.category_id == category_id)
        if is_featured is not None:
            conditions.append(Product.is_featured == is_featured)
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    Product.name.ilike(pattern),
                    Product.description.ilike(pattern),
                    Product.short_description.ilike(pattern),
                )
            )
        if min_price is not None:
            conditions.append(Product.base_price >= min_price)
        if max_price is not None:
            conditions.append(Product.base_price <= max_price)

        # Build sort
        sort_col = getattr(Product, sort_by, Product.created_at)
        sort_expr = sort_col.desc() if sort_order == "desc" else sort_col.asc()

        count_q = select(func.count()).select_from(Product)
        base_q = self._base_query_with_relations()

        if conditions:
            count_q = count_q.where(and_(*conditions))
            base_q = base_q.where(and_(*conditions))

        total = (await self.session.execute(count_q)).scalar_one()
        products = (
            await self.session.execute(base_q.order_by(sort_expr).limit(limit).offset(offset))
        ).scalars().all()

        return products, total

    async def slug_exists(self, slug: str, exclude_id: Optional[str] = None) -> bool:
        q = select(func.count()).select_from(Product).where(Product.slug == slug)
        if exclude_id:
            q = q.where(Product.id != exclude_id)
        return (await self.session.execute(q)).scalar_one() > 0
