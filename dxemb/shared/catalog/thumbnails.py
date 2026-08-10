from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from urllib.parse import unquote
from urllib.parse import urlsplit

DAYZIDB_IMAGE_BASE_URL = os.getenv(
    "DAYZIDB_IMAGE_BASE_URL",
    "https://dayzidb.com/images/items",
)

THUMBNAIL_FALLBACK_URL = os.getenv(
    "DAYZ_THUMBNAIL_FALLBACK_URL",
    "/static/ui/thumbnail-fallback.svg",
)

_WEB_STATIC_ROOT = Path(__file__).resolve().parents[2] / "web" / "static"
_LOCAL_IMAGE_DIRS = [
    _WEB_STATIC_ROOT / "catalog_items",
    _WEB_STATIC_ROOT / "items",
]


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
                indexed = _dir_index(str(directory)).get(option.name.lower())
                if indexed:
                    found = directory / indexed
                    if found.exists() and found.is_file():
                        return _static_url(found)

    return None


def resolve_thumbnail(
    classname: str,
    existing_thumbnail_url: str | None = None,
) -> dict[str, str]:
    """Resolve thumbnail URL and status for catalog consumers.

    Priority order:
    1) explicit item.thumbnail_url (future admin override support)
    2) mapped DayZIDB path from local map file
    3) shared fallback URL
    """
    existing = (existing_thumbnail_url or "").strip()
    mapped_url = mapped_thumbnail_url(classname)

    if existing:
        local_existing = _local_asset_url(existing)
        if local_existing:
            if mapped_url and _normalize_url(local_existing) == _normalize_url(mapped_url):
                return {
                    "thumbnail_url": local_existing,
                    "thumbnail_status": "mapped",
                    "thumbnail_source": "dayzidb_map",
                }

            return {
                "thumbnail_url": local_existing,
                "thumbnail_status": "override",
                "thumbnail_source": "item.thumbnail_url",
            }

    if mapped_url:
        return {
            "thumbnail_url": mapped_url,
            "thumbnail_status": "mapped",
            "thumbnail_source": "dayzidb_map",
        }

    return {
        "thumbnail_url": THUMBNAIL_FALLBACK_URL,
        "thumbnail_status": "fallback",
        "thumbnail_source": "fallback",
    }


def mapped_thumbnail_url(classname: str) -> str | None:
    """Return mapped DayZIDB thumbnail URL for classname if present."""
    if not classname.strip():
        return None

    mapping = _load_thumbnail_map()
    key = classname.strip().lower()
    relative = mapping.get(key)
    if not relative:
        return None

    local_url = _local_asset_url(relative)
    if local_url:
        return local_url

    return THUMBNAIL_FALLBACK_URL


@lru_cache(maxsize=1)
def _load_thumbnail_map() -> dict[str, str]:
    path = _resolve_map_path()
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data: Any = json.load(handle)

    if not isinstance(data, dict):
        return {}

    out: dict[str, str] = {}
    for raw_key, raw_value in data.items():
        key = str(raw_key).strip().lower()
        value = str(raw_value).strip()
        if key and value:
            out[key] = value
    return out


@lru_cache(maxsize=8)
def _dir_index(directory: str) -> dict[str, str]:
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        return {}

    out: dict[str, str] = {}
    for entry in root.rglob("*"):
        if not entry.is_file():
            continue
        out.setdefault(entry.name.lower(), entry.relative_to(root).as_posix())
    return out


def _resolve_map_path() -> Path:
    explicit = os.getenv("DAYZIDB_MAP_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    return (Path(__file__).resolve().parent / "data" / "dayzidb_map.json").resolve()


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()
