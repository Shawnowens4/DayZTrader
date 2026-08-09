from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "dxemb" / "shared" / "catalog" / "data"
DOCS_DIR = REPO_ROOT / "docs"
STATIC_DIR = REPO_ROOT / "dxemb" / "web" / "static"
REFERENCE_ITEMS_DIR = Path("C:/DXEMB/items")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}

PART_TOKENS = {
    "door",
    "wheel",
    "hood",
    "trunk",
    "tailgate",
    "radiator",
    "battery",
    "spark",
    "glow",
    "headlight",
    "plug",
}

EXCLUDED_TOKENS = {
    "wreck",
    "zmb",
    "animal_",
    "staticobj",
    "land_wreck",
    "prop",
    "arma",
    "mod",
    "workshop",
}

FAMILY_LABELS = {
    "civiliansedan": "Olga",
    "sedan_02": "Sarka",
    "offroad_02": "Gunter",
    "hatchback_02": "Ada 4x4",
    "truck_01": "M3S",
    "m1025": "Humvee",
    "uaz_452": "UAZ-452",
    "landrover": "Land Rover",
    "boat_01": "Boat",
    "offroadhatchback": "OffroadHatchback (resolver placeholder)",
}

REQUIRED_FAMILIES = [
    "hatchback_02",
    "offroad_02",
    "sedan_02",
    "civiliansedan",
    "truck_01",
    "m1025",
    "boat_01",
    "landrover",
    "uaz_452",
    "offroadhatchback",
    "v3s",
]

EVIDENCE_REVIEW_STATUSES = {
    "owner_confirmation_needed",
    "internally_consistent_no_console_provenance",
    "direct_console_proof_available",
    "unknown_or_missing",
}

DEFAULT_EVIDENCE_RECORD = {
    "source_type": "unverified",
    "source_path": "",
    "source_vehicle_type": "",
    "evidence_excerpt_locator": "",
    "reviewed_by": "",
    "review_status": "owner_confirmation_needed",
}


@dataclass
class VariantCoverage:
    family_key: str
    variant: str
    coverage: str
    body_candidates: list[str]
    evidence_state: str
    evidence_paths: list[str]


@dataclass
class QueueEntry:
    vehicle_family: str
    vehicle_label: str
    variant: str
    review_stage: str
    relationship: str
    observed_classname: str
    root_cause: str
    evidence_state: str
    evidence_paths: list[str]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_text_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def _list_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted([p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS])


def _stem(path: str) -> str:
    return Path(path).stem.lower()


def classify_image_role_from_stem(stem: str) -> str:
    lower = stem.lower()
    if any(token in lower for token in EXCLUDED_TOKENS):
        return "excluded"
    if any(token in lower for token in PART_TOKENS):
        return "part_only"
    return "vehicle_or_item"


def slot_group(slot_name: str) -> str:
    s = slot_name.lower().strip()
    if "wheel" in s:
        return "wheels"
    if "door" in s:
        return "doors"
    if "hood" in s:
        return "hood"
    if "trunk" in s or "tail" in s:
        return "trunk/tailgate"
    if "headlight" in s or "light" in s:
        return "headlights"
    if "battery" in s:
        return "battery"
    if "radiator" in s:
        return "radiator"
    if "spark" in s:
        return "spark plug"
    if "glow" in s:
        return "glow plug"
    if "cargo" in s:
        return "cargo"
    return "other"


def review_stage_for_slot(variant_name: str, slot_name: str) -> str:
    slot = slot_name.lower()
    if "cargo" in slot:
        return "special_cargo_slots"
    if variant_name != "default":
        return "color_parts"
    return "required_parts"


def _extract_local_image_names(repo_images: list[Path]) -> set[str]:
    return {p.name.lower() for p in repo_images}


def _normalize_vehicle_key(name: str) -> str:
    return name.lower().replace("-", "_")


def _source_evidence_record(
    source_type: str,
    source_path: str,
    source_vehicle_type: str,
    locator: str,
    review_status: str,
) -> dict[str, str]:
    if review_status not in EVIDENCE_REVIEW_STATUSES:
        raise ValueError(f"invalid review status {review_status}")
    return {
        "source_type": source_type,
        "source_path": source_path,
        "source_vehicle_type": source_vehicle_type,
        "evidence_excerpt_locator": locator,
        "reviewed_by": "",
        "review_status": review_status,
    }


