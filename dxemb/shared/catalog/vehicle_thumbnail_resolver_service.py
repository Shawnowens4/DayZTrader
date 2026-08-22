from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .vehicle_family_catalog import (
    candidate_resolver_family_keys,
    normalize_vehicle_family_key,
    resolve_vehicle_family_identity,
)

ROOT = Path(__file__).resolve().parents[3]
RESOLVER_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "vehicle_thumbnail_resolver.final.json"

DEFAULT_SLOT_ORDER = [
    "hood",
    "driver_door",
    "codriver_door",
    "rear_left_door",
    "rear_right_door",
    "side_door",
    "trunk",
    "wheel",
]

COLOR_ALIASES = {
    "gray": "grey",
    "grey": "grey",
    "default": "default",
    "greenrust": "green",
    "bluerust": "blue",
    "orangerust": "orange",
    "blackrust": "black",
    "winerust": "wine",
    "greyrust": "grey",
    "redrust": "red",
    "whiterust": "white",
}

SLOT_ALIASES = {
    "hood": "hood",
    "bonnet": "hood",
    "driverdoor": "driver_door",
    "driver_door": "driver_door",
    "leftdoor": "driver_door",
    "frontleftdoor": "driver_door",
    "codriverdoor": "codriver_door",
    "co_driver_door": "codriver_door",
    "co-driverdoor": "codriver_door",
    "codriver_door": "codriver_door",
    "rightdoor": "codriver_door",
    "frontrightdoor": "codriver_door",
    "rearleftdoor": "rear_left_door",
    "rear_left_door": "rear_left_door",
    "rearrightdoor": "rear_right_door",
    "rear_right_door": "rear_right_door",
    "sidedoor": "side_door",
    "side_door": "side_door",
    "trunk": "trunk",
    "trunkdoor": "trunk",
    "trunklid": "trunk",
    "rear_door": "trunk",
    "wheel": "wheel",
}

VEHICLE_BODY_SLOT = "vehicle_body"


@dataclass(frozen=True)
class VehicleImageRef:
    family: str
    color: str
    slot: str
    image: str | None
    source: str | None
    fallback_used: bool
    matched_color: str | None = None
    has_exact_color_part: bool = False
    is_part_like_body: bool = False

    @property
    def exists(self) -> bool:
        return bool(self.image)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "color": self.color,
            "slot": self.slot,
            "image": self.image,
            "source": self.source,
            "fallback_used": self.fallback_used,
            "matched_color": self.matched_color,
            "has_exact_color_part": self.has_exact_color_part,
            "is_part_like_body": self.is_part_like_body,
        }


def _normalize_token(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9_+]+", "", value.strip().lower())


def normalize_family(value: str | None) -> str:
    return normalize_vehicle_family_key(value)


def normalize_color(value: str | None) -> str:
    token = _normalize_token(value)
    if not token:
        return "default"
    return COLOR_ALIASES.get(token, token)


def normalize_slot(value: str | None) -> str:
    token = _normalize_token(value)
    if token == VEHICLE_BODY_SLOT:
        return VEHICLE_BODY_SLOT
    return SLOT_ALIASES.get(token, token)


@lru_cache(maxsize=1)
def load_vehicle_thumbnail_resolver() -> dict[str, Any]:
    if not RESOLVER_PATH.exists():
        raise FileNotFoundError(f"Resolver file not found: {RESOLVER_PATH}")
    with RESOLVER_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def clear_vehicle_thumbnail_resolver_cache() -> None:
    load_vehicle_thumbnail_resolver.cache_clear()


def _get_family_entry(family: str) -> dict[str, Any] | None:
    resolver = load_vehicle_thumbnail_resolver()
    families = resolver.get("families", {})
    for key in candidate_resolver_family_keys(family):
        entry = families.get(key)
        if isinstance(entry, dict):
            return entry
    return families.get(family)


def _get_variant_entry(family: str, color: str) -> dict[str, Any] | None:
    family_entry = _get_family_entry(family)
    if not family_entry:
        return None

    variants = family_entry.get("variants", {})
    if color in variants:
        return variants[color]
    if "default" in variants:
        return variants["default"]
    if variants:
        first_key = next(iter(variants))
        return variants[first_key]
    return None


def list_vehicle_families() -> list[str]:
    resolver = load_vehicle_thumbnail_resolver()
    return sorted(resolver.get("families", {}).keys())


def list_family_colors(family: str) -> list[str]:
    family_key = normalize_family(family)
    family_entry = _get_family_entry(family_key)
    if not family_entry:
        return []
    return sorted(family_entry.get("variants", {}).keys())


