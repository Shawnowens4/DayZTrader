from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from dataclasses import asdict
from typing import Any

from shared.db import DATABASE_URL
from shared.db import get_pool

from .models import CatalogItem
from .thumbnails import mapped_thumbnail_url
from .thumbnails import resolve_thumbnail
from .types_xml import parse_types_xml_for_import
from .types_xml import parse_types_xml


def import_types_xml_sync(path: str | None = None) -> dict[str, Any]:
    """Backward-compatible apply import wrapper."""
    report = import_types_xml_foundation_sync(path=path, dry_run=False)
    return {
        "source": report["source_basename"],
        "parsed": report["parsed"],
        "upserted": report["created"] + report["updated"],
    }


async def import_types_xml_async(path: str | None = None) -> dict[str, Any]:
    """Backward-compatible async apply import wrapper."""
    report = await import_types_xml_foundation_async(path=path, dry_run=False)
    return {
        "source": report["source_basename"],
        "parsed": report["parsed"],
        "upserted": report["created"] + report["updated"],
    }


def import_types_xml_foundation_sync(path: str | None = None, dry_run: bool = True) -> dict[str, Any]:
    """Import DayZ types.xml with explicit source provenance and safe field ownership."""
    parsed = parse_types_xml_for_import(path)
    records = parsed["records"]
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_label = "types.xml:local"

    import psycopg2

    report = {
        "mode": "dry-run" if dry_run else "apply",
        "source_basename": parsed["source_basename"],
        "source_sha256": parsed["source_sha256"],
        "source_label": source_label,
        "parsed": parsed["record_count"],
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "malformed": parsed["malformed_count"],
        "review_required": 0,
        "errors": [],
    }

    existing_by_classname: dict[str, dict[str, Any]] = {}
    with psycopg2.connect(DATABASE_URL, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
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
                """
            )
            for row in cur.fetchall():
                existing_by_classname[row[0]] = {
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

        plans = []
        seen: set[str] = set()
        for record in records:
            if record.classname in seen:
                report["skipped"] += 1
                report["errors"].append(f"duplicate_classname:{record.classname}")
                continue
            seen.add(record.classname)

            existing = existing_by_classname.get(record.classname)
            plan = _build_item_import_plan(
                record=record,
                existing=existing,
                source_sha256=parsed["source_sha256"],
                source_basename=parsed["source_basename"],
                source_label=source_label,
                imported_at_utc=now_iso,
            )

            plans.append(plan)
            if plan["review_required"]:
                report["review_required"] += 1

            if plan["action"] == "create":
                report["created"] += 1
            elif plan["action"] == "update":
                report["updated"] += 1
            else:
                report["unchanged"] += 1

        if dry_run:
            return report

        statement = """
            INSERT INTO item (
                classname,
                display_name,
                category,
                subcategory,
                buy_price,
                sell_price,
                is_enabled,
                thumbnail_url,
                notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (classname)
            DO UPDATE SET
                display_name = EXCLUDED.display_name,
                category = EXCLUDED.category,
                subcategory = EXCLUDED.subcategory,
                buy_price = item.buy_price,
                sell_price = item.sell_price,
                is_enabled = item.is_enabled,
                thumbnail_url = item.thumbnail_url,
                notes = EXCLUDED.notes,
                updated_at = NOW();
        """

        with conn.cursor() as cur:
            for plan in plans:
                if plan["action"] == "unchanged":
                    continue
                cur.execute(statement, plan["params"])

    return report


async def import_types_xml_foundation_async(path: str | None = None, dry_run: bool = True) -> dict[str, Any]:
    """Async variant for the same types.xml import behavior contract."""
    parsed = parse_types_xml_for_import(path)
    records = parsed["records"]
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_label = "types.xml:local"

    report = {
        "mode": "dry-run" if dry_run else "apply",
        "source_basename": parsed["source_basename"],
        "source_sha256": parsed["source_sha256"],
        "source_label": source_label,
        "parsed": parsed["record_count"],
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "malformed": parsed["malformed_count"],
        "review_required": 0,
        "errors": [],
    }

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
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
            """
        )

        existing_by_classname: dict[str, dict[str, Any]] = {}
        for row in rows:
            existing_by_classname[row["classname"]] = dict(row)

        plans = []
        seen: set[str] = set()
        for record in records:
            if record.classname in seen:
                report["skipped"] += 1
                report["errors"].append(f"duplicate_classname:{record.classname}")
                continue
            seen.add(record.classname)

            existing = existing_by_classname.get(record.classname)
            plan = _build_item_import_plan(
                record=record,
                existing=existing,
                source_sha256=parsed["source_sha256"],
                source_basename=parsed["source_basename"],
                source_label=source_label,
                imported_at_utc=now_iso,
            )
            plans.append(plan)

            if plan["review_required"]:
                report["review_required"] += 1

            if plan["action"] == "create":
                report["created"] += 1
            elif plan["action"] == "update":
                report["updated"] += 1
            else:
                report["unchanged"] += 1

        if dry_run:
            return report

        statement = """
            INSERT INTO item (
                classname,
                display_name,
                category,
                subcategory,
                buy_price,
                sell_price,
                is_enabled,
                thumbnail_url,
                notes
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (classname)
            DO UPDATE SET
                display_name = EXCLUDED.display_name,
                category = EXCLUDED.category,
                subcategory = EXCLUDED.subcategory,
                buy_price = item.buy_price,
                sell_price = item.sell_price,
                is_enabled = item.is_enabled,
                thumbnail_url = item.thumbnail_url,
                notes = EXCLUDED.notes,
                updated_at = NOW();
        """

        for plan in plans:
            if plan["action"] == "unchanged":
                continue
            await conn.execute(statement, *plan["params"])

    return report


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


def _build_item_import_plan(
    *,
    record: Any,
    existing: dict[str, Any] | None,
    source_sha256: str,
    source_basename: str,
    source_label: str,
    imported_at_utc: str,
) -> dict[str, Any]:
    existing_notes = _safe_notes_dict(existing.get("notes") if existing else None)
    merged_notes = _merge_import_notes(
        existing_notes,
        record=record,
        source_sha256=source_sha256,
        source_basename=source_basename,
        source_label=source_label,
        imported_at_utc=imported_at_utc,
    )

    import_display_name = record.display_name
    import_category = record.category
    import_subcategory = record.subcategory
    import_thumbnail = mapped_thumbnail_url(record.classname)

    if existing is None:
        is_enabled = False
        buy_price = None
        sell_price = None
        action = "create"
    else:
        is_enabled = bool(existing.get("is_enabled", False))
        buy_price = existing.get("buy_price")
        sell_price = existing.get("sell_price")
        existing_notes_normalized = _safe_notes_dict(existing.get("notes"))

        changed = any(
            [
                existing.get("display_name") != import_display_name,
                existing.get("category") != import_category,
                existing.get("subcategory") != import_subcategory,
                _notes_json(existing_notes_normalized) != _notes_json(merged_notes),
            ]
        )
        action = "update" if changed else "unchanged"

    review_required = (existing is None) or bool(record.malformed_fields)

    params = (
        record.classname,
        import_display_name,
        import_category,
        import_subcategory,
        buy_price,
        sell_price,
        is_enabled,
        existing.get("thumbnail_url") if existing and existing.get("thumbnail_url") else import_thumbnail,
        _notes_json(merged_notes),
    )

    return {
        "action": action,
        "review_required": review_required,
        "params": params,
    }


def _safe_notes_dict(raw_notes: Any) -> dict[str, Any]:
    if raw_notes is None:
        return {}

    if isinstance(raw_notes, dict):
        return dict(raw_notes)

    if isinstance(raw_notes, str):
        candidate = raw_notes.strip()
        if not candidate:
            return {}
        try:
            decoded = json.loads(candidate)
            if isinstance(decoded, dict):
                return decoded
        except json.JSONDecodeError:
            return {"_legacy_notes": raw_notes}

    return {}


def _merge_import_notes(
    existing_notes: dict[str, Any],
    *,
    record: Any,
    source_sha256: str,
    source_basename: str,
    source_label: str,
    imported_at_utc: str,
) -> dict[str, Any]:
    merged = dict(existing_notes)
    new_import = {
        "source_label": source_label,
        "source_basename": source_basename,
        "source_sha256": source_sha256,
        "imported_at_utc": imported_at_utc,
        "evidence_locator": record.evidence_locator,
        "review_required": bool(record.malformed_fields),
        "malformed_fields": list(record.malformed_fields),
        "types_xml": {
            "nominal": record.nominal,
            "lifetime": record.lifetime,
            "restock": record.restock,
            "min": record.min_count,
            "quantmin": record.quant_min,
            "quantmax": record.quant_max,
            "cost": record.cost,
            "categories": list(record.categories),
            "usages": list(record.usages),
            "values": list(record.values),
            "flags": dict(record.flags),
        },
    }

    existing_import = existing_notes.get("import") if isinstance(existing_notes.get("import"), dict) else None
    if isinstance(existing_import, dict):
        same_evidence = (
            existing_import.get("source_label") == source_label
            and existing_import.get("source_basename") == source_basename
            and existing_import.get("source_sha256") == source_sha256
            and existing_import.get("evidence_locator") == record.evidence_locator
            and bool(existing_import.get("review_required")) == bool(record.malformed_fields)
            and existing_import.get("malformed_fields") == list(record.malformed_fields)
            and existing_import.get("types_xml") == new_import["types_xml"]
        )
        if same_evidence and isinstance(existing_import.get("imported_at_utc"), str):
            new_import["imported_at_utc"] = existing_import["imported_at_utc"]

    merged["import"] = new_import
    return merged


def _notes_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)
