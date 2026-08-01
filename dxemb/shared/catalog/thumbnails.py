from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


DAYZIDB_IMAGE_BASE_URL = os.getenv(
    "DAYZIDB_IMAGE_BASE_URL",
    "https://dayzidb.com/images/items",
)

THUMBNAIL_FALLBACK_URL = os.getenv(
    "DAYZ_THUMBNAIL_FALLBACK_URL",
    "https://via.placeholder.com/320x180.png?text=DayZ+Item",
)


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
    mapped_url = mapped_thumbnail_url(classname)
    existing = (existing_thumbnail_url or "").strip()

    if existing:
        if mapped_url and _normalize_url(existing) == _normalize_url(mapped_url):
            return {
                "thumbnail_url": existing,
                "thumbnail_status": "mapped",
                "thumbnail_source": "dayzidb_map",
            }

        return {
            "thumbnail_url": existing,
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

    if relative.startswith("http://") or relative.startswith("https://"):
        return relative

    return f"{DAYZIDB_IMAGE_BASE_URL.rstrip('/')}/{relative.lstrip('/')}"


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


def _resolve_map_path() -> Path:
    explicit = os.getenv("DAYZIDB_MAP_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    return (Path(__file__).resolve().parent / "data" / "dayzidb_map.json").resolve()


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/").lower()
