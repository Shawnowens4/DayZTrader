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
from urllib.parse import quote
from urllib.parse import unquote
from urllib.parse import urlsplit

from .vehicle_family_catalog import resolve_vehicle_family_identity
from .vehicle_family_catalog import normalize_vehicle_family_token

_DATA_DIR = Path(__file__).resolve().parent / "data"
_WEB_STATIC_ROOT = Path(__file__).resolve().parents[2] / "web" / "static"
_LOCAL_IMAGE_DIRS = [
    _WEB_STATIC_ROOT / "catalog_items",
    _WEB_STATIC_ROOT / "items",
]
_LOCAL_GENERIC_VEHICLE_URL = "/static/catalog_items/vehicles.webp"
_LOCAL_FALLBACK_URL = "/static/ui/thumbnail-fallback.svg"

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


def _static_url(path: Path) -> str:
    return f"/static/{path.relative_to(_WEB_STATIC_ROOT).as_posix()}"


def _local_asset_url(path_or_url: str) -> str | None:
    candidate = (path_or_url or "").strip()
    if not candidate:
        return None

    raw_path = Path(unquote(urlsplit(candidate).path))
    options: list[Path] = []
    if raw_path.as_posix().strip("."):
        options.append(raw_path)
    if raw_path.name:
        options.append(Path(raw_path.name))

    seen: set[str] = set()
    for option in options:
        key = option.as_posix().lower()
        if key in seen:
            continue
        seen.add(key)
        for directory in _LOCAL_IMAGE_DIRS:
            exact = directory / option
            if exact.exists() and exact.is_file():
                return _static_url(exact)
            if option.name:
                for found in directory.rglob(option.name):
                    if found.is_file():
                        return _static_url(found)

    return None


def _vehicle_fallback_url() -> str:
    return _LOCAL_FALLBACK_URL


def _category_accent(category: str | None) -> str:
    key = (category or "").strip().lower()
    if "truck" in key:
        return "#7daeff"
    if "car" in key:
        return "#7dff57"
    if "helicopter" in key or "air" in key:
        return "#d18bff"
    if "boat" in key or "water" in key:
        return "#6dd7f7"
    return "#9aa7a0"


def _safe_svg_text(value: str, limit: int = 40) -> str:
    txt = (value or "").strip().replace("&", " and ").replace("<", "[").replace(">", "]")
    return txt[:limit] if len(txt) > limit else txt


def _lookup_token(value: str) -> str:
    return normalize_vehicle_family_token(value)


def _resolve_family_entry(resolver: dict[str, Any], classname: str) -> tuple[str | None, dict[str, Any] | None]:
    key = classname.strip().lower()
    entry = resolver.get(key) or resolver.get(classname.strip())
    if isinstance(entry, dict):
        return classname.strip(), entry

    identity = resolve_vehicle_family_identity(classname)
    wanted_tokens = {
        _lookup_token(classname),
        _lookup_token(classname.replace("_", "")),
    }
    if identity:
        wanted_tokens.add(_lookup_token(str(identity.get("canonical_key", ""))))
        for alias in identity.get("aliases", []) or []:
            wanted_tokens.add(_lookup_token(str(alias)))
        for prefix in identity.get("source_classname_prefixes", []) or []:
            wanted_tokens.add(_lookup_token(str(prefix).rstrip("_")))

    for resolver_key, resolver_entry in resolver.items():
        if not isinstance(resolver_entry, dict):
            continue
        if _lookup_token(str(resolver_key)) in wanted_tokens:
            return str(resolver_key), resolver_entry

    return None, None


def _svg_data_uri(svg: str) -> str:
    return f"data:image/svg+xml;utf8,{quote(svg, safe='')}"


def _vehicle_identity_fallback(display_name: str, family_label: str, category: str | None) -> str:
    accent = _category_accent(category)
    title = _safe_svg_text(display_name, 30)
    family = _safe_svg_text(family_label, 34)
    category_txt = _safe_svg_text(category or "vehicle", 16)
    svg = f"""
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 180'>
  <defs>
    <linearGradient id='bg' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0%' stop-color='#11171c'/>
      <stop offset='100%' stop-color='#1a2328'/>
    </linearGradient>
  </defs>
  <rect width='320' height='180' fill='url(#bg)'/>
  <rect x='10' y='10' width='300' height='160' rx='12' ry='12' fill='none' stroke='#2b373f' stroke-width='1.5'/>
  <rect x='16' y='16' width='4' height='148' fill='{accent}' opacity='0.85'/>
  <path d='M56 108h194l-11-25h-42l-12-16h-57l-19 16h-36z' fill='#2a343a' stroke='#3a474f' stroke-width='2'/>
  <circle cx='98' cy='112' r='9' fill='#0f1418' stroke='#4c5b64' stroke-width='2'/>
  <circle cx='213' cy='112' r='9' fill='#0f1418' stroke='#4c5b64' stroke-width='2'/>
  <text x='28' y='36' fill='#e7eee8' font-family='Segoe UI, Tahoma, sans-serif' font-size='16' font-weight='700'>{title}</text>
  <text x='28' y='55' fill='#95a49c' font-family='Segoe UI, Tahoma, sans-serif' font-size='11'>Class: {family}</text>
  <text x='28' y='72' fill='{accent}' font-family='Segoe UI, Tahoma, sans-serif' font-size='10' text-transform='uppercase'>Category: {category_txt}</text>
  <text x='28' y='157' fill='#aab5af' font-family='Segoe UI, Tahoma, sans-serif' font-size='11'>Art pending - local fallback</text>
</svg>
""".strip()
    return _svg_data_uri(svg)