def build_variant_coverage(
    variant_manifest: dict[str, Any],
    resolver_final: dict[str, Any],
    map_data: dict[str, str],
    local_image_names: set[str],
) -> list[VariantCoverage]:
    rows: list[VariantCoverage] = []
    map_keys = {k.lower() for k in map_data.keys()}

    families = variant_manifest.get("families", {})
    for family_key, family_data in families.items():
        variants = family_data.get("variants", {})
        for variant_name, variant_data in variants.items():
            body_candidates = [name.lower() for name in variant_data.get("vehicle_images", [])]

            exact_local = any(name in local_image_names for name in body_candidates)
            if exact_local:
                rows.append(
                    VariantCoverage(
                        family_key=family_key,
                        variant=variant_name,
                        coverage="exact_local_image",
                        evidence_state="owner_confirmation_needed",
                        body_candidates=body_candidates,
                        evidence_paths=["dxemb/web/static/catalog_items", "dxemb/web/static/ui"],
                    )
                )
                continue

            resolver_entry = resolver_final.get(family_key) or resolver_final.get(family_key.capitalize())
            family_has_resolver = isinstance(resolver_entry, dict) and bool(resolver_entry.get("body_thumbnail"))
            family_has_parts = bool(variant_data.get("parts", {}))
            body_map_match = any(_stem(candidate) in map_keys for candidate in body_candidates)

            if family_has_resolver and family_has_parts:
                rows.append(
                    VariantCoverage(
                        family_key=family_key,
                        variant=variant_name,
                        coverage="generic_fallback_only",
                        evidence_state="internally_consistent_no_console_provenance",
                        body_candidates=body_candidates,
                        evidence_paths=[
                            "dxemb/shared/catalog/data/vehicle_variant_manifest.json",
                            "dxemb/shared/catalog/data/vehicle_thumbnail_resolver.final.json",
                        ],
                    )
                )
                continue

            if body_map_match:
                rows.append(
                    VariantCoverage(
                        family_key=family_key,
                        variant=variant_name,
                        coverage="generic_fallback_only",
                        evidence_state="owner_confirmation_needed",
                        body_candidates=body_candidates,
                        evidence_paths=["dxemb/shared/catalog/data/dayzidb_map.json"],
                    )
                )
                continue

            rows.append(
                VariantCoverage(
                    family_key=family_key,
                    variant=variant_name,
                    coverage="missing",
                    evidence_state="unknown_or_missing",
                    body_candidates=body_candidates,
                    evidence_paths=[],
                )
            )

    return rows


def _build_boat_entries(map_data: dict[str, str]) -> tuple[list[dict[str, Any]], list[QueueEntry]]:
    variants: list[dict[str, Any]] = []
    queue: list[QueueEntry] = []
    boat_keys = sorted([k for k in map_data.keys() if k.startswith("boat_01")])

    for key in boat_keys:
        variant_name = key.replace("boat_01_", "") or "default"
        variants.append(
            {
                "variant": variant_name,
                "console_classname": key,
                "approved_status": "owner_review_required",
                "selection_state": "blocked",
                "body_image_coverage": "generic_fallback_only",
                "part_image_coverage": "missing",
                "confidence": "owner_review_required",
                "evidence_records": [
                    _source_evidence_record(
                        source_type="project_map",
                        source_path="dxemb/shared/catalog/data/dayzidb_map.json",
                        source_vehicle_type="boat_01",
                        locator=f"key:{key}",
                        review_status="owner_confirmation_needed",
                    )
                ],
            }
        )
        queue.append(
            QueueEntry(
                vehicle_family="boat_01",
                vehicle_label="Boat",
                variant=variant_name,
                review_stage="whole_vehicle",
                relationship="body_thumbnail",
                observed_classname=_stem(map_data.get(key, "")),
                root_cause="vehicle key is visible in project map but console mission proof is not attached",
                evidence_state="owner_confirmation_needed",
                evidence_paths=["dxemb/shared/catalog/data/dayzidb_map.json"],
            )
        )

    return variants, queue


def _append_image_gap_entries(
    queue: list[QueueEntry],
    display_name: str,
    family_key: str,
    variant_name: str,
    coverage: VariantCoverage | None,
) -> None:
    if coverage is None:
        return
    if coverage.coverage == "exact_local_image":
        return

    queue.append(
        QueueEntry(
            vehicle_family=family_key,
            vehicle_label=display_name,
            variant=variant_name,
            review_stage="image_only_gaps",
            relationship="body_image",
            observed_classname=", ".join([_stem(c) for c in coverage.body_candidates]) or "none",
            root_cause="body image is fallback-only until owner supplies console provenance and approved local image",
            evidence_state=coverage.evidence_state,
            evidence_paths=coverage.evidence_paths,
        )
    )


