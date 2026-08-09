from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from flask import Flask
from flask import url_for

_MANIFEST_PATH = Path(__file__).resolve().parent / "static" / "ui" / "asset_manifest.json"
_FALLBACK_IMAGE = "ui/thumbnail-fallback.svg"


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
    if src and src.strip():
        return src.strip()
    return ui_asset("images.thumbnail_fallback")


def ui_nav_links() -> list[dict[str, str]]:
    return [
        {"href": "/", "label": "Status"},
        {"href": "/catalog", "label": "Catalog"},
        {"href": "/vehicles", "label": "Vehicles"},
    ]


def register_ui_helpers(app: Flask) -> None:
    app.jinja_env.globals["ui_asset"] = ui_asset
    app.jinja_env.globals["ui_image"] = ui_image
    app.jinja_env.globals["ui_nav_links"] = ui_nav_links
