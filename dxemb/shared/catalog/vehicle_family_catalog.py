from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "vehicle_family_catalog.json"


def _normalize_token(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def normalize_vehicle_family_token(value: str | None) -> str:
    return _normalize_token(value)


@lru_cache(maxsize=1)
def load_vehicle_family_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.exists():
        return {"families": []}
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        return {"families": []}
    families = payload.get("families")
    if not isinstance(families, list):
        return {"families": []}
    return payload


def clear_vehicle_family_catalog_cache() -> None:
    load_vehicle_family_catalog.cache_clear()
    _family_indexes.cache_clear()


def _list_families() -> list[dict[str, Any]]:
    payload = load_vehicle_family_catalog()
    out: list[dict[str, Any]] = []
    for row in payload.get("families", []):
        if isinstance(row, dict):
            out.append(row)
    return out


@lru_cache(maxsize=1)
def _family_indexes() -> tuple[list[tuple[str, dict[str, Any]]], dict[str, dict[str, Any]]]:
    prefix_index: list[tuple[str, dict[str, Any]]] = []
    token_index: dict[str, dict[str, Any]] = {}
    for family in _list_families():
        for prefix in family.get("source_classname_prefixes", []) or []:
            if isinstance(prefix, str) and prefix.strip():
                prefix_index.append((prefix.lower(), family))
        resolver_keys = family.get("resolver_family_keys", [])
        aliases = family.get("aliases", [])
        candidates = []
        if isinstance(aliases, list):
            candidates.extend(aliases)
        if isinstance(resolver_keys, list):
            candidates.extend(resolver_keys)
        candidates.append(family.get("canonical_key", ""))
        for candidate in candidates:
            normalized = _normalize_token(str(candidate))
            if normalized and normalized not in token_index:
                token_index[normalized] = family
    return prefix_index, token_index


def resolve_vehicle_family_identity(value: str | None) -> dict[str, Any] | None:
    raw = (value or "").strip()
    token = _normalize_token(raw)
    if not token:
        return None

    lowered = raw.lower()
    prefix_index, token_index = _family_indexes()
    for prefix, family in prefix_index:
        if lowered.startswith(prefix):
            out = dict(family)
            out["matched_by"] = "source_classname_prefix"
            out["matched_value"] = prefix
            return out

    family = token_index.get(token)
    if family:
        out = dict(family)
        out["matched_by"] = "alias"
        out["matched_value"] = token
        return out
    return None


def normalize_vehicle_family_key(value: str | None) -> str:
    identity = resolve_vehicle_family_identity(value)
    if identity:
        return str(identity.get("canonical_key", "")).strip() or _normalize_token(value)
    return _normalize_token(value)


def candidate_resolver_family_keys(value: str | None) -> list[str]:
    identity = resolve_vehicle_family_identity(value)
    if not identity:
        token = _normalize_token(value)
        return [token] if token else []

    resolver_keys = identity.get("resolver_family_keys", [])
    seen: set[str] = set()
    out: list[str] = []
    for key in resolver_keys if isinstance(resolver_keys, list) else []:
        k = str(key).strip()
        if k and k.lower() not in seen:
            out.append(k)
            seen.add(k.lower())
    canonical = str(identity.get("canonical_key", "")).strip()
    if canonical and canonical.lower() not in seen:
        out.append(canonical)
    return out
