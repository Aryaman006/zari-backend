from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def get_customers(
        self,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[User], int]:
        from sqlalchemy import func, or_

        query = select(User).where(User.role == "customer")
        count_query = select(func.count()).select_from(User).where(User.role == "customer")

        if search:
            pattern = f"%{search}%"
            condition = or_(
                User.email.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            )
            query = query.where(condition)
            count_query = count_query.where(condition)

        total = (await self.session.execute(count_query)).scalar_one()
        users = (
            await self.session.execute(query.limit(limit).offset(offset).order_by(User.created_at.desc()))
        ).scalars().all()

        return users, total

    async def email_exists(self, email: str) -> bool:
        return await self.exists(email=email)
