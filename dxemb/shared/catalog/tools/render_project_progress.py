from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_PATH = REPO_ROOT / "dxemb" / "shared" / "catalog" / "data" / "project_progress.json"
DOC_PATH = REPO_ROOT / "docs" / "PROJECT_PROGRESS.md"

FIXED_STATUS_PERCENT = {
    "not_started": 0,
    "discovery": 10,
    "planned": 20,
    "in_progress": 40,
    "implemented_unverified": 60,
    "locally_tested": 80,
    "owner_review_required": 85,
    "complete": 100,
    "intentionally_disabled": 0,
}

ALLOWED_STATUSES = set(FIXED_STATUS_PERCENT.keys()) | {"blocked"}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("project_progress.json must be an object")
    return payload


def _progress_bar(percent: int, width: int = 10) -> str:
    filled = int(round((percent / 100) * width))
    filled = max(0, min(width, filled))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def _validate_item(item: dict[str, Any], owner_queue_resolved: bool) -> None:
    required = [
        "id",
        "product_area",
        "title",
        "weight",
        "status",
        "percent_complete",
        "evidence",
        "test_status",
        "blocker",
        "owner_action_needed",
        "next_step",
        "last_verified_commit",
    ]
    for field in required:
        if field not in item:
            raise ValueError(f"missing required item field: {field}")

    status = item["status"]
    percent = item["percent_complete"]

    if status not in ALLOWED_STATUSES:
        raise ValueError(f"invalid status {status} for item {item['id']}")

    if not isinstance(percent, int) or percent < 0 or percent > 100:
        raise ValueError(f"invalid percent_complete for item {item['id']}")

    if status in FIXED_STATUS_PERCENT:
        expected = FIXED_STATUS_PERCENT[status]
        if percent != expected:
            raise ValueError(f"item {item['id']} status {status} requires percent {expected}, got {percent}")

    if status == "blocked" and percent == 100:
        raise ValueError(f"blocked item {item['id']} cannot be 100")

    if percent > 60 and item["test_status"] not in {"passed", "validated"}:
        raise ValueError(f"item {item['id']} cannot exceed 60 without tests/validation evidence")

    if percent > 80 and not bool(item.get("usable_local", False)):
        raise ValueError(f"item {item['id']} cannot exceed 80 unless usable locally")

    if status == "owner_review_required" and percent > 85:
        raise ValueError(f"item {item['id']} owner_review_required cannot exceed 85")

    if status == "complete":
        if item["test_status"] not in {"passed", "validated"}:
            raise ValueError(f"complete item {item['id']} requires passing test_status")
        if not item.get("manual_test_instructions"):
            raise ValueError(f"complete item {item['id']} requires manual_test_instructions")
        if item.get("blocker"):
            raise ValueError(f"complete item {item['id']} cannot have blocker")
        if not item.get("last_verified_commit"):
            raise ValueError(f"complete item {item['id']} requires last_verified_commit")

    if item.get("depends_on_owner_review_queue") and not owner_queue_resolved:
        if status in {"complete", "owner_review_required", "locally_tested"}:
            raise ValueError(
                f"item {item['id']} depends on unresolved owner queue and cannot be complete/owner_review_required/locally_tested"
            )


