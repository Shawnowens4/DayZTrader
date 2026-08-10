from __future__ import annotations

from flask import Blueprint
from flask import abort
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from urllib.parse import urlencode

from shared.catalog.service import ADMIN_FUTURE_FLAG_KEYS
from shared.catalog.service import CATALOG_ADMIN_DEFAULT_LIMIT
from shared.catalog.service import bulk_set_catalog_review_required_sync
from shared.catalog.service import get_catalog_admin_item_sync
from shared.catalog.service import get_catalog_item_sync
from shared.catalog.service import list_catalog_categories_sync
from shared.catalog.service import search_catalog_admin_sync
from shared.catalog.service import search_catalog_sync
from shared.catalog.service import set_catalog_item_enabled_sync
from shared.catalog.service import update_catalog_admin_item_sync

catalog_bp = Blueprint("catalog", __name__)

PAGE_SIZE = 20
ADMIN_FILTER_FIELDS = [
    "q",
    "imported_state",
    "review_state",
    "enabled_state",
    "image_state",
    "warning_state",
    "imported_category",
    "imported_usage",
    "auto_trader_candidate",
    "direct_purchase_candidate",
    "rental_candidate",
    "bundle_candidate",
    "horde_event_candidate",
    "page",
    "limit",
]


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


@catalog_bp.get("/catalog/admin")
def catalog_admin_list():
    workspace = _catalog_admin_workspace_from_args(request.args)
    return render_template(
        "catalog_admin_list.html",
        **workspace,
        future_flag_labels=ADMIN_FUTURE_FLAG_KEYS,
        admin_message=(request.args.get("message", "") or "").strip(),
        admin_errors=[],
        auth_notice="Local admin tooling only. No real authentication or production authorization is implemented in this Flask app.",
    )


@catalog_bp.post("/catalog/admin/bulk-review")
def catalog_admin_bulk_review():
    desired_review_required = (request.form.get("bulk_action", "") or "").strip().lower() == "enable"
    filters = _catalog_admin_filters_from_form(request.form)
    filters["page"] = 1
    selected_classnames = request.form.getlist("selected_classnames")
    apply_to_filtered = (request.form.get("apply_to_filtered", "") or "").strip().lower() in {"1", "true", "yes", "on"}
    result = bulk_set_catalog_review_required_sync(
        desired_review_required=desired_review_required,
        confirmation=(request.form.get("confirmation", "") or "").strip(),
        filters=filters,
        selected_classnames=selected_classnames,
        apply_to_filtered=apply_to_filtered,
    )

    if result.get("ok"):
        action_label = "enabled" if desired_review_required else "disabled"
        params = _catalog_admin_redirect_params(filters, message=f"Review-required state {action_label} for {result['affected_count']} item(s).")
        return redirect(f"/catalog/admin?{urlencode(params, doseq=True)}")

    workspace = _catalog_admin_workspace_from_filters(filters)
    return (
        render_template(
            "catalog_admin_list.html",
            **workspace,
            future_flag_labels=ADMIN_FUTURE_FLAG_KEYS,
            admin_message="",
            admin_errors=result.get("errors", ["bulk review update failed"]),
            auth_notice="Local admin tooling only. No real authentication or production authorization is implemented in this Flask app.",
        ),
        int(result.get("status_code", 400)),
    )


@catalog_bp.get("/catalog/admin/<classname>")
def catalog_admin_detail(classname: str):
    item = get_catalog_admin_item_sync(classname)
    if item is None:
        abort(404, description="Catalog admin item not found")

    return render_template(
        "catalog_admin_detail.html",
        item=item,
        future_flag_labels=ADMIN_FUTURE_FLAG_KEYS,
        admin_message=(request.args.get("message", "") or "").strip(),
        admin_errors=[],
        auth_notice="Local admin tooling only. No real authentication or production authorization is implemented in this Flask app.",
    )


@catalog_bp.post("/catalog/admin/<classname>")
def catalog_admin_save(classname: str):
    payload = {
        key: request.form.getlist(key)[-1]
        for key in request.form.keys()
        if request.form.getlist(key)
    }
    result = update_catalog_admin_item_sync(classname, payload)
    if result.get("ok"):
        params = {"message": result["item"].get("last_change_note") or "Catalog curation saved."}
        return redirect(f"/catalog/admin/{classname}?{urlencode(params)}")

    item = result.get("item") or get_catalog_admin_item_sync(classname)
    if item is None:
        abort(404, description="Catalog admin item not found")

    return (
        render_template(
            "catalog_admin_detail.html",
            item=item,
            future_flag_labels=ADMIN_FUTURE_FLAG_KEYS,
            admin_message="",
            admin_errors=result.get("errors", ["save failed"]),
            auth_notice="Local admin tooling only. No real authentication or production authorization is implemented in this Flask app.",
        ),
        int(result.get("status_code", 400)),
    )


