"""Drop all tables and reset the DB to re-run migrations cleanly."""
import asyncio
import asyncpg


async def reset():
    conn = await asyncpg.connect(
        "postgresql://postgres:6289379872%40As@localhost:5432/zari"
    )
    try:
        # Drop all tables via cascade
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        print("All tables dropped — schema reset.")
    finally:
        await conn.close()


asyncio.run(reset())