def _queue_to_json_row(entry: QueueEntry) -> dict[str, Any]:
    return {
        "vehicle_family": entry.vehicle_family,
        "vehicle": entry.vehicle_label,
        "variant": entry.variant,
        "review_stage": entry.review_stage,
        "relationship": entry.relationship,
        "observed_classname": entry.observed_classname,
        "root_cause": entry.root_cause,
        "evidence_state": entry.evidence_state,
        "evidence_records": [
            _source_evidence_record(
                source_type="project_artifact",
                source_path=path,
                source_vehicle_type=entry.vehicle_family,
                locator=f"variant:{entry.variant};relationship:{entry.relationship}",
                review_status=entry.evidence_state,
            )
            for path in entry.evidence_paths
        ]
        or [
            _source_evidence_record(
                source_type="missing",
                source_path="",
                source_vehicle_type=entry.vehicle_family,
                locator=f"variant:{entry.variant};relationship:{entry.relationship}",
                review_status="unknown_or_missing",
            )
        ],
        "choices": ["approve", "correct", "exclude", "attach_console_evidence"],
    }


def build_vehicle_compatibility(
    variant_manifest: dict[str, Any],
    resolver_final: dict[str, Any],
    map_data: dict[str, str],
    excluded_classnames: set[str],
    coverage_rows: list[VariantCoverage],
) -> dict[str, Any]:
    families = variant_manifest.get("families", {})
    coverage_index = {(row.family_key, row.variant): row for row in coverage_rows}

    vehicles: list[dict[str, Any]] = []
    queue_raw: list[QueueEntry] = []

    for family_key in sorted(set(REQUIRED_FAMILIES + list(families.keys()))):
        normalized = _normalize_vehicle_key(family_key)
        family_data = families.get(family_key)
        resolver_data = resolver_final.get(family_key)

        if normalized in {"v3s", "vs3"}:
            vehicles.append(
                {
                    "family_key": family_key,
                    "display_name": "V3S / VS3",
                    "approved_status": "excluded",
                    "selection_state": "blocked",
                    "reason": "future_or_unverified_content",
                    "confidence": "owner_review_required",
                    "variants": [],
                    "attachments": {},
                    "cargo_rules": [],
                    "evidence_records": [
                        _source_evidence_record(
                            source_type="policy",
                            source_path="owner_policy",
                            source_vehicle_type="v3s",
                            locator="exclude_future_content",
                            review_status="owner_confirmation_needed",
                        )
                    ],
                }
            )
            continue

        if family_key == "boat_01":
            variants, boat_queue = _build_boat_entries(map_data)
            queue_raw.extend(boat_queue)
            vehicles.append(
                {
                    "family_key": family_key,
                    "display_name": "Boat",
                    "approved_status": "owner_review_required",
                    "selection_state": "blocked",
                    "confidence": "owner_review_required",
                    "variants": variants,
                    "attachments": {},
                    "cargo_rules": [],
                    "evidence_records": [
                        _source_evidence_record(
                            source_type="project_map",
                            source_path="dxemb/shared/catalog/data/dayzidb_map.json",
                            source_vehicle_type="boat_01",
                            locator="prefix:boat_01",
                            review_status="owner_confirmation_needed",
                        )
                    ],
                }
            )
            continue

        if family_data is None and resolver_data is None:
            vehicles.append(
                {
                    "family_key": family_key,
                    "display_name": FAMILY_LABELS.get(family_key, family_key),
                    "approved_status": "owner_review_required",
                    "selection_state": "blocked",
                    "reason": "missing_family_data",
                    "confidence": "unknown_or_missing",
                    "variants": [],
                    "attachments": {},
                    "cargo_rules": [],
                    "evidence_records": [
                        _source_evidence_record(
                            source_type="missing",
                            source_path="",
                            source_vehicle_type=family_key,
                            locator="family_missing",
                            review_status="unknown_or_missing",
                        )
                    ],
                }
            )
            queue_raw.append(
                QueueEntry(
                    vehicle_family=family_key,
                    vehicle_label=FAMILY_LABELS.get(family_key, family_key),
                    variant="default",
                    review_stage="whole_vehicle",
                    relationship="family_presence",
                    observed_classname="missing",
                    root_cause="family is absent from both manifest and resolver",
                    evidence_state="unknown_or_missing",
                    evidence_paths=[],
                )
            )
            continue

        display_name = FAMILY_LABELS.get(family_key, str((family_data or {}).get("label") or family_key))
        variants_out: list[dict[str, Any]] = []
        slots_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)

        fam_variants = (family_data or {}).get("variants", {})
        for variant_name, variant_data in fam_variants.items():
            coverage = coverage_index.get((family_key, variant_name))
            coverage_label = coverage.coverage if coverage else "missing"
            evidence_state = coverage.evidence_state if coverage else "unknown_or_missing"

            variants_out.append(
                {
                    "variant": variant_name,
                    "console_classname": family_key,
                    "approved_status": "owner_review_required",
                    "selection_state": "blocked",
                    "body_image_coverage": coverage_label,
                    "part_image_coverage": "part_only" if variant_data.get("parts", {}) else "missing",
                    "confidence": evidence_state,
                    "evidence_records": [
                        _source_evidence_record(
                            source_type="project_manifest",
                            source_path="dxemb/shared/catalog/data/vehicle_variant_manifest.json",
                            source_vehicle_type=family_key,
                            locator=f"family:{family_key};variant:{variant_name}",
                            review_status="internally_consistent_no_console_provenance",
                        )
                    ],
                }
            )

            queue_raw.append(
                QueueEntry(
                    vehicle_family=family_key,
                    vehicle_label=display_name,
                    variant=variant_name,
                    review_stage="whole_vehicle",
                    relationship="variant_eligibility",
                    observed_classname=family_key,
                    root_cause="variant exists in project manifest but console source files are not attached",
                    evidence_state=evidence_state,
                    evidence_paths=["dxemb/shared/catalog/data/vehicle_variant_manifest.json"],
                )
            )

            color_part_map = variant_data.get("parts", {})
            for slot_name, part_files in color_part_map.items():
                group = slot_group(slot_name)
                for part_file in sorted(set(part_files)):
                    part_classname = _stem(part_file)
                    stage = review_stage_for_slot(variant_name, slot_name)
                    slots_by_group[group].append(
                        {
                            "slot": slot_name,
                            "variant": variant_name,
                            "part_classname": part_classname,
                            "approved_status": "owner_review_required",
                            "selection_state": "blocked",
                            "confidence": "internally_consistent_no_console_provenance",
                            "evidence_records": [
                                _source_evidence_record(
                                    source_type="project_manifest",
                                    source_path="dxemb/shared/catalog/data/vehicle_variant_manifest.json",
                                    source_vehicle_type=family_key,
                                    locator=f"family:{family_key};variant:{variant_name};slot:{slot_name}",
                                    review_status="internally_consistent_no_console_provenance",
                                )
                            ],
                        }
                    )
                    queue_raw.append(
                        QueueEntry(
                            vehicle_family=family_key,
                            vehicle_label=display_name,
                            variant=variant_name,
                            review_stage=stage,
                            relationship=slot_name,
                            observed_classname=part_classname,
                            root_cause="slot mapping comes from project manifest and needs owner console evidence",
                            evidence_state="internally_consistent_no_console_provenance",
                            evidence_paths=["dxemb/shared/catalog/data/vehicle_variant_manifest.json"],
                        )
                    )

            _append_image_gap_entries(queue_raw, display_name, family_key, variant_name, coverage)

        vehicles.append(
            {
                "family_key": family_key,
                "display_name": display_name,
                "approved_status": "owner_review_required",
                "selection_state": "blocked",
                "confidence": "owner_review_required",
                "variants": variants_out,
                "attachments": dict(slots_by_group),
                "cargo_rules": [
                    {
                        "rule": "Not available until console compatibility is verified.",
                        "approved_status": "owner_review_required",
                        "selection_state": "blocked",
                        "confidence": "owner_review_required",
                        "evidence_records": [
                            _source_evidence_record(
                                source_type="policy",
                                source_path="owner_policy",
                                source_vehicle_type=family_key,
                                locator="fail_closed_default",
                                review_status="owner_confirmation_needed",
                            )
                        ],
                    }
                ],
                "evidence_records": [
                    _source_evidence_record(
                        source_type="project_manifest",
                        source_path="dxemb/shared/catalog/data/vehicle_variant_manifest.json",
                        source_vehicle_type=family_key,
                        locator=f"family:{family_key}",
                        review_status="internally_consistent_no_console_provenance",
                    )
                ],
            }
        )

    # Deduplicate raw queue but keep every unresolved classname represented at least once.
    seen = set()
    deduped_raw: list[QueueEntry] = []
    for row in queue_raw:
        key = (
            row.vehicle_family,
            row.variant,
            row.review_stage,
            row.relationship,
            row.observed_classname,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped_raw.append(row)

    queue_grouped = _group_queue_rows(deduped_raw)
    unresolved_classnames = sorted({row.observed_classname for row in deduped_raw if row.observed_classname and row.observed_classname != "missing"})

    summary = {
        "approved_total": 0,
        "owner_review_required_total": sum(1 for v in vehicles if v["approved_status"] == "owner_review_required"),
        "excluded_total": sum(1 for v in vehicles if v["approved_status"] == "excluded"),
        "review_rows_raw": len(deduped_raw),
        "review_rows_grouped": len(queue_grouped),
    }

    return {
        "schema_version": "1.1",
        "scope": "xbox_playstation_console_only",
        "fail_closed_message": "Not available until console compatibility is verified.",
        "policy": {
            "selection_rule": "approved vehicle AND explicit slot mapping AND explicit variant mapping AND approved status",
            "default_for_uncertain": "owner_review_required",
            "do_not_infer": [
                "image_names",
                "generic_resolver_guesses",
                "archive_javascript",
                "generic_vehicle_family_aliases",
                "color_suffixes",
            ],
        },
        "evidence_record_template": DEFAULT_EVIDENCE_RECORD,
        "sources": {
            "dayz_map": "dxemb/shared/catalog/data/dayzidb_map.json",
            "resolver": "dxemb/shared/catalog/data/vehicle_thumbnail_resolver.final.json",
            "variant_manifest": "dxemb/shared/catalog/data/vehicle_variant_manifest.json",
            "excluded_classnames": "dxemb/shared/catalog/data/excluded_classnames.txt",
            "reference_images": "C:/DXEMB/items",
            "owner_console_reference_dir": "local_console_reference/",
        },
        "summary": summary,
        "vehicles": vehicles,
        "owner_review": {
            "grouped": queue_grouped,
            "raw": [_queue_to_json_row(row) for row in deduped_raw],
            "unresolved_classnames": unresolved_classnames,
            "source_files_needed": [
                "types.xml",
                "cfgspawnabletypes.xml",
                "events.xml",
                "cfgeventspawns.xml",
                "mission files (if owner already has current Xbox/PlayStation copies)",
            ],
        },
        "excluded_classname_count": len(excluded_classnames),
    }


def _group_queue_rows(rows: list[QueueEntry]) -> list[dict[str, Any]]:
    stage_order = {
        "whole_vehicle": 0,
        "required_parts": 1,
        "color_parts": 2,
        "special_cargo_slots": 3,
        "image_only_gaps": 4,
    }
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}

    for row in rows:
        key = (row.vehicle_family, row.review_stage, row.relationship)
        if row.review_stage == "color_parts":
            key = (row.vehicle_family, row.review_stage, f"{row.relationship}:{row.variant}")

        item = grouped.get(key)
        if item is None:
            item = {
                "vehicle_family": row.vehicle_family,
                "vehicle": row.vehicle_label,
                "review_stage": row.review_stage,
                "relationship": row.relationship,
                "variants": set(),
                "classnames": set(),
                "root_causes": set(),
                "evidence_states": set(),
                "evidence_paths": set(),
            }
            grouped[key] = item

        item["variants"].add(row.variant)
        item["classnames"].add(row.observed_classname)
        item["root_causes"].add(row.root_cause)
        item["evidence_states"].add(row.evidence_state)
        for path in row.evidence_paths:
            item["evidence_paths"].add(path)

    out: list[dict[str, Any]] = []
    for item in grouped.values():
        out.append(
            {
                "vehicle_family": item["vehicle_family"],
                "vehicle": item["vehicle"],
                "review_stage": item["review_stage"],
                "relationship": item["relationship"],
                "variants": sorted(item["variants"]),
                "unresolved_classnames": sorted([c for c in item["classnames"] if c and c != "missing"]),
                "root_causes": sorted(item["root_causes"]),
                "evidence_states": sorted(item["evidence_states"]),
                "evidence_paths": sorted(item["evidence_paths"]),
                "choices": ["approve", "correct", "exclude", "attach_console_evidence"],
            }
        )

    return sorted(out, key=lambda x: (x["vehicle_family"], stage_order.get(x["review_stage"], 9), x["relationship"]))


