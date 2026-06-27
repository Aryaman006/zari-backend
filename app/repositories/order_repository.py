from typing import Optional, Sequence

from sqlalchemy import and_, func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.shipment import Shipment
from app.repositories.base_repository import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: AsyncSession):
        super().__init__(Order, session)

    def _base_query_with_relations(self):
        return select(Order).options(
            selectinload(Order.items).selectinload(OrderItem.variant),
            selectinload(Order.address),
            selectinload(Order.coupon),
            selectinload(Order.payment),
            selectinload(Order.shipment).selectinload(Shipment.provider),
            selectinload(Order.invoice),
            selectinload(Order.user),
        )

    async def get_by_id_with_relations(self, order_id: str) -> Optional[Order]:
        result = await self.session.execute(
            self._base_query_with_relations().where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_user_orders(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Order], int]:
        count_q = select(func.count()).select_from(Order).where(Order.user_id == user_id)
        total = (await self.session.execute(count_q)).scalar_one()

        orders = (
            await self.session.execute(
                self._base_query_with_relations()
                .where(Order.user_id == user_id)
                .order_by(Order.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        return orders, total

    async def list_all_orders(
        self,
        status: Optional[str] = None,
        payment_status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Order], int]:
        from sqlalchemy.orm import joinedload
        from app.models.user import User

        conditions = []
        if status:
            conditions.append(Order.status == status)
        if payment_status:
            conditions.append(Order.payment_status == payment_status)

        base_q = self._base_query_with_relations()
        count_q = select(func.count()).select_from(Order)

        if search:
            base_q = base_q.join(User, Order.user_id == User.id)
            count_q = count_q.join(User, Order.user_id == User.id)
            conditions.append(
                or_(
                    Order.id.ilike(f"%{search}%"),
                    User.first_name.ilike(f"%{search}%"),
                    User.last_name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )

        if conditions:
            base_q = base_q.where(and_(*conditions))
            count_q = count_q.where(and_(*conditions))

        total = (await self.session.execute(count_q)).scalar_one()
        orders = (
            await self.session.execute(
                base_q.order_by(Order.created_at.desc()).limit(limit).offset(offset)
            )
        ).scalars().all()

        return orders, total

    async def get_revenue_by_period(self, days: int = 30) -> float:
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import cast, Date

        since = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.session.execute(
            select(func.sum(Order.total)).where(
                and_(Order.payment_status == "paid", Order.created_at >= since)
            )
        )
        return float(result.scalar_one() or 0)
