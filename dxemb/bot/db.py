# =============================================================
# DXEMB — db.py  (Epic A3)
# Shared async Postgres connection pool.
# Import get_pool() anywhere in the bot that needs DB access.
# Uses asyncpg. Pool is created once on first call (lazy init).
# =============================================================
import os
import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://dxemb:dxemb@db:5432/dxemb",  # matches docker-compose defaults
)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the shared connection pool, creating it if needed."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=10,
        )
    return _pool


async def close_pool() -> None:
    """Gracefully close the pool on shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