def _coverage_totals(coverage_rows: list[VariantCoverage]) -> dict[str, int]:
    totals = {
        "exact_local_image": 0,
        "family_fallback_only": 0,
        "generic_fallback_only": 0,
        "missing": 0,
        "part_only": 0,
        "excluded": 0,
    }
    for row in coverage_rows:
        totals[row.coverage] = totals.get(row.coverage, 0) + 1
    return totals


def _coverage_evidence_state_totals(coverage_rows: list[VariantCoverage]) -> dict[str, int]:
    totals = {
        "owner_confirmation_needed": 0,
        "internally_consistent_no_console_provenance": 0,
        "direct_console_proof_available": 0,
        "unknown_or_missing": 0,
    }
    for row in coverage_rows:
        totals[row.evidence_state] = totals.get(row.evidence_state, 0) + 1
    return totals


def _image_classification_totals(image_paths: list[Path]) -> dict[str, int]:
    totals = {
        "part_only": 0,
        "excluded": 0,
        "vehicle_or_item": 0,
    }
    for path in image_paths:
        role = classify_image_role_from_stem(path.stem)
        totals[role] += 1
    return totals


def _render_variant_table(coverage_rows: list[VariantCoverage]) -> str:
    lines = [
        "| Family | Variant | Coverage | Evidence State | Body Candidates | Evidence Paths |",
        "|---|---|---|---|---|---|",
    ]
    for row in sorted(coverage_rows, key=lambda x: (x.family_key, x.variant)):
        lines.append(
            "| {family} | {variant} | {coverage} | {state} | {candidates} | {paths} |".format(
                family=row.family_key,
                variant=row.variant,
                coverage=row.coverage,
                state=row.evidence_state,
                candidates=", ".join(row.body_candidates) or "-",
                paths=", ".join(row.evidence_paths) or "-",
            )
        )
    return "\n".join(lines)


