from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from shared.db import DATABASE_URL
from shared.db import get_pool

from .models import CatalogItem
from .thumbnails import mapped_thumbnail_url
from .thumbnails import resolve_thumbnail
from .types_xml import parse_types_xml


def import_types_xml_sync(path: str | None = None) -> dict[str, Any]:
    """Import canonical types.xml into item table using sync DB access."""
    items = parse_types_xml(path)
    imported = upsert_items_sync(items)
    return {"source": "types.xml", "parsed": len(items), "upserted": imported}


async def import_types_xml_async(path: str | None = None) -> dict[str, Any]:
    """Import canonical types.xml into item table using async DB access."""
    items = parse_types_xml(path)
    imported = await upsert_items_async(items)
    return {"source": "types.xml", "parsed": len(items), "upserted": imported}


def upsert_items_sync(items: list[CatalogItem]) -> int:
    if not items:
        return 0

    import psycopg2

    statement = """
        INSERT INTO item (
            classname,
            display_name,
            category,
            subcategory,
            is_enabled,
            thumbnail_url,
            notes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (classname)
        DO UPDATE SET
            display_name = COALESCE(EXCLUDED.display_name, item.display_name),
            category = COALESCE(EXCLUDED.category, item.category),
            subcategory = COALESCE(EXCLUDED.subcategory, item.subcategory),
            thumbnail_url = COALESCE(item.thumbnail_url, EXCLUDED.thumbnail_url),
            notes = COALESCE(EXCLUDED.notes, item.notes),
            updated_at = NOW();
    """

    with psycopg2.connect(DATABASE_URL, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(statement, _item_params(item))
    return len(items)


async def upsert_items_async(items: list[CatalogItem]) -> int:
    if not items:
        return 0

    statement = """
        INSERT INTO item (
            classname,
            display_name,
            category,
            subcategory,
            is_enabled,
            thumbnail_url,
            notes
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (classname)
        DO UPDATE SET
            display_name = COALESCE(EXCLUDED.display_name, item.display_name),
            category = COALESCE(EXCLUDED.category, item.category),
            subcategory = COALESCE(EXCLUDED.subcategory, item.subcategory),
            thumbnail_url = COALESCE(item.thumbnail_url, EXCLUDED.thumbnail_url),
            notes = COALESCE(EXCLUDED.notes, item.notes),
            updated_at = NOW();
    """

    pool = await get_pool()
    async with pool.acquire() as conn:
        for item in items:
            await conn.execute(statement, *_item_params(item))
    return len(items)


def search_catalog_sync(
    query: str = "",
    category: str | None = None,
    enabled_only: bool = True,
    limit: int = 25,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Search imported catalog rows for web/admin usage."""
    import psycopg2

    clauses = ["1=1"]
    params: list[Any] = []

    if enabled_only:
        clauses.append("is_enabled = TRUE")

    if category:
        clauses.append("LOWER(category) = LOWER(%s)")
        params.append(category)

    if query.strip():
        pattern = f"%{query.strip()}%"
        clauses.append("(classname ILIKE %s OR COALESCE(display_name, '') ILIKE %s)")
        params.extend([pattern, pattern])

    params.extend([max(1, min(limit, 100)), max(0, offset)])

    statement = f"""
        SELECT
            classname,
            display_name,
            category,
            subcategory,
            buy_price,
            sell_price,
            is_enabled,
            thumbnail_url,
            notes
        FROM item
        WHERE {' AND '.join(clauses)}
        ORDER BY classname ASC
        LIMIT %s OFFSET %s;
    """

    with psycopg2.connect(DATABASE_URL, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(statement, params)
            rows = cur.fetchall()

    out = []
    for row in rows:
        thumb = resolve_thumbnail(row[0], row[7])
        out.append(
            {
            "classname": row[0],
            "display_name": row[1],
            "category": row[2],
            "subcategory": row[3],
            "buy_price": row[4],
            "sell_price": row[5],
            "is_enabled": row[6],
            "thumbnail_url": row[7],
            "resolved_thumbnail_url": thumb["thumbnail_url"],
            "thumbnail_status": thumb["thumbnail_status"],
            "thumbnail_source": thumb["thumbnail_source"],
            "notes": row[8],
        }
        )
    return out


def list_catalog_categories_sync(enabled_only: bool = False) -> list[str]:
    """List available categories for Flask catalog filtering."""
    import psycopg2

    clause = "WHERE category IS NOT NULL"
    if enabled_only:
        clause += " AND is_enabled = TRUE"

    statement = f"""
        SELECT DISTINCT category
        FROM item
        {clause}
        ORDER BY category ASC;
    """

    with psycopg2.connect(DATABASE_URL, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(statement)
            rows = cur.fetchall()

    return [row[0] for row in rows if row[0]]


def get_catalog_item_sync(classname: str) -> dict[str, Any] | None:
    """Get one catalog item by classname for Flask detail pages."""
    import psycopg2

    statement = """
        SELECT
            classname,
            display_name,
            category,
            subcategory,
            buy_price,
            sell_price,
            is_enabled,
            thumbnail_url,
            notes
        FROM item
        WHERE classname = %s
        LIMIT 1;
    """

    with psycopg2.connect(DATABASE_URL, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(statement, (classname,))
            row = cur.fetchone()

    if not row:
        return None

    item = {
        "classname": row[0],
        "display_name": row[1],
        "category": row[2],
        "subcategory": row[3],
        "buy_price": row[4],
        "sell_price": row[5],
        "is_enabled": row[6],
        "thumbnail_url": row[7],
        "notes": row[8],
    }
    thumb = resolve_thumbnail(item["classname"], item["thumbnail_url"])
    item["resolved_thumbnail_url"] = thumb["thumbnail_url"]
    item["thumbnail_status"] = thumb["thumbnail_status"]
    item["thumbnail_source"] = thumb["thumbnail_source"]
    return item


def set_catalog_item_enabled_sync(classname: str, enabled: bool) -> bool:
    """Set item enabled state by classname. Returns True when row was updated."""
    import psycopg2

    statement = """
        UPDATE item
        SET is_enabled = %s,
            updated_at = NOW()
        WHERE classname = %s;
    """

    with psycopg2.connect(DATABASE_URL, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(statement, (enabled, classname))
            updated = cur.rowcount > 0

    return updated


async def search_catalog_async(
    query: str = "",
    category: str | None = None,
    enabled_only: bool = True,
    limit: int = 25,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Search imported catalog rows for Discord usage."""
    clauses = ["1=1"]
    params: list[Any] = []
    idx = 1

    if enabled_only:
        clauses.append("is_enabled = TRUE")

    if category:
        clauses.append(f"LOWER(category) = LOWER(${idx})")
        params.append(category)
        idx += 1

    if query.strip():
        pattern = f"%{query.strip()}%"
        clauses.append(
            f"(classname ILIKE ${idx} OR COALESCE(display_name, '') ILIKE ${idx + 1})"
        )
        params.extend([pattern, pattern])
        idx += 2

    capped_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)

    statement = f"""
        SELECT
            classname,
            display_name,
            category,
            subcategory,
            buy_price,
            sell_price,
            is_enabled,
            thumbnail_url,
            notes
        FROM item
        WHERE {' AND '.join(clauses)}
        ORDER BY classname ASC
        LIMIT ${idx} OFFSET ${idx + 1};
    """

    params.extend([capped_limit, safe_offset])

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(statement, *params)

    out = []
    for row in rows:
        item = dict(row)
        thumb = resolve_thumbnail(item["classname"], item["thumbnail_url"])
        item["resolved_thumbnail_url"] = thumb["thumbnail_url"]
        item["thumbnail_status"] = thumb["thumbnail_status"]
        item["thumbnail_source"] = thumb["thumbnail_source"]
        out.append(item)
    return out


async def list_catalog_categories_async(enabled_only: bool = True) -> list[str]:
    """List available item categories for Discord browse flow."""
    clause = "WHERE category IS NOT NULL"
    if enabled_only:
        clause += " AND is_enabled = TRUE"

    statement = f"""
        SELECT DISTINCT category
        FROM item
        {clause}
        ORDER BY category ASC;
    """

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(statement)

    return [row["category"] for row in rows if row["category"]]


async def get_catalog_item_async(classname: str) -> dict[str, Any] | None:
    """Get one catalog item by classname for detail views."""
    statement = """
        SELECT
            classname,
            display_name,
            category,
            subcategory,
            buy_price,
            sell_price,
            is_enabled,
            thumbnail_url,
            notes
        FROM item
        WHERE classname = $1
        LIMIT 1;
    """

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(statement, classname)

    if not row:
        return None

    item = dict(row)
    thumb = resolve_thumbnail(item["classname"], item["thumbnail_url"])
    item["resolved_thumbnail_url"] = thumb["thumbnail_url"]
    item["thumbnail_status"] = thumb["thumbnail_status"]
    item["thumbnail_source"] = thumb["thumbnail_source"]
    return item


def _item_params(item: CatalogItem) -> tuple[Any, ...]:
    normalized = asdict(item)
    metadata = {
        "source": "types.xml",
        "nominal": normalized["nominal"],
        "lifetime": normalized["lifetime"],
        "restock": normalized["restock"],
        "min_count": normalized["min_count"],
        "quant_min": normalized["quant_min"],
        "quant_max": normalized["quant_max"],
        "cost": normalized["cost"],
    }

    return (
        item.classname,
        item.display_name,
        item.category,
        item.subcategory,
        item.is_enabled,
        mapped_thumbnail_url(item.classname),
        json.dumps(metadata, separators=(",", ":")),
    )
