"""Shared database helpers for DXEMB services.

This module is intentionally dependency-light:
- async helpers are used by the Discord bot (asyncpg)
- sync health helpers are used by the Flask web app (psycopg2)
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://dxemb:dxemb@db:5432/dxemb",
)

_pool: Any = None


async def get_pool():
    """Return the shared async connection pool, creating it on first use."""
    global _pool
    if _pool is None:
        import asyncpg

        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=10,
        )
    return _pool


async def close_pool() -> None:
    """Close the async pool if initialized."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_sync_health(tables: list[str]) -> dict:
    """Run a sync DB connectivity check and row counts for the provided tables."""
    result = {
        "connected": False,
        "error": None,
        "latency_ms": None,
        "tables": {},
    }

    try:
        import psycopg2
        from psycopg2 import sql

        t0 = time.monotonic()
        with psycopg2.connect(DATABASE_URL, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                for table in tables:
                    cur.execute(
                        sql.SQL("SELECT COUNT(*) FROM {}")
                        .format(sql.Identifier(table))
                    )
                    result["tables"][table] = cur.fetchone()[0]

        result["latency_ms"] = round((time.monotonic() - t0) * 1000)
        result["connected"] = True
    except Exception as exc:
        result["error"] = str(exc)

    return result