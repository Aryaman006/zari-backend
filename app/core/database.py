from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, MappedColumn
from sqlalchemy import MetaData
import uuid

from app.core.config import settings

# ── Naming Convention for Alembic ─────────────────────────────────────────────
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)

# ── Async Engine ──────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_recycle=1800,           # Recycle connections older than 30 minutes
    pool_timeout=30,             # Max seconds to wait for a connection from the pool
    pool_pre_ping=True,          # Test connection health before using it
    pool_use_lifo=True,          # Reuse the most recently returned connection first
    connect_args={
        "prepared_statement_cache_size": 0,  # Required for PgBouncer transaction mode
        "statement_cache_size": 0,           # Required for PgBouncer transaction mode
    },
    echo=settings.DATABASE_ECHO,
)

# ── Async Session Factory ─────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Base Model ────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    metadata = metadata


# ── DB Dependency ─────────────────────────────────────────────────────────────
async def get_db():
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