def list_family_slots(family: str, include_vehicle_body: bool = True) -> list[str]:
    family_key = normalize_family(family)
    family_entry = _get_family_entry(family_key)
    if not family_entry:
        return [VEHICLE_BODY_SLOT] if include_vehicle_body else []

    slots = set()
    for variant in family_entry.get("variants", {}).values():
        slots.update(variant.get("slots", {}).keys())

    ordered = [slot for slot in DEFAULT_SLOT_ORDER if slot in slots]
    extras = sorted(slots - set(DEFAULT_SLOT_ORDER))

    if include_vehicle_body:
        return [VEHICLE_BODY_SLOT] + ordered + extras
    return ordered + extras


def get_vehicle_body(family: str, color: str | None = None) -> VehicleImageRef:
    family_key = normalize_family(family)
    color_key = normalize_color(color)
    variant = _get_variant_entry(family_key, color_key)

    if not variant:
        return VehicleImageRef(
            family=family_key,
            color=color_key,
            slot=VEHICLE_BODY_SLOT,
            image=None,
            source=None,
            fallback_used=True,
            matched_color=None,
            has_exact_color_part=False,
            is_part_like_body=False,
        )

    body = variant.get("vehicle_body", {})
    return VehicleImageRef(
        family=family_key,
        color=color_key,
        slot=VEHICLE_BODY_SLOT,
        image=body.get("image"),
        source=body.get("source"),
        fallback_used=bool(body.get("fallback_used", True)),
        matched_color=color_key,
        has_exact_color_part=False,
        is_part_like_body=bool(body.get("is_part_like_body", False)),
    )


def get_vehicle_slot_thumb(family: str, color: str | None, slot: str) -> VehicleImageRef:
    family_key = normalize_family(family)
    color_key = normalize_color(color)
    slot_key = normalize_slot(slot)

    if slot_key == VEHICLE_BODY_SLOT:
        return get_vehicle_body(family_key, color_key)

    variant = _get_variant_entry(family_key, color_key)
    if not variant:
        return VehicleImageRef(
            family=family_key,
            color=color_key,
            slot=slot_key,
            image=None,
            source=None,
            fallback_used=True,
            matched_color=None,
            has_exact_color_part=False,
            is_part_like_body=False,
        )

    slot_data = variant.get("slots", {}).get(slot_key, {})
    return VehicleImageRef(
        family=family_key,
        color=color_key,
        slot=slot_key,
        image=slot_data.get("image"),
        source=slot_data.get("source"),
        fallback_used=bool(slot_data.get("fallback_used", True)),
        matched_color=slot_data.get("matched_color"),
        has_exact_color_part=bool(slot_data.get("has_exact_color_part", False)),
        is_part_like_body=False,
    )


def is_exact_slot_thumb(family: str, color: str | None, slot: str) -> bool:
    ref = get_vehicle_slot_thumb(family, color, slot)
    return ref.has_exact_color_part


def uses_fallback_thumb(family: str, color: str | None, slot: str) -> bool:
    ref = get_vehicle_slot_thumb(family, color, slot)
    return ref.fallback_used


def get_vehicle_thumbnail_payload(family: str, color: str | None = None) -> dict[str, Any]:
    family_key = normalize_family(family)
    color_key = normalize_color(color)
    identity = resolve_vehicle_family_identity(family)

    body = get_vehicle_body(family_key, color_key)
    slots = {}

    for slot in list_family_slots(family_key, include_vehicle_body=False):
        ref = get_vehicle_slot_thumb(family_key, color_key, slot)
        slots[slot] = ref.to_dict()

    return {
        "family": family_key,
        "family_identity": {
            "canonical_key": identity.get("canonical_key") if identity else family_key,
            "display_name": identity.get("display_name") if identity else family_key,
            "source_classname_prefixes": identity.get("source_classname_prefixes", []) if identity else [],
            "aliases": identity.get("aliases", []) if identity else [],
        },
        "color": color_key,
        "body": body.to_dict(),
        "slots": slots,
        "available_colors": list_family_colors(family_key),
        "available_slots": list_family_slots(family_key, include_vehicle_body=False),
    }


def get_best_vehicle_card_image(family: str, color: str | None = None) -> str | None:
    return get_vehicle_body(family, color).image


def get_best_slot_image(family: str, color: str | None, slot: str) -> str | None:
    return get_vehicle_slot_thumb(family, color, slot).image