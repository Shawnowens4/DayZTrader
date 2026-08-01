# =============================================================
# DXEMB — db.py  (Epic A3)
# Shared async Postgres connection pool.
# Import get_pool() anywhere in the bot that needs DB access.
# Uses asyncpg. Pool is created once on first call (lazy init).
# =============================================================
import os
import sys
from pathlib import Path

# Ensure shared package is importable in script mode (python bot/main.py).
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from shared.db import close_pool as shared_close_pool
from shared.db import get_pool as shared_get_pool


async def get_pool():
    """Return the shared connection pool, creating it if needed."""
    return await shared_get_pool()


async def close_pool() -> None:
    """Gracefully close the pool on shutdown."""
    await shared_close_pool()
