from __future__ import annotations
# =============================================================
# DXEMB  shared/catalog/vehicle_resolver.py  (A9)
# Loads vehicle_thumbnail_resolver.final.json and exposes
# per-vehicle thumbnail resolution with exact/fallback flags.
#
# Consumed by:
#   - vehicle_builder_service.py  (builder payloads)
#   - Flask vehicle_admin blueprint
#   - Discord vehicle selector cog (future)
# =============================================================

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent / "data"

VEHICLE_RESOLVER_PATH = os.getenv(
    "VEHICLE_RESOLVER_PATH",
    str(_DATA_DIR / "vehicle_thumbnail_resolver.final.json"),
)

VEHICLE_OVERRIDES_PATH = os.getenv(
    "VEHICLE_OVERRIDES_PATH",
    str(_DATA_DIR / "vehicle_overrides.json"),
)

DAYZIDB_IMAGE_BASE_URL = os.getenv(
    "DAYZIDB_IMAGE_BASE_URL",
    "https://dayzidb.com/images/items",
)

THUMBNAIL_FALLBACK_URL = os.getenv(
    "DAYZ_THUMBNAIL_FALLBACK_URL",
    "https://via.placeholder.com/320x180.png?text=DayZ+Vehicle",
)


@lru_cache(maxsize=1)
def _load_resolver() -> dict[str, Any]:
    path = Path(VEHICLE_RESOLVER_PATH)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def _load_overrides() -> dict[str, Any]:
    path = Path(VEHICLE_OVERRIDES_PATH)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def resolve_vehicle_thumbnail(
    classname: str,
    color: str | None = None,
) -> dict[str, str]:
    """Resolve a single vehicle thumbnail URL with status flags.

    Priority:
      1. classname-level override (vehicle_overrides.json)
      2. exact color match in resolver
      3. family body thumbnail (fallback within same family)
      4. global fallback

    Returns dict with keys:
        thumbnail_url, thumbnail_status (exact|family_fallback|override|fallback),
        thumbnail_source, resolved_color
    """
    overrides = _load_overrides()
    resolver = _load_resolver()

    key = classname.strip().lower()
    override_url = overrides.get("classnames", {}).get(key)
    if override_url:
        return {
            "thumbnail_url": _full_url(override_url),
            "thumbnail_status": "override",
            "thumbnail_source": "vehicle_overrides.json#classnames",
            "resolved_color": color or "",
        }

    entry = resolver.get(key) or resolver.get(classname.strip())
    if not entry:
        family_key = _guess_family(classname)
        family_entry = resolver.get(family_key) if family_key else None
        if family_entry:
            body_url = family_entry.get("body_thumbnail") or ""
            if body_url:
                return {
                    "thumbnail_url": _full_url(body_url),
                    "thumbnail_status": "family_fallback",
                    "thumbnail_source": f"resolver#family:{family_key}",
                    "resolved_color": "",
                }
        return {
            "thumbnail_url": THUMBNAIL_FALLBACK_URL,
            "thumbnail_status": "fallback",
            "thumbnail_source": "fallback",
            "resolved_color": "",
        }

    color_key = (color or "").strip().lower()
    colors: dict[str, Any] = entry.get("colors", {})

    if color_key and color_key in colors:
        url = colors[color_key].get("thumbnail") or entry.get("body_thumbnail") or ""
        return {
            "thumbnail_url": _full_url(url) if url else THUMBNAIL_FALLBACK_URL,
            "thumbnail_status": "exact" if url else "fallback",
            "thumbnail_source": f"resolver#colors:{color_key}",
            "resolved_color": color_key,
        }

    body_url = entry.get("body_thumbnail") or ""
    if body_url:
        return {
            "thumbnail_url": _full_url(body_url),
            "thumbnail_status": "family_fallback",
            "thumbnail_source": "resolver#body_thumbnail",
            "resolved_color": "",
        }

    return {
        "thumbnail_url": THUMBNAIL_FALLBACK_URL,
        "thumbnail_status": "fallback",
        "thumbnail_source": "fallback",
        "resolved_color": "",
    }


