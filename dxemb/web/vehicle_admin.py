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

from flask import Blueprint, abort, jsonify, render_template_string, request

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
def api_vehicle_catalog():
    """Return all vehicle families as card-ready JSON list."""
    families = get_builder_catalog()
    return jsonify({"ok": True, "count": len(families), "families": families})


@vehicle_bp.get("/api/vehicles/builder/<classname>")
def api_vehicle_builder(classname: str):
    """Return full builder payload for one vehicle family."""
    payload = get_builder_payload(classname)
    if payload is None:
        return jsonify({"ok": False, "error": f"Vehicle '{classname}' not found in resolver"}), 404
    return jsonify({"ok": True, "vehicle": payload})


@vehicle_bp.post("/api/vehicles/cache/flush")
def api_flush_cache():
    """Flush resolver LRU caches (call after uploading new resolver JSON)."""
    flush_resolver_cache()
    return jsonify({"ok": True, "message": "Vehicle resolver cache flushed"})


# ------------------------------------------------------------------
# Admin HTML pages
# ------------------------------------------------------------------

@vehicle_bp.get("/vehicles")
def vehicle_list():
    """Vehicle family card grid — admin vehicle builder landing page."""
    families = get_builder_catalog()
    return render_template_string(_VEHICLE_LIST_TMPL, families=families)


@vehicle_bp.get("/vehicles/<classname>")
def vehicle_builder(classname: str):
    """Single vehicle builder page — color + slot card selectors."""
    payload = get_builder_payload(classname)
    if payload is None:
        abort(404, description=f"Vehicle '{classname}' not found in resolver")
    return render_template_string(_VEHICLE_BUILDER_TMPL, vehicle=payload)


# ------------------------------------------------------------------
# Templates
# ------------------------------------------------------------------

