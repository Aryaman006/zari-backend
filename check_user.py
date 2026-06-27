
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select
from app.core.security import verify_password

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        print("Users found:")
        for user in users:
            print(f"\n  ID: {user.id}")
            print(f"  Email: {user.email}")
            print(f"  Role: {user.role}")
            print(f"  Is active: {user.is_active}")
            print(f"  Is verified: {user.is_verified}")
            print(f"  Full hash: {user.password_hash}")
            print(f"  Verify 'Admin@12345': {verify_password('Admin@12345', user.password_hash)}")

if __name__ == "__main__":
    asyncio.run(check())
