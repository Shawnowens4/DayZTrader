from __future__ import annotations

from flask import Blueprint
from flask import abort
from flask import redirect
from flask import render_template_string
from flask import request
from flask import url_for

from shared.catalog.service import get_catalog_item_sync
from shared.catalog.service import list_catalog_categories_sync
from shared.catalog.service import search_catalog_sync
from shared.catalog.service import set_catalog_item_enabled_sync

catalog_bp = Blueprint("catalog", __name__)

PAGE_SIZE = 20


@catalog_bp.get("/catalog")
def catalog_list():
    query = request.args.get("q", "").strip()
    category = (request.args.get("category", "") or "").strip() or None
    state = (request.args.get("state", "all") or "all").strip().lower()
    page = max(1, int(request.args.get("page", "1") or "1"))

    enabled_only = state == "enabled"
    disabled_only = state == "disabled"

    rows = search_catalog_sync(
        query=query,
        category=category,
        enabled_only=False,
        limit=PAGE_SIZE + 1,
        offset=(page - 1) * PAGE_SIZE,
    )

    if enabled_only:
        rows = [row for row in rows if row["is_enabled"]]
    if disabled_only:
        rows = [row for row in rows if not row["is_enabled"]]

    has_next = len(rows) > PAGE_SIZE
    visible = rows[:PAGE_SIZE]
    categories = list_catalog_categories_sync(enabled_only=False)

    return render_template_string(
        _CATALOG_LIST_TMPL,
        items=visible,
        categories=categories,
        selected_category=category or "",
        query=query,
        state=state,
        page=page,
        has_next=has_next,
    )


@catalog_bp.get("/catalog/<classname>")
def catalog_detail(classname: str):
    item = get_catalog_item_sync(classname)
    if item is None:
        abort(404, description="Catalog item not found")

    return render_template_string(_CATALOG_DETAIL_TMPL, item=item)


@catalog_bp.post("/catalog/<classname>/enabled")
def set_enabled(classname: str):
    raw = (request.form.get("enabled", "") or "").strip().lower()
    enabled = raw in {"1", "true", "yes", "on"}
    set_catalog_item_enabled_sync(classname, enabled)

    return_to = request.form.get("return_to", "") or ""
    if return_to:
        return redirect(return_to)
    return redirect(url_for("catalog.catalog_detail", classname=classname))


