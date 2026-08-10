from __future__ import annotations
# =============================================================
# DXEMB  web/vehicle_admin.py  (A9)
# Flask blueprint: admin vehicle builder routes.
#
# Routes:
#   GET  /vehicles                        — vehicle family card grid
#   GET  /vehicles/<classname>            — single family builder page
#   GET  /api/vehicles/catalog            — JSON: all families (card list)
#   GET  /api/vehicles/builder/<family>   — JSON: full builder payload
#   POST /api/vehicles/cache/flush        — flush resolver LRU caches
# =============================================================

from flask import Blueprint, abort, jsonify, render_template, request

try:
    from web.local_auth import admin_or_higher
except ModuleNotFoundError:
    from local_auth import admin_or_higher

try:
    from shared.catalog.vehicle_builder_service import (
        flush_resolver_cache,
        get_builder_catalog,
        get_builder_payload,
    )
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from shared.catalog.vehicle_builder_service import (
        flush_resolver_cache,
        get_builder_catalog,
        get_builder_payload,
    )

vehicle_bp = Blueprint("vehicles", __name__)


# ------------------------------------------------------------------
# JSON API — consumed by Discord cogs and future JS frontend
# ------------------------------------------------------------------

@vehicle_bp.get("/api/vehicles/catalog")
@admin_or_higher(message="admin role is required for vehicle admin workspace")
def api_vehicle_catalog():
    """Return all vehicle families as card-ready JSON list."""
    families = get_builder_catalog()
    return jsonify({"ok": True, "count": len(families), "families": families})


@vehicle_bp.get("/api/vehicles/builder/<classname>")
@admin_or_higher(message="admin role is required for vehicle admin workspace")
def api_vehicle_builder(classname: str):
    """Return full builder payload for one vehicle family."""
    payload = get_builder_payload(classname)
    if payload is None:
        return jsonify({"ok": False, "error": f"Vehicle '{classname}' not found in resolver"}), 404
    return jsonify({"ok": True, "vehicle": payload})


@vehicle_bp.post("/api/vehicles/cache/flush")
@admin_or_higher(message="admin role is required for vehicle admin workspace")
def api_flush_cache():
    """Flush resolver LRU caches (call after uploading new resolver JSON)."""
    flush_resolver_cache()
    return jsonify({"ok": True, "message": "Vehicle resolver cache flushed"})


# ------------------------------------------------------------------
# Admin HTML pages
# ------------------------------------------------------------------

@vehicle_bp.get("/vehicles")
@admin_or_higher(message="admin role is required for vehicle admin workspace")
def vehicle_list():
    """Vehicle family card grid — admin vehicle builder landing page."""
    families = get_builder_catalog()
    return render_template("vehicle_list.html", families=families)


@vehicle_bp.get("/vehicles/<classname>")
@admin_or_higher(message="admin role is required for vehicle admin workspace")
def vehicle_builder(classname: str):
    """Single vehicle builder page — color + slot card selectors."""
    payload = get_builder_payload(classname)
    if payload is None:
        abort(404, description=f"Vehicle '{classname}' not found in resolver")
    return render_template("vehicle_builder.html", vehicle=payload)
