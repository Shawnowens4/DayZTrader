from __future__ import annotations
# =============================================================
# DXEMB  shared/catalog/vehicle_builder_service.py  (A9)
# Shared service that wraps vehicle_resolver and returns
# builder-ready payloads for Flask admin pages and Discord cogs.
#
# Both Flask (sync) and Discord (async) consume the same output
# dict — no DB required at this layer.
# =============================================================

from typing import Any

from .vehicle_resolver import (
    get_vehicle_family,
    list_vehicle_families,
    resolve_vehicle_thumbnail,
    reload_resolver,
)
from .vehicle_family_catalog import resolve_vehicle_family_identity


def get_builder_catalog() -> list[dict[str, Any]]:
    """Return all vehicle families as card-ready list for admin selector.

    Each item contains everything needed to render a thumbnail card:
        classname, display_name, category, body_thumbnail_url,
        thumbnail_status, color_count, slot_count
    """
    families = list_vehicle_families()
    for family in families:
        identity = resolve_vehicle_family_identity(family.get("classname"))
        family["family_identity"] = {
            "canonical_key": identity.get("canonical_key") if identity else family.get("classname"),
            "display_name": identity.get("display_name") if identity else family.get("display_name"),
            "source_classname_prefixes": identity.get("source_classname_prefixes", []) if identity else [],
            "aliases": identity.get("aliases", []) if identity else [],
        }
    return families


def get_builder_payload(classname: str) -> dict[str, Any] | None:
    """Return full builder payload for one vehicle family.

    Returns None if family is not in the resolver.

    Payload shape:
    {
        classname: str,
        display_name: str,
        category: str,
        body_thumbnail_url: str,
        thumbnail_status: str,
        colors: [
            { color, display_name, thumbnail_url, thumbnail_status, classname }
        ],
        slots: [
            { slot_name, classname, display_name, required,
              thumbnail_url, thumbnail_status }
        ],
    }
    """
    payload = get_vehicle_family(classname)
    if not payload:
        return None
    identity = resolve_vehicle_family_identity(classname)
    payload["family_identity"] = {
        "canonical_key": identity.get("canonical_key") if identity else classname,
        "display_name": identity.get("display_name") if identity else payload.get("display_name"),
        "source_classname_prefixes": identity.get("source_classname_prefixes", []) if identity else [],
        "aliases": identity.get("aliases", []) if identity else [],
    }
    return payload


def resolve_thumbnail_for_card(
    classname: str,
    color: str | None = None,
) -> dict[str, str]:
    """Resolve thumbnail URL + status for a single vehicle card.

    Thin wrapper around vehicle_resolver.resolve_vehicle_thumbnail
    so callers don't need to import the resolver directly.
    """
    return resolve_vehicle_thumbnail(classname, color)


def get_color_options(classname: str) -> list[dict[str, Any]]:
    """Return just the color options for a vehicle family.

    Useful for Discord select menus where only the color step is needed.
    Returns [] if family is not found.
    """
    payload = get_vehicle_family(classname)
    if not payload:
        return []
    return payload.get("colors", [])


def get_slot_options(classname: str) -> list[dict[str, Any]]:
    """Return just the slot/part options for a vehicle family.

    Useful for Discord part-picker menus and trunk builder.
    Returns [] if family is not found.
    """
    payload = get_vehicle_family(classname)
    if not payload:
        return []
    return payload.get("slots", [])


def flush_resolver_cache() -> None:
    """Force resolver to reload from disk on next call.

    Call this after uploading a new vehicle_thumbnail_resolver.final.json
    or vehicle_overrides.json via the admin panel.
    """
    reload_resolver()
