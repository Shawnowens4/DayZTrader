from __future__ import annotations

import json
import os
from datetime import UTC
from datetime import datetime
from dataclasses import asdict
from pathlib import Path
from typing import Any

from shared.db import DATABASE_URL
from shared.db import get_pool

from .models import CatalogItem
from .thumbnails import _local_asset_url
from .thumbnails import mapped_thumbnail_url
from .thumbnails import resolve_thumbnail
from .types_xml import parse_types_xml_for_import
from .types_xml import parse_types_xml

ADMIN_FUTURE_FLAG_KEYS = {
    "auto_trader_candidate": "Auto Trader candidate",
    "direct_purchase_candidate": "Direct-purchase candidate",
    "rental_candidate": "Rental candidate",
    "bundle_candidate": "Bundle/bag candidate",
    "horde_event_candidate": "Horde/event candidate",
}

CATALOG_ADMIN_DEFAULT_LIMIT = 25
CATALOG_ADMIN_MAX_LIMIT = 50

_WEB_STATIC_ROOT = Path(__file__).resolve().parents[2] / "web" / "static"


def _catalog_database_url() -> str:
    return os.getenv("DATABASE_URL", DATABASE_URL)


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
    with psycopg2.connect(_catalog_database_url(), connect_timeout=5) as conn:
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

    with psycopg2.connect(_catalog_database_url(), connect_timeout=5) as conn:
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

    with psycopg2.connect(_catalog_database_url(), connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(statement, params)
            rows = cur.fetchall()

    out = []
    for row in rows:
        out.append(_expand_catalog_row(_row_to_item_dict(row)))
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

    with psycopg2.connect(_catalog_database_url(), connect_timeout=5) as conn:
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

    with psycopg2.connect(_catalog_database_url(), connect_timeout=5) as conn:
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
    return _expand_catalog_row(item)


def set_catalog_item_enabled_sync(classname: str, enabled: bool) -> bool:
    """Set item enabled state by classname. Returns True when row was updated."""
    import psycopg2

    statement = """
        UPDATE item
        SET is_enabled = %s,
            updated_at = NOW()
        WHERE classname = %s;
    """

    with psycopg2.connect(_catalog_database_url(), connect_timeout=5) as conn:
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
        out.append(_expand_catalog_row(dict(row)))
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

    return _expand_catalog_row(dict(row))


def search_catalog_admin_sync(
    *,
    query: str = "",
    imported_state: str = "all",
    review_state: str = "all",
    enabled_state: str = "all",
    image_state: str = "all",
    warning_state: str = "all",
    imported_category: str = "",
    imported_usage: str = "",
    auto_trader_candidate: str = "all",
    direct_purchase_candidate: str = "all",
    rental_candidate: str = "all",
    bundle_candidate: str = "all",
    horde_event_candidate: str = "all",
    page: int = 1,
    limit: int = CATALOG_ADMIN_DEFAULT_LIMIT,
) -> dict[str, Any]:
    rows = _fetch_all_catalog_rows_sync()
    expanded = [_expand_catalog_row(row) for row in rows]

    filters = {
        "query": query.strip(),
        "imported_state": imported_state,
        "review_state": review_state,
        "enabled_state": enabled_state,
        "image_state": image_state,
        "warning_state": warning_state,
        "imported_category": imported_category.strip(),
        "imported_usage": imported_usage.strip(),
        "auto_trader_candidate": auto_trader_candidate,
        "direct_purchase_candidate": direct_purchase_candidate,
        "rental_candidate": rental_candidate,
        "bundle_candidate": bundle_candidate,
        "horde_event_candidate": horde_event_candidate,
    }

    filtered = _filter_catalog_admin_rows(expanded, filters)
    safe_limit = max(1, min(limit, CATALOG_ADMIN_MAX_LIMIT))
    safe_page = max(1, page)
    start = (safe_page - 1) * safe_limit
    end = start + safe_limit
    visible = filtered[start:end]

    return {
        "items": visible,
        "page": safe_page,
        "limit": safe_limit,
        "total_count": len(filtered),
        "has_next": end < len(filtered),
        "filters": filters,
        "available_imported_categories": sorted({row["primary_imported_category"] for row in expanded if row["primary_imported_category"]}),
        "available_imported_usages": sorted({usage for row in expanded for usage in row["imported_usages"] if usage}),
    }


def get_catalog_admin_item_sync(classname: str) -> dict[str, Any] | None:
    item = get_catalog_item_sync(classname)
    if item is None:
        return None
    return item


def update_catalog_admin_item_sync(
    classname: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    existing = _get_catalog_row_by_classname_sync(classname)
    if existing is None:
        return {"ok": False, "status_code": 404, "errors": ["catalog item not found"]}

    item = _expand_catalog_row(existing)
    errors: list[str] = []

    display_name = _normalized_optional_text(payload.get("display_name"))
    category = _normalized_optional_text(payload.get("curated_category"))
    subcategory = _normalized_optional_text(payload.get("curated_subcategory"))
    buy_price = _parse_optional_non_negative_int(payload.get("buy_price"), "buy price", errors)
    sell_price = _parse_optional_non_negative_int(payload.get("sell_price"), "sell price", errors)
    review_required = _parse_bool_field(payload.get("review_required"), "review required", errors)
    catalog_enabled = _parse_bool_field(payload.get("catalog_enabled"), "catalog enabled", errors)
    thumbnail_override = _normalized_optional_text(payload.get("thumbnail_override"))
    note_append = _normalized_optional_text(payload.get("admin_note_append"))

    future_flags = {
        key: _parse_bool_field(payload.get(key), ADMIN_FUTURE_FLAG_KEYS[key], errors)
        for key in ADMIN_FUTURE_FLAG_KEYS
    }

    resolved_thumbnail_override = None
    if thumbnail_override:
        resolved_thumbnail_override = _validate_local_thumbnail_override(thumbnail_override, errors)

    if buy_price is not None and sell_price is not None and sell_price > buy_price:
        errors.append("sell price cannot exceed buy price")

    if errors:
        failed = dict(item)
        failed["form_values"] = {
            "display_name": display_name or "",
            "curated_category": category or "",
            "curated_subcategory": subcategory or "",
            "buy_price": "" if buy_price is None else str(buy_price),
            "sell_price": "" if sell_price is None else str(sell_price),
            "thumbnail_override": thumbnail_override or "",
            "review_required": review_required,
            "catalog_enabled": catalog_enabled,
            "admin_note_append": note_append or "",
            **future_flags,
        }
        return {"ok": False, "status_code": 400, "errors": errors, "item": failed}

    notes = _safe_notes_dict(existing.get("notes"))
    manual = _safe_manual_dict(notes)
    manual["display_name"] = display_name
    manual["category"] = category
    manual["subcategory"] = subcategory
    manual["review_required"] = review_required
    manual["thumbnail_override"] = resolved_thumbnail_override
    manual["future_flags"] = future_flags
    manual["last_saved_at_utc"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    if note_append:
        notes_list = _normalized_admin_notes_list(manual.get("admin_notes"))
        notes_list.append(
            {
                "created_at_utc": manual["last_saved_at_utc"],
                "note": note_append,
            }
        )
        manual["admin_notes"] = notes_list

    manual["last_change_note"] = (
        f"Saved local admin curation fields at {manual['last_saved_at_utc']}"
    )

    notes["manual"] = manual

    import psycopg2

    statement = """
        UPDATE item
        SET buy_price = %s,
            sell_price = %s,
            is_enabled = %s,
            notes = %s,
            updated_at = NOW()
        WHERE classname = %s;
    """

    with psycopg2.connect(_catalog_database_url(), connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                statement,
                (
                    buy_price,
                    sell_price,
                    catalog_enabled,
                    _notes_json(notes),
                    classname,
                ),
            )

    updated = get_catalog_admin_item_sync(classname)
    return {"ok": True, "status_code": 200, "item": updated}


def bulk_set_catalog_review_required_sync(
    *,
    desired_review_required: bool,
    confirmation: str,
    filters: dict[str, Any],
    selected_classnames: list[str],
    apply_to_filtered: bool,
) -> dict[str, Any]:
    workspace = search_catalog_admin_sync(
        query=str(filters.get("query", "")),
        imported_state=str(filters.get("imported_state", "all")),
        review_state=str(filters.get("review_state", "all")),
        enabled_state=str(filters.get("enabled_state", "all")),
        image_state=str(filters.get("image_state", "all")),
        warning_state=str(filters.get("warning_state", "all")),
        imported_category=str(filters.get("imported_category", "")),
        imported_usage=str(filters.get("imported_usage", "")),
        auto_trader_candidate=str(filters.get("auto_trader_candidate", "all")),
        direct_purchase_candidate=str(filters.get("direct_purchase_candidate", "all")),
        rental_candidate=str(filters.get("rental_candidate", "all")),
        bundle_candidate=str(filters.get("bundle_candidate", "all")),
        horde_event_candidate=str(filters.get("horde_event_candidate", "all")),
        page=1,
        limit=CATALOG_ADMIN_MAX_LIMIT,
    )

    filtered_rows = workspace["items"] if workspace["total_count"] <= CATALOG_ADMIN_MAX_LIMIT else _filter_catalog_admin_rows(
        [_expand_catalog_row(row) for row in _fetch_all_catalog_rows_sync()],
        workspace["filters"],
    )

    if apply_to_filtered:
        active_filter_values = [
            str(filters.get("query", "")).strip(),
            str(filters.get("imported_state", "all")),
            str(filters.get("review_state", "all")),
            str(filters.get("enabled_state", "all")),
            str(filters.get("image_state", "all")),
            str(filters.get("warning_state", "all")),
            str(filters.get("imported_category", "")).strip(),
            str(filters.get("imported_usage", "")).strip(),
            str(filters.get("auto_trader_candidate", "all")),
            str(filters.get("direct_purchase_candidate", "all")),
            str(filters.get("rental_candidate", "all")),
            str(filters.get("bundle_candidate", "all")),
            str(filters.get("horde_event_candidate", "all")),
        ]
        if all(value in {"", "all"} for value in active_filter_values):
            return {"ok": False, "status_code": 400, "errors": ["bulk review updates require at least one active filter or explicit selections"]}
        target_rows = filtered_rows
    else:
        selected = {value.strip() for value in selected_classnames if value.strip()}
        if not selected:
            return {"ok": False, "status_code": 400, "errors": ["bulk review updates require explicit selected classnames or apply-to-filtered"]}
        target_rows = [row for row in filtered_rows if row["classname"] in selected]
        if len(target_rows) != len(selected):
            return {"ok": False, "status_code": 400, "errors": ["selected classnames must match the current filtered result set"]}

    affected_count = len(target_rows)
    if affected_count <= 0:
        return {"ok": False, "status_code": 400, "errors": ["no catalog items matched this bulk request"]}

    expected = f"{'ENABLE' if desired_review_required else 'DISABLE'} {affected_count}"
    if confirmation.strip() != expected:
        return {"ok": False, "status_code": 400, "errors": [f"confirmation token must exactly match {expected}"]}

    import psycopg2

    with psycopg2.connect(_catalog_database_url(), connect_timeout=5) as conn:
        with conn.cursor() as cur:
            for row in target_rows:
                notes = _safe_notes_dict(row.get("notes"))
                manual = _safe_manual_dict(notes)
                manual["review_required"] = desired_review_required
                manual["last_saved_at_utc"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
                manual["last_change_note"] = (
                    f"Bulk review state set to {'required' if desired_review_required else 'not required'} at {manual['last_saved_at_utc']}"
                )
                notes["manual"] = manual
                cur.execute(
                    """
                    UPDATE item
                    SET notes = %s,
                        updated_at = NOW()
                    WHERE classname = %s
                    """,
                    (_notes_json(notes), row["classname"]),
                )

    return {
        "ok": True,
        "status_code": 200,
        "affected_count": affected_count,
        "resulting_review_required": desired_review_required,
    }


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
        "display_name": record.display_name,
        "category": record.category,
        "subcategory": record.subcategory,
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


def _fetch_all_catalog_rows_sync() -> list[dict[str, Any]]:
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
        ORDER BY classname ASC;
    """

    with psycopg2.connect(_catalog_database_url(), connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(statement)
            rows = cur.fetchall()

    return [_row_to_item_dict(row) for row in rows]


def _get_catalog_row_by_classname_sync(classname: str) -> dict[str, Any] | None:
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

    with psycopg2.connect(_catalog_database_url(), connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(statement, (classname,))
            row = cur.fetchone()

    return _row_to_item_dict(row) if row else None


def _row_to_item_dict(row: Any) -> dict[str, Any]:
    return {
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


def _expand_catalog_row(item: dict[str, Any]) -> dict[str, Any]:
    expanded = dict(item)
    notes = _safe_notes_dict(item.get("notes"))
    import_meta = notes.get("import") if isinstance(notes.get("import"), dict) else {}
    manual = _safe_manual_dict(notes)
    imported_types = import_meta.get("types_xml") if isinstance(import_meta.get("types_xml"), dict) else {}
    future_flags = _normalized_future_flags(manual.get("future_flags"))

    effective_display_name = _normalized_optional_text(manual.get("display_name")) or item.get("display_name")
    effective_category = _normalized_optional_text(manual.get("category")) or item.get("category")
    effective_subcategory = _normalized_optional_text(manual.get("subcategory")) or item.get("subcategory")
    review_required = (
        bool(manual.get("review_required"))
        if "review_required" in manual
        else bool(import_meta)
    )

    effective_thumbnail_input = _normalized_optional_text(manual.get("thumbnail_override")) or item.get("thumbnail_url")
    thumb = resolve_thumbnail(item["classname"], effective_thumbnail_input)
    image_state = _classify_image_state(item.get("thumbnail_url"), manual.get("thumbnail_override"), thumb)

    expanded["display_name"] = effective_display_name
    expanded["category"] = effective_category
    expanded["subcategory"] = effective_subcategory
    expanded["resolved_thumbnail_url"] = thumb["thumbnail_url"]
    expanded["thumbnail_status"] = thumb["thumbnail_status"]
    expanded["thumbnail_source"] = thumb["thumbnail_source"]
    expanded["notes"] = notes
    expanded["import_meta"] = import_meta
    expanded["manual_meta"] = manual
    expanded["imported_categories"] = _safe_string_list(imported_types.get("categories"))
    expanded["imported_usages"] = _safe_string_list(imported_types.get("usages"))
    expanded["imported_values"] = _safe_string_list(imported_types.get("values"))
    expanded["imported_flags"] = imported_types.get("flags") if isinstance(imported_types.get("flags"), dict) else {}
    expanded["imported_numeric_values"] = {
        "nominal": imported_types.get("nominal"),
        "lifetime": imported_types.get("lifetime"),
        "restock": imported_types.get("restock"),
        "min": imported_types.get("min"),
        "quantmin": imported_types.get("quantmin"),
        "quantmax": imported_types.get("quantmax"),
        "cost": imported_types.get("cost"),
    }
    expanded["source_basename"] = import_meta.get("source_basename")
    expanded["source_sha256"] = import_meta.get("source_sha256")
    expanded["source_label"] = import_meta.get("source_label")
    expanded["imported_at_utc"] = import_meta.get("imported_at_utc")
    expanded["evidence_locator"] = import_meta.get("evidence_locator")
    expanded["malformed_fields"] = _safe_string_list(import_meta.get("malformed_fields"))
    expanded["has_source_warning"] = bool(expanded["malformed_fields"])
    expanded["review_required"] = review_required
    expanded["is_imported"] = bool(import_meta)
    expanded["image_state"] = image_state
    expanded["future_flags"] = future_flags
    expanded["admin_notes"] = _normalized_admin_notes_list(manual.get("admin_notes"))
    expanded["last_change_note"] = manual.get("last_change_note") if isinstance(manual.get("last_change_note"), str) else None
    expanded["manual_thumbnail_override"] = _normalized_optional_text(manual.get("thumbnail_override"))
    expanded["primary_imported_category"] = expanded["imported_categories"][0] if expanded["imported_categories"] else ""
    expanded["primary_imported_usage"] = expanded["imported_usages"][0] if expanded["imported_usages"] else ""
    expanded["is_curated"] = _is_curated_row(expanded)
    return expanded


def _filter_catalog_admin_rows(rows: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    query = str(filters.get("query", "")).strip().lower()
    imported_state = str(filters.get("imported_state", "all")).strip().lower()
    review_state = str(filters.get("review_state", "all")).strip().lower()
    enabled_state = str(filters.get("enabled_state", "all")).strip().lower()
    image_state = str(filters.get("image_state", "all")).strip().lower()
    warning_state = str(filters.get("warning_state", "all")).strip().lower()
    imported_category = str(filters.get("imported_category", "")).strip().lower()
    imported_usage = str(filters.get("imported_usage", "")).strip().lower()

    flag_filters = {
        key: str(filters.get(key, "all")).strip().lower()
        for key in ADMIN_FUTURE_FLAG_KEYS
    }

    out: list[dict[str, Any]] = []
    for row in rows:
        if query:
            display_name = str(row.get("display_name") or "").lower()
            if query not in row["classname"].lower() and query not in display_name:
                continue

        if imported_state == "imported" and not row["is_imported"]:
            continue
        if imported_state == "legacy_or_unknown" and row["is_imported"]:
            continue

        if review_state == "yes" and not row["review_required"]:
            continue
        if review_state == "no" and row["review_required"]:
            continue

        if enabled_state == "enabled" and not row["is_enabled"]:
            continue
        if enabled_state == "disabled" and row["is_enabled"]:
            continue

        if image_state != "all" and row["image_state"] != image_state:
            continue

        if warning_state == "yes" and not row["has_source_warning"]:
            continue
        if warning_state == "no" and row["has_source_warning"]:
            continue

        if imported_category and imported_category not in {value.lower() for value in row["imported_categories"]}:
            continue
        if imported_usage and imported_usage not in {value.lower() for value in row["imported_usages"]}:
            continue

        flag_mismatch = False
        for key, mode in flag_filters.items():
            value = bool(row["future_flags"].get(key))
            if mode == "yes" and not value:
                flag_mismatch = True
                break
            if mode == "no" and value:
                flag_mismatch = True
                break
        if flag_mismatch:
            continue

        out.append(row)

    return out


def _normalized_future_flags(raw: Any) -> dict[str, bool]:
    out = {key: False for key in ADMIN_FUTURE_FLAG_KEYS}
    if not isinstance(raw, dict):
        return out
    for key in out:
        out[key] = bool(raw.get(key, False))
    return out


def _safe_manual_dict(notes: dict[str, Any]) -> dict[str, Any]:
    manual = notes.get("manual") if isinstance(notes.get("manual"), dict) else {}
    return dict(manual)


def _safe_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(value).strip() for value in raw if str(value).strip()]


def _normalized_admin_notes_list(raw: Any) -> list[dict[str, str]]:
    if isinstance(raw, list):
        out: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            note = str(item.get("note") or "").strip()
            if not note:
                continue
            out.append(
                {
                    "created_at_utc": str(item.get("created_at_utc") or "").strip(),
                    "note": note,
                }
            )
        return out
    if isinstance(raw, str) and raw.strip():
        return [{"created_at_utc": "", "note": raw.strip()}]
    return []


def _normalized_optional_text(raw: Any) -> str | None:
    value = str(raw or "").strip()
    return value or None


def _parse_optional_non_negative_int(raw: Any, field_label: str, errors: list[str]) -> int | None:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        errors.append(f"{field_label} must be a whole number")
        return None
    if parsed < 0:
        errors.append(f"{field_label} must be zero or greater")
        return None
    return parsed


def _coerce_bool(raw: Any) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_bool_field(raw: Any, field_label: str, errors: list[str]) -> bool:
    normalized = str(raw or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    errors.append(f"{field_label} must be a boolean form value")
    return False


def _validate_local_thumbnail_override(raw: str, errors: list[str]) -> str | None:
    candidate = raw.strip()
    lowered = candidate.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        errors.append("thumbnail override must be a local-only asset reference")
        return None

    local_url = _local_asset_url(candidate)
    if not local_url:
        errors.append("thumbnail override must resolve to an existing local asset under web/static/catalog_items or web/static/items")
        return None

    static_path = _WEB_STATIC_ROOT / local_url.removeprefix("/static/")
    if not static_path.exists() or not static_path.is_file():
        errors.append("thumbnail override must resolve to an existing local file")
        return None

    return local_url


def _classify_image_state(stored_thumbnail_url: Any, manual_thumbnail_override: Any, thumb: dict[str, str]) -> str:
    if thumb.get("thumbnail_status") == "override":
        return "local"
    if thumb.get("thumbnail_status") == "mapped":
        return "mapped"
    if _normalized_optional_text(manual_thumbnail_override) or _normalized_optional_text(stored_thumbnail_url):
        return "fallback"
    return "missing"


def _is_curated_row(row: dict[str, Any]) -> bool:
    manual = row.get("manual_meta") if isinstance(row.get("manual_meta"), dict) else {}
    return any(
        [
            bool(_normalized_optional_text(manual.get("display_name"))),
            bool(_normalized_optional_text(manual.get("category"))),
            bool(_normalized_optional_text(manual.get("subcategory"))),
            bool(_normalized_optional_text(manual.get("thumbnail_override"))),
            bool(row.get("buy_price") is not None),
            bool(row.get("sell_price") is not None),
            any(bool(value) for value in row.get("future_flags", {}).values()),
            bool(row.get("admin_notes")),
            "review_required" in manual,
        ]
    )
