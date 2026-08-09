from __future__ import annotations

from flask import Blueprint
from flask import abort
from flask import redirect
from flask import render_template
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

    return render_template(
        "catalog_list.html",
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

    return render_template("catalog_detail.html", item=item)


@catalog_bp.post("/catalog/<classname>/enabled")
def set_enabled(classname: str):
    raw = (request.form.get("enabled", "") or "").strip().lower()
    enabled = raw in {"1", "true", "yes", "on"}
    set_catalog_item_enabled_sync(classname, enabled)

    return_to = request.form.get("return_to", "") or ""
    if return_to:
        return redirect(return_to)
    return redirect(url_for("catalog.catalog_detail", classname=classname))