def calculate_and_validate(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty list")

    owner_queue_resolved = bool(payload.get("owner_review_queue_resolved", False))

    for item in items:
        _validate_item(item, owner_queue_resolved)

    active_local = [
        item
        for item in items
        if item.get("phase") == "local_finish" and item.get("status") != "intentionally_disabled" and int(item.get("weight", 0)) > 0
    ]
    deferred = [item for item in items if item.get("phase") == "deferred_live_phase"]

    active_weight_total = sum(int(item["weight"]) for item in active_local)
    if active_weight_total != 100:
        raise ValueError(f"active local-finish weights must total 100, got {active_weight_total}")

    for item in deferred:
        if int(item.get("weight", 0)) != 0:
            raise ValueError(f"deferred/live item {item['id']} must have zero weight")

    weighted_sum = sum(int(item["weight"]) * int(item["percent_complete"]) for item in active_local)
    overall = round(weighted_sum / active_weight_total)

    if overall < 35:
        confidence = "low"
    elif overall < 80:
        confidence = "medium"
    else:
        confidence = "high"

    return {
        "active_local": active_local,
        "deferred": deferred,
        "active_weight_total": active_weight_total,
        "weighted_sum": weighted_sum,
        "overall": overall,
        "confidence": confidence,
    }


def render_markdown(payload: dict[str, Any], stats: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# PROJECT_PROGRESS")
    lines.append("")
    lines.append("Single source of truth: dxemb/shared/catalog/data/project_progress.json")
    lines.append("")
    lines.append("## Weight Rationale")
    lines.append("")
    lines.append("Higher weights are assigned to compatibility safety, vehicle builder readiness, map readiness, catalog workflow, and regression health.")
    lines.append("Cosmetic-only or deferred live-phase work does not inflate local-finish progress.")
    lines.append("")
    lines.append("## Local-Finish Progress Bars")
    lines.append("")

    for item in sorted(stats["active_local"], key=lambda x: int(x["id"])):
        lines.append(
            "- {area:<45} {bar} {percent:>3}%  {status}".format(
                area=item["product_area"][:45],
                bar=_progress_bar(int(item["percent_complete"])),
                percent=int(item["percent_complete"]),
                status=item["status"],
            )
        )

    lines.append("")
    lines.append(
        "- {label:<45} {bar} {percent:>3}%  {confidence} confidence".format(
            label="Overall local-finish",
            bar=_progress_bar(stats["overall"]),
            percent=stats["overall"],
            confidence=stats["confidence"],
        )
    )

    lines.append("")
    lines.append("## Calculation Inputs")
    lines.append("")
    lines.append("| ID | Product Area | Weight | Percent | Weighted Contribution |")
    lines.append("|---|---|---:|---:|---:|")
    for item in sorted(stats["active_local"], key=lambda x: int(x["id"])):
        contribution = int(item["weight"]) * int(item["percent_complete"])
        lines.append(
            "| {id} | {area} | {weight} | {percent} | {contribution} |".format(
                id=item["id"],
                area=item["product_area"],
                weight=item["weight"],
                percent=item["percent_complete"],
                contribution=contribution,
            )
        )

    lines.append("")
    lines.append(
        "Overall formula: sum(weight * percent_complete) / sum(active weights) = {weighted_sum} / {denominator} = {overall}%".format(
            weighted_sum=stats["weighted_sum"],
            denominator=stats["active_weight_total"],
            overall=stats["overall"],
        )
    )

    lines.append("")
    lines.append("## Deferred/Live Phase (Excluded From Local-Finish Denominator)")
    lines.append("")
    lines.append("| ID | Product Area | Status | Weight |")
    lines.append("|---|---|---|---:|")
    for item in sorted(stats["deferred"], key=lambda x: int(x["id"])):
        lines.append(
            "| {id} | {area} | {status} | {weight} |".format(
                id=item["id"],
                area=item["product_area"],
                status=item["status"],
                weight=item["weight"],
            )
        )

    change = payload.get("changes_since_last_verified_commit", {})
    lines.append("")
    lines.append("## What Changed Since Last Verified Commit")
    lines.append("")
    lines.append("### Newly Completed")
    for entry in change.get("newly_completed", []) or ["None in this audit-only slice."]:
        lines.append(f"- {entry}")

    lines.append("")
    lines.append("### Percentage Increases/Decreases And Why")
    for entry in change.get("percentage_changes", []) or ["No recorded percentage movement."]:
        lines.append(f"- {entry}")

    lines.append("")
    lines.append("### New Blockers")
    for entry in change.get("new_blockers", []) or ["None."]:
        lines.append(f"- {entry}")

    lines.append("")
    lines.append("### Owner Actions Needed")
    for entry in change.get("owner_actions_needed", []) or ["None."]:
        lines.append(f"- {entry}")

    lines.append("")
    lines.append("### Next Highest-Value Slice")
    lines.append(f"- {change.get('next_highest_value_slice', 'Not set.')}" )

    lines.append("")
    lines.append("## Owner Action Queue")
    lines.append("")
    lines.append("- Provide owner-owned console vehicle evidence inputs listed in docs/CONSOLE_VEHICLE_SOURCE_IMPORT_GUIDE.md.")
    lines.append("- Resolve grouped queue rows in docs/CONSOLE_VEHICLE_OWNER_REVIEW_QUEUE.md in listed priority order.")

    return "\n".join(lines) + "\n"


def render_project_progress() -> dict[str, Any]:
    payload = _load_json(DATA_PATH)
    stats = calculate_and_validate(payload)
    markdown = render_markdown(payload, stats)
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(markdown, encoding="utf-8")
    return {"overall": stats["overall"], "confidence": stats["confidence"], "active_weight_total": stats["active_weight_total"]}


def main() -> None:
    summary = render_project_progress()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