def _catalog_admin_workspace_from_args(args) -> dict:
    filters = {
        "query": (args.get("q", "") or "").strip(),
        "imported_state": (args.get("imported_state", "all") or "all").strip().lower(),
        "review_state": (args.get("review_state", "all") or "all").strip().lower(),
        "enabled_state": (args.get("enabled_state", "all") or "all").strip().lower(),
        "image_state": (args.get("image_state", "all") or "all").strip().lower(),
        "warning_state": (args.get("warning_state", "all") or "all").strip().lower(),
        "imported_category": (args.get("imported_category", "") or "").strip(),
        "imported_usage": (args.get("imported_usage", "") or "").strip(),
        "auto_trader_candidate": (args.get("auto_trader_candidate", "all") or "all").strip().lower(),
        "direct_purchase_candidate": (args.get("direct_purchase_candidate", "all") or "all").strip().lower(),
        "rental_candidate": (args.get("rental_candidate", "all") or "all").strip().lower(),
        "bundle_candidate": (args.get("bundle_candidate", "all") or "all").strip().lower(),
        "horde_event_candidate": (args.get("horde_event_candidate", "all") or "all").strip().lower(),
        "page": max(1, int(args.get("page", "1") or "1")),
        "limit": max(1, min(int(args.get("limit", str(CATALOG_ADMIN_DEFAULT_LIMIT)) or str(CATALOG_ADMIN_DEFAULT_LIMIT)), 50)),
    }
    return _catalog_admin_workspace_from_filters(filters)


def _catalog_admin_workspace_from_filters(filters: dict) -> dict:
    return search_catalog_admin_sync(
        query=filters["query"],
        imported_state=filters["imported_state"],
        review_state=filters["review_state"],
        enabled_state=filters["enabled_state"],
        image_state=filters["image_state"],
        warning_state=filters["warning_state"],
        imported_category=filters["imported_category"],
        imported_usage=filters["imported_usage"],
        auto_trader_candidate=filters["auto_trader_candidate"],
        direct_purchase_candidate=filters["direct_purchase_candidate"],
        rental_candidate=filters["rental_candidate"],
        bundle_candidate=filters["bundle_candidate"],
        horde_event_candidate=filters["horde_event_candidate"],
        page=filters["page"],
        limit=filters["limit"],
    )


def _catalog_admin_filters_from_form(form) -> dict:
    return {
        "query": (form.get("query", "") or "").strip(),
        "imported_state": (form.get("imported_state", "all") or "all").strip().lower(),
        "review_state": (form.get("review_state", "all") or "all").strip().lower(),
        "enabled_state": (form.get("enabled_state", "all") or "all").strip().lower(),
        "image_state": (form.get("image_state", "all") or "all").strip().lower(),
        "warning_state": (form.get("warning_state", "all") or "all").strip().lower(),
        "imported_category": (form.get("imported_category", "") or "").strip(),
        "imported_usage": (form.get("imported_usage", "") or "").strip(),
        "auto_trader_candidate": (form.get("auto_trader_candidate", "all") or "all").strip().lower(),
        "direct_purchase_candidate": (form.get("direct_purchase_candidate", "all") or "all").strip().lower(),
        "rental_candidate": (form.get("rental_candidate", "all") or "all").strip().lower(),
        "bundle_candidate": (form.get("bundle_candidate", "all") or "all").strip().lower(),
        "horde_event_candidate": (form.get("horde_event_candidate", "all") or "all").strip().lower(),
        "page": 1,
        "limit": max(1, min(int(form.get("limit", str(CATALOG_ADMIN_DEFAULT_LIMIT)) or str(CATALOG_ADMIN_DEFAULT_LIMIT)), 50)),
    }


def _catalog_admin_redirect_params(filters: dict, message: str = "") -> dict:
    params = {
        "q": filters.get("query", ""),
        "imported_state": filters.get("imported_state", "all"),
        "review_state": filters.get("review_state", "all"),
        "enabled_state": filters.get("enabled_state", "all"),
        "image_state": filters.get("image_state", "all"),
        "warning_state": filters.get("warning_state", "all"),
        "imported_category": filters.get("imported_category", ""),
        "imported_usage": filters.get("imported_usage", ""),
        "auto_trader_candidate": filters.get("auto_trader_candidate", "all"),
        "direct_purchase_candidate": filters.get("direct_purchase_candidate", "all"),
        "rental_candidate": filters.get("rental_candidate", "all"),
        "bundle_candidate": filters.get("bundle_candidate", "all"),
        "horde_event_candidate": filters.get("horde_event_candidate", "all"),
        "limit": filters.get("limit", CATALOG_ADMIN_DEFAULT_LIMIT),
    }
    if message:
        params["message"] = message
    return params