def _render_owner_queue_md(grouped_rows: list[dict[str, Any]], raw_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# CONSOLE_VEHICLE_OWNER_REVIEW_QUEUE",
        "",
        "Front section is collapsed and actionable. Appendix preserves every unresolved classname row.",
        "",
        "## Checklist By Priority",
        "",
        "| Priority | Vehicle | Stage | Relationship | Variants | Unresolved Classnames | Root Cause | Evidence States |",
        "|---|---|---|---|---|---|---|---|",
    ]

    stage_priority = {
        "whole_vehicle": "1-whole_vehicle",
        "required_parts": "2-required_parts",
        "color_parts": "3-color_parts",
        "special_cargo_slots": "4-special_cargo_slots",
        "image_only_gaps": "5-image_only_gaps",
    }

    for row in sorted(grouped_rows, key=lambda r: (r["vehicle_family"], stage_priority.get(r["review_stage"], "9"), r["relationship"])):
        lines.append(
            "| {priority} | {vehicle} | {stage} | {relationship} | {variants} | {classnames} | {cause} | {states} |".format(
                priority=stage_priority.get(row["review_stage"], "9-other"),
                vehicle=row["vehicle"],
                stage=row["review_stage"],
                relationship=row["relationship"],
                variants=", ".join(row["variants"]),
                classnames=", ".join(row["unresolved_classnames"]) or "none",
                cause="; ".join(row["root_causes"]),
                states=", ".join(row["evidence_states"]),
            )
        )

    lines.extend(
        [
            "",
            "## Appendix: Full Unresolved Rows",
            "",
            "| Vehicle Family | Vehicle | Variant | Stage | Relationship | Observed Classname | Root Cause | Evidence State | Evidence Paths |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )

    for row in raw_rows:
        lines.append(
            "| {family} | {vehicle} | {variant} | {stage} | {relationship} | {classname} | {cause} | {state} | {paths} |".format(
                family=row["vehicle_family"],
                vehicle=row["vehicle"],
                variant=row["variant"],
                stage=row["review_stage"],
                relationship=row["relationship"],
                classname=row["observed_classname"],
                cause=row["root_cause"],
                state=row["evidence_state"],
                paths=", ".join(rec.get("source_path", "") for rec in row["evidence_records"] if rec.get("source_path")) or "-",
            )
        )

    return "\n".join(lines) + "\n"


def _render_image_audit_md(
    map_data: dict[str, str],
    resolver_final: dict[str, Any],
    variant_manifest: dict[str, Any],
    repo_images: list[Path],
    corpus_images: list[Path],
    coverage_rows: list[VariantCoverage],
    coverage_totals: dict[str, int],
    coverage_states: dict[str, int],
    repo_roles: dict[str, int],
    corpus_roles: dict[str, int],
    compat: dict[str, Any],
) -> str:
    families = variant_manifest.get("families", {})
    variant_total = sum(len((f.get("variants") or {})) for f in families.values())

    lines = [
        "# DAYZ_IMAGE_AND_VEHICLE_VARIANT_AUDIT",
        "",
        "Scope: Xbox/PlayStation vanilla console only. No PC/mod/Arma/workshop/future content is approved.",
        "",
        "## Reproducible Inventory Instructions",
        "",
        "1. Run: python dxemb/shared/catalog/tools/audit_console_vehicle_assets.py",
        "2. Read generated files in docs/ and dxemb/shared/catalog/data/.",
        "3. No image copying/downloading is performed by this audit.",
        "",
        "## Numeric Totals",
        "",
        f"- catalog classnames: {len(map_data)}",
        f"- vehicle families (variant manifest): {len(families)}",
        f"- vehicle families (resolver final): {len([k for k in resolver_final.keys() if k != '__note__'])}",
        f"- vehicle variants (variant manifest): {variant_total}",
        f"- repository local images: {len(repo_images)}",
        f"- reference corpus images (C:/DXEMB/items): {len(corpus_images)}",
        f"- exact_local_image: {coverage_totals.get('exact_local_image', 0)}",
        f"- family_fallback_only: {coverage_totals.get('family_fallback_only', 0)}",
        f"- generic_fallback_only: {coverage_totals.get('generic_fallback_only', 0)}",
        f"- missing: {coverage_totals.get('missing', 0)}",
        f"- evidence owner_confirmation_needed: {coverage_states.get('owner_confirmation_needed', 0)}",
        f"- evidence internally_consistent_no_console_provenance: {coverage_states.get('internally_consistent_no_console_provenance', 0)}",
        f"- evidence direct_console_proof_available: {coverage_states.get('direct_console_proof_available', 0)}",
        f"- evidence unknown_or_missing: {coverage_states.get('unknown_or_missing', 0)}",
        f"- part_only images (repo): {repo_roles.get('part_only', 0)}",
        f"- part_only images (reference corpus): {corpus_roles.get('part_only', 0)}",
        f"- excluded images (repo): {repo_roles.get('excluded', 0)}",
        f"- excluded images (reference corpus): {corpus_roles.get('excluded', 0)}",
        "",
        "## Source Paths",
        "",
        "- dxemb/shared/catalog/data/dayzidb_map.json",
        "- dxemb/shared/catalog/data/vehicle_thumbnail_resolver.final.json",
        "- dxemb/shared/catalog/data/vehicle_variant_manifest.json",
        "- dxemb/shared/catalog/data/excluded_classnames.txt",
        "- dxemb/web/static/catalog_items",
        "- dxemb/web/static/ui",
        "- C:/DXEMB/items (read-only reference corpus)",
        "",
        "## Vehicle Color/Variant Coverage",
        "",
        _render_variant_table(coverage_rows),
        "",
        "## Wrong/Mixed/Missing Color Mapping Findings",
        "",
        "- OffroadHatchback in resolver final is a placeholder family unrelated to full console family manifest coverage.",
        "- truck_01 manifest variants include mixed labels (red+blue, red+orange) that need owner verification before exposure.",
        "- sedan_02 default variant has missing codriver_door mapping in manifest completeness metadata.",
        "- resolver final currently contains only 3 concrete families plus note placeholder; this is incomplete against variant manifest.",
        "",
        "## Evidence Maturity Interpretation",
        "",
        "- owner_confirmation_needed: source exists in project artifacts but console-owned XML/mission evidence is not attached.",
        "- internally_consistent_no_console_provenance: variant and slot structure is internally coherent across manifest/resolver, but still unproven for console rules.",
        "- direct_console_proof_available: reserved for owner-attached console files proving exact vehicle-to-slot rule (none present in this run).",
        "- unknown_or_missing: source is absent or contradictory in current local project artifacts.",
        "",
        "## Candidate Corrections (CANDIDATE ONLY, NOT APPLIED)",
        "",
        "- Replace placeholder resolver entries with reviewed console-only family/classname/color set from compatibility review JSON.",
        "- Normalize family keys to manifest-backed keys after owner supplies console XML evidence.",
        "- Keep all uncertain rows blocked until evidence records are populated and reviewed.",
        "",
        "## Review Queue Totals",
        "",
        f"- grouped checklist rows: {compat['summary']['review_rows_grouped']}",
        f"- raw unresolved rows: {compat['summary']['review_rows_raw']}",
    ]

    return "\n".join(lines) + "\n"


def _render_compatibility_md(compat: dict[str, Any]) -> str:
    vehicles = compat["vehicles"]
    summary = compat["summary"]

    lines = [
        "# CONSOLE_VEHICLE_COMPATIBILITY_MATRIX",
        "",
        "Fail-closed policy: selection is blocked unless vehicle + slot + variant mapping are explicitly approved.",
        "",
        "## Totals",
        "",
        f"- approved: {summary['approved_total']}",
        f"- owner_review_required: {summary['owner_review_required_total']}",
        f"- excluded: {summary['excluded_total']}",
        f"- review_rows_grouped: {summary['review_rows_grouped']}",
        f"- review_rows_raw: {summary['review_rows_raw']}",
        "",
        "## Vehicle Family Matrix",
        "",
        "| Family | Display Name | Status | Confidence | Variant Count |",
        "|---|---|---|---|---|",
    ]

    for vehicle in vehicles:
        lines.append(
            "| {family} | {display} | {status} | {confidence} | {count} |".format(
                family=vehicle["family_key"],
                display=vehicle.get("display_name", vehicle["family_key"]),
                status=vehicle["approved_status"],
                confidence=vehicle.get("confidence", "owner_review_required"),
                count=len(vehicle.get("variants", [])),
            )
        )

    lines.extend(
        [
            "",
            "## Evidence Rule Summary",
            "",
            "- source exists but needs owner confirmation: owner_confirmation_needed",
            "- internally consistent but lacks console provenance: internally_consistent_no_console_provenance",
            "- source directly proves vehicle-to-part rule: direct_console_proof_available",
            "- unknown/missing: unknown_or_missing",
            "",
            "## Builder Consumption Rule",
            "",
            "The future vehicle builder must consume only console_vehicle_compatibility.review.json and fail closed.",
            "Default message: Not available until console compatibility is verified.",
        ]
    )

    return "\n".join(lines) + "\n"


def run_audit() -> dict[str, Any]:
    map_data = _load_json(DATA_DIR / "dayzidb_map.json")
    resolver_final = _load_json(DATA_DIR / "vehicle_thumbnail_resolver.final.json")
    variant_manifest = _load_json(DATA_DIR / "vehicle_variant_manifest.json")
    excluded_classnames = set(_load_text_lines(DATA_DIR / "excluded_classnames.txt"))

    repo_images = _list_images(STATIC_DIR)
    corpus_images = _list_images(REFERENCE_ITEMS_DIR)

    local_image_names = _extract_local_image_names(repo_images)
    coverage_rows = build_variant_coverage(variant_manifest, resolver_final, map_data, local_image_names)
    coverage_totals = _coverage_totals(coverage_rows)
    coverage_states = _coverage_evidence_state_totals(coverage_rows)

    repo_roles = _image_classification_totals(repo_images)
    corpus_roles = _image_classification_totals(corpus_images)

    compat = build_vehicle_compatibility(
        variant_manifest=variant_manifest,
        resolver_final=resolver_final,
        map_data=map_data,
        excluded_classnames=excluded_classnames,
        coverage_rows=coverage_rows,
    )

    image_audit_md = _render_image_audit_md(
        map_data=map_data,
        resolver_final=resolver_final,
        variant_manifest=variant_manifest,
        repo_images=repo_images,
        corpus_images=corpus_images,
        coverage_rows=coverage_rows,
        coverage_totals=coverage_totals,
        coverage_states=coverage_states,
        repo_roles=repo_roles,
        corpus_roles=corpus_roles,
        compat=compat,
    )

    compatibility_md = _render_compatibility_md(compat)
    owner_queue_md = _render_owner_queue_md(compat["owner_review"]["grouped"], compat["owner_review"]["raw"])

    outputs = {
        DOCS_DIR / "DAYZ_IMAGE_AND_VEHICLE_VARIANT_AUDIT.md": image_audit_md,
        DOCS_DIR / "CONSOLE_VEHICLE_COMPATIBILITY_MATRIX.md": compatibility_md,
        DOCS_DIR / "CONSOLE_VEHICLE_OWNER_REVIEW_QUEUE.md": owner_queue_md,
        DATA_DIR / "console_vehicle_compatibility.review.json": json.dumps(compat, indent=2),
    }

    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return {
        "repo_images": len(repo_images),
        "corpus_images": len(corpus_images),
        "coverage_totals": coverage_totals,
        "coverage_states": coverage_states,
        "compatibility_summary": compat["summary"],
        "owner_review_queue_count": len(compat["owner_review"]["raw"]),
        "owner_review_grouped_count": len(compat["owner_review"]["grouped"]),
    }


def main() -> None:
    summary = run_audit()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
