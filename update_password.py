
import asyncio
from app.core.database import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select
from app.core.security import hash_password

async def update():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "admin@zarijasi.com"))
        user = result.scalars().first()
        if user:
            new_hash = hash_password("Admin@12345")
            user.password_hash = new_hash
            await session.commit()
            print("Password updated!")
            print(f"New hash: {new_hash}")

if __name__ == "__main__":
    asyncio.run(update())