_CATALOG_LIST_TMPL = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DXEMB Catalog Admin</title>
  <style>
    body { font-family: 'Segoe UI', sans-serif; margin: 0; background: #101115; color: #e8e8e8; }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 1.25rem; }
    a { color: #8fd3ff; text-decoration: none; }
    h1 { margin: 0 0 0.75rem 0; font-size: 1.4rem; }
    .muted { color: #9aa3af; }
    .panel { background: #171a21; border: 1px solid #2b2f3a; border-radius: 10px; padding: 1rem; margin-bottom: 1rem; }
    .filters { display: grid; gap: 0.6rem; grid-template-columns: 1.4fr 1fr 1fr auto; }
    input, select, button { width: 100%; padding: 0.45rem 0.6rem; border-radius: 6px; border: 1px solid #333947; background: #0f131a; color: #e8e8e8; }
    button { cursor: pointer; background: #1f6feb; border-color: #1f6feb; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 0.6rem; border-bottom: 1px solid #252a35; font-size: 0.9rem; text-align: left; }
    .badge { display:inline-block; padding:0.12rem 0.45rem; border-radius:999px; font-size:0.72rem; }
    .on { background:#163924; color:#6ee7a8; }
    .off { background:#441414; color:#fca5a5; }
    .mapped { color:#7dd3fc; }
    .fallback { color:#fbbf24; }
    .pager { display:flex; gap:0.6rem; justify-content:flex-end; margin-top:0.7rem; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>DXEMB Catalog Management</h1>
    <p class="muted">Browse, search, filter, inspect thumbnail mapping, and toggle enabled state.</p>

    <div class="panel">
      <form method="get" action="/catalog" class="filters">
        <input type="text" name="q" value="{{ query }}" placeholder="Search classname or display name">
        <select name="category">
          <option value="">All categories</option>
          {% for cat in categories %}
          <option value="{{ cat }}" {{ 'selected' if selected_category == cat else '' }}>{{ cat }}</option>
          {% endfor %}
        </select>
        <select name="state">
          <option value="all" {{ 'selected' if state == 'all' else '' }}>All states</option>
          <option value="enabled" {{ 'selected' if state == 'enabled' else '' }}>Enabled only</option>
          <option value="disabled" {{ 'selected' if state == 'disabled' else '' }}>Disabled only</option>
        </select>
        <button type="submit">Apply</button>
      </form>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Category</th>
            <th>Status</th>
            <th>Thumbnail</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {% for item in items %}
          <tr>
            <td>
              <a href="/catalog/{{ item.classname }}">{{ item.display_name or item.classname }}</a><br>
              <span class="muted">{{ item.classname }}</span>
            </td>
            <td>{{ item.category or '-' }} / {{ item.subcategory or '-' }}</td>
            <td>
              <span class="badge {{ 'on' if item.is_enabled else 'off' }}">
                {{ 'enabled' if item.is_enabled else 'disabled' }}
              </span>
            </td>
            <td>
              <span class="{{ item.thumbnail_status }}">{{ item.thumbnail_status }}</span>
              <div class="muted">{{ item.thumbnail_source }}</div>
            </td>
            <td>
              <form method="post" action="/catalog/{{ item.classname }}/enabled">
                <input type="hidden" name="enabled" value="{{ '0' if item.is_enabled else '1' }}">
                <input type="hidden" name="return_to" value="{{ request.full_path }}">
                <button type="submit">{{ 'Disable' if item.is_enabled else 'Enable' }}</button>
              </form>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>

      <div class="pager">
        {% if page > 1 %}
          <a href="?q={{ query }}&category={{ selected_category }}&state={{ state }}&page={{ page - 1 }}">Prev</a>
        {% endif %}
        {% if has_next %}
          <a href="?q={{ query }}&category={{ selected_category }}&state={{ state }}&page={{ page + 1 }}">Next</a>
        {% endif %}
      </div>
    </div>
  </div>
</body>
</html>
"""


_CATALOG_DETAIL_TMPL = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ item.display_name or item.classname }} - DXEMB Catalog</title>
  <style>
    body { font-family: 'Segoe UI', sans-serif; margin: 0; background: #101115; color: #e8e8e8; }
    .wrap { max-width: 920px; margin: 0 auto; padding: 1.25rem; }
    .panel { background: #171a21; border: 1px solid #2b2f3a; border-radius: 10px; padding: 1rem; }
    .grid { display:grid; grid-template-columns: 280px 1fr; gap:1rem; }
    .thumb { width: 100%; border-radius: 8px; border: 1px solid #2b2f3a; background: #0f131a; }
    .muted { color:#9aa3af; }
    code { background:#0f131a; border:1px solid #2b2f3a; padding: 0.1rem 0.3rem; border-radius: 4px; }
    .row { margin-bottom: 0.55rem; }
    button { padding: 0.45rem 0.8rem; border-radius: 6px; border: 1px solid #333947; background: #1f6feb; color: #e8e8e8; cursor: pointer; }
  </style>
</head>
<body>
  <div class="wrap">
    <p><a href="/catalog">&larr; Back to catalog</a></p>
    <div class="panel grid">
      <div>
        <img class="thumb" src="{{ item.resolved_thumbnail_url }}" alt="{{ item.classname }}">
        <p class="muted">{{ item.thumbnail_status }} / {{ item.thumbnail_source }}</p>
      </div>
      <div>
        <h1>{{ item.display_name or item.classname }}</h1>
        <p class="muted"><code>{{ item.classname }}</code></p>
        <div class="row">Category: {{ item.category or '-' }}</div>
        <div class="row">Subcategory: {{ item.subcategory or '-' }}</div>
        <div class="row">Buy price: {{ item.buy_price if item.buy_price is not none else 'unset' }}</div>
        <div class="row">Sell price: {{ item.sell_price if item.sell_price is not none else 'unset' }}</div>
        <div class="row">Enabled: {{ 'yes' if item.is_enabled else 'no' }}</div>
        <div class="row">Raw thumbnail URL: {{ item.thumbnail_url or 'none' }}</div>
        <div class="row">Metadata notes: <code>{{ item.notes or '{}' }}</code></div>

        <form method="post" action="/catalog/{{ item.classname }}/enabled">
          <input type="hidden" name="enabled" value="{{ '0' if item.is_enabled else '1' }}">
          <button type="submit">{{ 'Disable item' if item.is_enabled else 'Enable item' }}</button>
        </form>
      </div>
    </div>
  </div>
</body>
</html>
"""