_VEHICLE_LIST_TMPL = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DXEMB — Vehicle Builder</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #101115; color: #e8e8e8; padding: 1.5rem; }
    a { color: #8fd3ff; text-decoration: none; }
    h1 { font-size: 1.35rem; font-weight: 700; margin-bottom: 0.25rem; }
    .sub { color: #9aa3af; font-size: 0.85rem; margin-bottom: 1.5rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }
    .card {
      background: #171a21; border: 1px solid #2b2f3a; border-radius: 10px;
      overflow: hidden; cursor: pointer; transition: border-color 0.15s, transform 0.12s;
    }
    .card:hover { border-color: #3b82f6; transform: translateY(-2px); }
    .card img { width: 100%; aspect-ratio: 16/9; object-fit: cover; background: #0f131a; display: block; }
    .card-body { padding: 0.6rem 0.75rem 0.75rem; }
    .card-name { font-weight: 600; font-size: 0.9rem; margin-bottom: 0.2rem; }
    .card-meta { font-size: 0.75rem; color: #9aa3af; }
    .badge { display: inline-block; padding: 0.1rem 0.4rem; border-radius: 999px; font-size: 0.7rem; }
    .mapped  { background: #163924; color: #6ee7a8; }
    .fallback { background: #441414; color: #fca5a5; }
    .override { background: #1e3a5f; color: #7dd3fc; }
    .empty { color: #9aa3af; padding: 2rem 0; text-align: center; }
    .nav { margin-bottom: 1.25rem; font-size: 0.85rem; }
  </style>
</head>
<body>
  <div class="nav"><a href="/">&larr; Admin Home</a> &nbsp;|&nbsp; <a href="/catalog">Catalog</a></div>
  <h1>&#x1F697; Vehicle Builder</h1>
  <p class="sub">Select a vehicle family to configure color variants and part slots.</p>

  {% if families %}
  <div class="grid">
    {% for v in families %}
    <a href="/vehicles/{{ v.classname }}" class="card">
      <img src="{{ v.body_thumbnail_url }}" alt="{{ v.display_name }}" loading="lazy">
      <div class="card-body">
        <div class="card-name">{{ v.display_name }}</div>
        <div class="card-meta">
          {{ v.color_count }} color{{ 's' if v.color_count != 1 else '' }}
          &nbsp;&middot;&nbsp;
          {{ v.slot_count }} part{{ 's' if v.slot_count != 1 else '' }}
        </div>
        <div style="margin-top:0.35rem">
          <span class="badge {{ v.thumbnail_status }}">{{ v.thumbnail_status }}</span>
        </div>
      </div>
    </a>
    {% endfor %}
  </div>
  {% else %}
  <p class="empty">No vehicle families found in resolver. Add entries to vehicle_thumbnail_resolver.final.json.</p>
  {% endif %}
</body>
</html>
"""


_VEHICLE_BUILDER_TMPL = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ vehicle.display_name }} — DXEMB Vehicle Builder</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #101115; color: #e8e8e8; padding: 1.5rem; }
    a { color: #8fd3ff; text-decoration: none; }
    h1 { font-size: 1.3rem; font-weight: 700; margin-bottom: 0.1rem; }
    h2 { font-size: 0.95rem; font-weight: 600; color: #9aa3af; text-transform: uppercase;
         letter-spacing: 0.06em; margin: 1.25rem 0 0.6rem; }
    .sub { color: #9aa3af; font-size: 0.82rem; margin-bottom: 1.25rem; }
    .hero { display: flex; gap: 1.25rem; align-items: flex-start; margin-bottom: 1rem; }
    .hero img { width: 220px; border-radius: 8px; border: 1px solid #2b2f3a; background: #0f131a; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 0.75rem; }
    .card {
      background: #171a21; border: 2px solid #2b2f3a; border-radius: 8px;
      overflow: hidden; cursor: pointer; transition: border-color 0.15s;
    }
    .card:hover  { border-color: #3b82f6; }
    .card.active { border-color: #22c55e; }
    .card img { width: 100%; aspect-ratio: 1/1; object-fit: cover; background: #0f131a; display: block; }
    .card-body { padding: 0.45rem 0.55rem 0.5rem; }
    .card-name { font-size: 0.82rem; font-weight: 600; }
    .card-cls  { font-size: 0.7rem; color: #9aa3af; margin-top: 0.1rem; }
    .badge { display: inline-block; padding: 0.1rem 0.35rem; border-radius: 999px; font-size: 0.65rem; margin-top: 0.2rem; }
    .exact   { background: #163924; color: #6ee7a8; }
    .family_fallback { background: #3b2a05; color: #fbbf24; }
    .fallback { background: #441414; color: #fca5a5; }
    .override { background: #1e3a5f; color: #7dd3fc; }
    .required-tag { font-size: 0.65rem; color: #f97316; }
    .nav { margin-bottom: 1.25rem; font-size: 0.85rem; }
    .section-panel { background: #171a21; border: 1px solid #2b2f3a; border-radius: 10px; padding: 1rem 1.1rem 1.2rem; }
    .api-note { margin-top: 1.5rem; font-size: 0.78rem; color: #9aa3af; }
    code { background: #0f131a; border: 1px solid #2b2f3a; padding: 0.1rem 0.3rem; border-radius: 4px; font-size: 0.78rem; }
  </style>
</head>
<body>
  <div class="nav"><a href="/vehicles">&larr; Vehicle List</a></div>

  <div class="hero">
    <img src="{{ vehicle.body_thumbnail_url }}" alt="{{ vehicle.display_name }}">
    <div>
      <h1>{{ vehicle.display_name }}</h1>
      <p class="sub">{{ vehicle.category }} &nbsp;&middot;&nbsp; {{ vehicle.colors|length }} color{{ 's' if vehicle.colors|length != 1 else '' }} &nbsp;&middot;&nbsp; {{ vehicle.slots|length }} part slot{{ 's' if vehicle.slots|length != 1 else '' }}</p>
      <code>{{ vehicle.classname }}</code>
    </div>
  </div>

  {% if vehicle.colors %}
  <h2>Color Variants</h2>
  <div class="section-panel">
    <div class="grid">
      {% for c in vehicle.colors %}
      <div class="card" data-color="{{ c.color }}">
        <img src="{{ c.thumbnail_url }}" alt="{{ c.display_name }}" loading="lazy">
        <div class="card-body">
          <div class="card-name">{{ c.display_name }}</div>
          <div class="card-cls">{{ c.classname or '—' }}</div>
          <span class="badge {{ c.thumbnail_status }}">{{ c.thumbnail_status }}</span>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  {% if vehicle.slots %}
  <h2>Part Slots</h2>
  <div class="section-panel">
    <div class="grid">
      {% for s in vehicle.slots %}
      <div class="card" data-slot="{{ s.slot_name }}">
        <img src="{{ s.thumbnail_url }}" alt="{{ s.display_name }}" loading="lazy">
        <div class="card-body">
          <div class="card-name">{{ s.display_name }}</div>
          <div class="card-cls">{{ s.classname or '—' }}</div>
          {% if s.required %}<div class="required-tag">required</div>{% endif %}
          <span class="badge {{ s.thumbnail_status }}">{{ s.thumbnail_status }}</span>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  <p class="api-note">
    JSON API: <a href="/api/vehicles/builder/{{ vehicle.classname }}">/api/vehicles/builder/{{ vehicle.classname }}</a>
  </p>
</body>
</html>
"""
