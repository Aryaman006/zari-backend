import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Load .env for DATABASE_URL ────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed; fall back to reading .env manually
    _env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.isfile(_env_file):
        with open(_env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# ── Alembic Config ────────────────────────────────────────────────────────────
config = context.config

# NOTE: The DATABASE_URL may contain % characters (URL-encoded password characters
# like %40 for @). ConfigParser interprets % as interpolation syntax, so we must
# NOT pass the raw URL through set_main_option(). Instead, we override the URL
# directly in the engine configuration in run_async_migrations() below.
# Prefer DATABASE_DIRECT_URL for Alembic migrations.
# For Supabase: the direct URL (port 5432) bypasses PgBouncer and is
# required for DDL operations. If not set, falls back to DATABASE_URL.
_db_url = (
    os.environ.get("DATABASE_DIRECT_URL")
    or os.environ.get("DATABASE_URL")
    or "postgresql+asyncpg://postgres:postgres@localhost:5432/zari_db"
)

# Only set via config if there are no % characters (to avoid ConfigParser issues)
if "%" not in _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import all models so Alembic can detect them ──────────────────────────────
from app.core.database import Base
import app.models  # noqa: F401 — triggers all model imports

target_metadata = Base.metadata


# ── Offline Mode ──────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    context.configure(
        url=_db_url,  # Use the raw URL directly, bypassing ConfigParser
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online Mode ───────────────────────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Create the async engine directly from the DATABASE_URL environment variable,
    bypassing alembic.ini ConfigParser to avoid % interpolation issues.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_db_url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
