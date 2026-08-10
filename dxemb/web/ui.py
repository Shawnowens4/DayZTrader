from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from urllib.parse import urlsplit

from flask import Flask
from flask import url_for

_MANIFEST_PATH = Path(__file__).resolve().parent / "static" / "ui" / "asset_manifest.json"
_FALLBACK_IMAGE = "ui/thumbnail-fallback.svg"
_STATIC_ROOT = Path(__file__).resolve().parent / "static"
_LOCAL_CATALOG_DIRS = [
    _STATIC_ROOT / "catalog_items",
    _STATIC_ROOT / "items",
]


@lru_cache(maxsize=1)
def _load_manifest() -> dict[str, Any]:
    with _MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _get_by_key(data: dict[str, Any], dotted_key: str) -> str | None:
    node: Any = data
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def ui_asset(key: str) -> str:
    manifest = _load_manifest()
    path = _get_by_key(manifest, key)
    if not path:
        path = _FALLBACK_IMAGE if key.startswith("images.") else ""
    return url_for("static", filename=path) if path else ""


def ui_image(src: str | None) -> str:
    if not src or not src.strip():
        return ui_asset("images.thumbnail_fallback")

    candidate = src.strip()
    if candidate.startswith("/static/"):
        return candidate
    if candidate.startswith("data:image/"):
        return candidate

    local = _resolve_local_asset_url(candidate)
    if local:
        return local

    if candidate.startswith("http://") or candidate.startswith("https://"):
        return ui_asset("images.thumbnail_fallback")

    return candidate if candidate.startswith("/") else ui_asset("images.thumbnail_fallback")


@lru_cache(maxsize=8)
def _dir_index(directory: str) -> dict[str, str]:
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        return {}
    return {entry.name.lower(): entry.name for entry in root.iterdir() if entry.is_file()}


def _resolve_local_asset_url(src: str) -> str | None:
    candidate = (src or "").strip()
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
        for directory in _LOCAL_CATALOG_DIRS:
            exact = directory / option
            if exact.exists() and exact.is_file():
                rel = exact.relative_to(_STATIC_ROOT).as_posix()
                return f"/static/{rel}"
            if option.name:
                for found in directory.rglob(option.name):
                    if found.is_file():
                        rel = found.relative_to(_STATIC_ROOT).as_posix()
                        return f"/static/{rel}"

    return None


def _catalog_candidates(classname: str | None, source_url: str | None) -> list[str]:
    out: list[str] = []
    if source_url:
        base = Path(unquote(urlsplit(source_url).path)).name.strip()
        if base:
            out.append(base)

    if classname:
        normalized = classname.strip().lower()
        variants = {
            normalized,
            normalized.replace("-", "_"),
            normalized.replace(" ", "_"),
        }
        for value in variants:
            out.append(f"{value}.webp")
            out.append(f"{value}.png")
            out.append(f"{value}.jpg")
            out.append(f"{value}.jpeg")

    seen: set[str] = set()
    deduped: list[str] = []
    for name in out:
        lowered = name.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(name)
    return deduped


def catalog_thumbnail_src(classname: str | None, source_url: str | None) -> str:
    candidates = _catalog_candidates(classname=classname, source_url=source_url)
    for directory in _LOCAL_CATALOG_DIRS:
        index = _dir_index(str(directory))
        for candidate in candidates:
            found = index.get(candidate.lower())
            if found:
                rel = directory.relative_to(_STATIC_ROOT).as_posix()
                return url_for("static", filename=f"{rel}/{found}")

    return ui_image(source_url)


def ui_nav_links() -> list[dict[str, str]]:
    return [
        {"href": "/", "label": "Status"},
        {"href": "/catalog", "label": "Catalog"},
        {"href": "/catalog/admin", "label": "Catalog Admin"},
        {"href": "/vehicles", "label": "Vehicles"},
    ]


def register_ui_helpers(app: Flask) -> None:
    app.jinja_env.globals["ui_asset"] = ui_asset
    app.jinja_env.globals["ui_image"] = ui_image
    app.jinja_env.globals["catalog_thumbnail_src"] = catalog_thumbnail_src
    app.jinja_env.globals["ui_nav_links"] = ui_nav_links