def _part_identity_fallback(part_label: str, slot_label: str, status_text: str, review_required: bool = False) -> str:
    accent = "#ffcb4c" if review_required else "#97a39b"
    fill = "#ffcb4c" if review_required else "#c3cbc6"
    title = _safe_svg_text(part_label, 30)
    slot = _safe_svg_text(slot_label, 26)
    status = _safe_svg_text(status_text, 30)
    svg = f"""
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 180'>
  <rect width='320' height='180' fill='#151c21'/>
  <rect x='10' y='10' width='300' height='160' rx='12' ry='12' fill='none' stroke='#2e3940' stroke-width='1.5'/>
  <rect x='16' y='16' width='4' height='148' fill='{accent}' opacity='0.82'/>
  <rect x='58' y='62' width='82' height='58' rx='8' ry='8' fill='#263038' stroke='#44525b' stroke-width='1.5'/>
  <path d='M62 88h74' stroke='#4f5e67' stroke-width='2'/>
  <path d='M162 72h102M162 89h84M162 106h95' stroke='#53616a' stroke-width='3' stroke-linecap='round'/>
  <text x='28' y='36' fill='#e7eeea' font-family='Segoe UI, Tahoma, sans-serif' font-size='15' font-weight='700'>{title}</text>
  <text x='28' y='54' fill='#a0aca5' font-family='Segoe UI, Tahoma, sans-serif' font-size='11'>Slot: {slot}</text>
  <text x='28' y='157' fill='{fill}' font-family='Segoe UI, Tahoma, sans-serif' font-size='11'>{status}</text>
</svg>
""".strip()
    return _svg_data_uri(svg)


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
    fallback_display = classname.strip() or "Unknown Vehicle"

    key = classname.strip().lower()
    override_url = overrides.get("classnames", {}).get(key)
    if override_url:
        local_override = _local_asset_url(override_url)
        return {
            "thumbnail_url": local_override or _vehicle_identity_fallback(fallback_display, classname, "Vehicle"),
            "thumbnail_status": "override" if local_override else "fallback",
            "thumbnail_source": "vehicle_overrides.json#classnames" if local_override else "local_identity_vehicle",
            "resolved_color": color or "",
        }

    _, entry = _resolve_family_entry(resolver, classname)
    if not entry:
        return {
            "thumbnail_url": _vehicle_identity_fallback(fallback_display, classname, "Vehicle"),
            "thumbnail_status": "fallback",
            "thumbnail_source": "local_identity_vehicle",
            "resolved_color": "",
        }

    color_key = (color or "").strip().lower()
    colors: dict[str, Any] = entry.get("colors", {})

    if color_key and color_key in colors:
        url = colors[color_key].get("thumbnail") or entry.get("body_thumbnail") or ""
        local_url = _local_asset_url(url)
        if not local_url:
            local_url = _vehicle_identity_fallback(
                entry.get("display_name") or classname,
                classname,
                entry.get("category") or "Vehicle",
            )
        return {
            "thumbnail_url": local_url,
            "thumbnail_status": "exact" if _local_asset_url(url) else "family_fallback",
            "thumbnail_source": f"resolver#colors:{color_key}" if _local_asset_url(url) else "local_identity_vehicle",
            "resolved_color": color_key,
        }

    body_url = entry.get("body_thumbnail") or ""
    local_body_url = _local_asset_url(body_url)
    if not local_body_url:
        local_body_url = _vehicle_identity_fallback(
            entry.get("display_name") or classname,
            classname,
            entry.get("category") or "Vehicle",
        )
    if body_url:
        return {
            "thumbnail_url": local_body_url,
            "thumbnail_status": "mapped" if _local_asset_url(body_url) else "family_fallback",
            "thumbnail_source": "resolver#body_thumbnail" if _local_asset_url(body_url) else "local_identity_vehicle",
            "resolved_color": "",
        }

    return {
        "thumbnail_url": _vehicle_identity_fallback(
            entry.get("display_name") or classname,
            classname,
            entry.get("category") or "Vehicle",
        ),
        "thumbnail_status": "fallback",
        "thumbnail_source": "local_identity_vehicle",
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
        has_local_body = bool(_local_asset_url(body_url))
        local_body_url = _local_asset_url(body_url) or _vehicle_identity_fallback(
            entry.get("display_name") or classname,
            classname,
            entry.get("category") or "Vehicle",
        )
        families.append({
            "classname": classname,
            "display_name": entry.get("display_name") or classname,
            "category": entry.get("category") or "Vehicle",
            "color_count": len(entry.get("colors", {})),
            "slot_count": len(entry.get("slots", [])),
            "body_thumbnail_url": local_body_url,
            "thumbnail_status": "override" if family_override and _local_asset_url(family_override) else ("mapped" if has_local_body else "family_fallback"),
        })

    families.sort(key=lambda x: x["display_name"].lower())
    return families


def get_vehicle_family(classname: str) -> dict[str, Any] | None:
    """Return full resolver entry for one vehicle family, with overrides applied."""
    resolver = _load_resolver()
    overrides = _load_overrides()

    resolved_key, entry = _resolve_family_entry(resolver, classname)
    if not entry:
        return None

    lookup_key = (resolved_key or classname).strip().lower()
    family_override_url = overrides.get("families", {}).get(lookup_key)
    colors_raw: dict[str, Any] = entry.get("colors", {})
    colors_out: list[dict[str, Any]] = []

    body_url = family_override_url or entry.get("body_thumbnail") or ""
    local_body_path = _local_asset_url(body_url)
    local_body_url = local_body_path or _vehicle_identity_fallback(
        entry.get("display_name") or classname,
        classname,
        entry.get("category") or "Vehicle",
    )

    for color_key, color_data in colors_raw.items():
        color_override = overrides.get("colors", {}).get(f"{lookup_key}#{color_key}")
        raw_url = color_override or color_data.get("thumbnail") or entry.get("body_thumbnail") or ""
        local_color_path = _local_asset_url(raw_url)
        local_color_url = local_color_path or local_body_url
        colors_out.append({
            "color": color_key,
            "display_name": color_data.get("display_name") or color_key.replace("_", " ").title(),
            "thumbnail_url": local_color_url,
            "thumbnail_status": "override" if color_override and _local_asset_url(color_override) else ("exact" if local_color_path else ("family_fallback" if local_color_url == local_body_url else "fallback")),
            "classname": color_data.get("classname") or "",
        })

    slots_raw: list[Any] = entry.get("slots", [])
    slots_out: list[dict[str, Any]] = []
    for slot in slots_raw:
        slot_class = slot.get("classname") or ""
        slot_override_url = overrides.get("classnames", {}).get(slot_class.lower())
        raw_url = slot_override_url or slot.get("thumbnail") or ""
        local_slot_path = _local_asset_url(raw_url)
        review_required = slot.get("approved_status") == "owner_review_required"
        local_slot_url = local_slot_path or _part_identity_fallback(
            slot.get("display_name") or slot_class or "Unknown Part",
            slot.get("slot_name") or "unknown-slot",
            "Owner review required" if review_required else "Art pending - local fallback",
            review_required=review_required,
        )
        slots_out.append({
            "slot_name": slot.get("slot_name") or slot_class,
            "classname": slot_class,
            "display_name": slot.get("display_name") or slot_class,
            "required": slot.get("required", False),
            "thumbnail_url": local_slot_url,
            "thumbnail_status": "override" if slot_override_url and _local_asset_url(slot_override_url) else ("mapped" if local_slot_path else ("owner_review_required" if review_required else "family_fallback")),
        })
    identity = resolve_vehicle_family_identity(classname)
    return {
        "classname": classname,
        "resolved_classname": resolved_key or classname,
        "family_identity": {
            "canonical_key": identity.get("canonical_key") if identity else classname,
            "display_name": identity.get("display_name") if identity else (entry.get("display_name") or classname),
            "source_classname_prefixes": identity.get("source_classname_prefixes", []) if identity else [],
            "aliases": identity.get("aliases", []) if identity else [],
        },
        "display_name": entry.get("display_name") or classname,
        "category": entry.get("category") or "Vehicle",
        "body_thumbnail_url": local_body_url,
        "thumbnail_status": "override" if family_override_url and _local_asset_url(family_override_url) else ("mapped" if local_body_path else "family_fallback"),
        "colors": colors_out,
        "slots": slots_out,
    }


def reload_resolver() -> None:
    """Clear LRU caches so next call reloads from disk (e.g. after file update)."""
    _load_resolver.cache_clear()
    _load_overrides.cache_clear()


def _guess_family(classname: str) -> str | None:
    """Best-effort family key from classname (e.g. 'Olga247_Black' -> 'olga247')."""
    import re
    match = re.match(r"^([a-zA-Z]+\d*)", classname.strip())
    if match:
        return match.group(1).lower()
    return None