def list_vehicle_families() -> list[dict[str, Any]]:
    """Return all known vehicle families with metadata for admin list pages."""
    resolver = _load_resolver()
    overrides = _load_overrides()
    families: list[dict[str, Any]] = []

    for classname, entry in resolver.items():
        if not isinstance(entry, dict):
            continue
        family_override = overrides.get("families", {}).get(classname.lower())
        body_url = family_override or entry.get("body_thumbnail") or ""
        families.append({
            "classname": classname,
            "display_name": entry.get("display_name") or classname,
            "category": entry.get("category") or "Vehicle",
            "color_count": len(entry.get("colors", {})),
            "slot_count": len(entry.get("slots", [])),
            "body_thumbnail_url": _full_url(body_url) if body_url else THUMBNAIL_FALLBACK_URL,
            "thumbnail_status": "override" if family_override else ("mapped" if body_url else "fallback"),
        })

    families.sort(key=lambda x: x["display_name"].lower())
    return families


def get_vehicle_family(classname: str) -> dict[str, Any] | None:
    """Return full resolver entry for one vehicle family, with overrides applied."""
    resolver = _load_resolver()
    overrides = _load_overrides()

    key = classname.strip().lower()
    entry = resolver.get(key) or resolver.get(classname.strip())
    if not entry:
        return None

    family_override_url = overrides.get("families", {}).get(key)
    colors_raw: dict[str, Any] = entry.get("colors", {})
    colors_out: list[dict[str, Any]] = []

    for color_key, color_data in colors_raw.items():
        color_override = overrides.get("colors", {}).get(f"{key}#{color_key}")
        raw_url = color_override or color_data.get("thumbnail") or entry.get("body_thumbnail") or ""
        colors_out.append({
            "color": color_key,
            "display_name": color_data.get("display_name") or color_key.replace("_", " ").title(),
            "thumbnail_url": _full_url(raw_url) if raw_url else THUMBNAIL_FALLBACK_URL,
            "thumbnail_status": "override" if color_override else ("exact" if color_data.get("thumbnail") else "family_fallback"),
            "classname": color_data.get("classname") or "",
        })

    slots_raw: list[Any] = entry.get("slots", [])
    slots_out: list[dict[str, Any]] = []
    for slot in slots_raw:
        slot_class = slot.get("classname") or ""
        slot_override_url = overrides.get("classnames", {}).get(slot_class.lower())
        raw_url = slot_override_url or slot.get("thumbnail") or ""
        slots_out.append({
            "slot_name": slot.get("slot_name") or slot_class,
            "classname": slot_class,
            "display_name": slot.get("display_name") or slot_class,
            "required": slot.get("required", False),
            "thumbnail_url": _full_url(raw_url) if raw_url else THUMBNAIL_FALLBACK_URL,
            "thumbnail_status": "override" if slot_override_url else ("mapped" if slot.get("thumbnail") else "fallback"),
        })

    body_url = family_override_url or entry.get("body_thumbnail") or ""
    return {
        "classname": classname,
        "display_name": entry.get("display_name") or classname,
        "category": entry.get("category") or "Vehicle",
        "body_thumbnail_url": _full_url(body_url) if body_url else THUMBNAIL_FALLBACK_URL,
        "thumbnail_status": "override" if family_override_url else ("mapped" if body_url else "fallback"),
        "colors": colors_out,
        "slots": slots_out,
    }


def reload_resolver() -> None:
    """Clear LRU caches so next call reloads from disk (e.g. after file update)."""
    _load_resolver.cache_clear()
    _load_overrides.cache_clear()


def _full_url(path_or_url: str) -> str:
    if not path_or_url:
        return THUMBNAIL_FALLBACK_URL
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return f"{DAYZIDB_IMAGE_BASE_URL.rstrip('/')}/{path_or_url.lstrip('/')}"


def _guess_family(classname: str) -> str | None:
    """Best-effort family key from classname (e.g. 'Olga247_Black' -> 'olga247')."""
    import re
    match = re.match(r"^([a-zA-Z]+\d*)", classname.strip())
    if match:
        return match.group(1).lower()
    return None
