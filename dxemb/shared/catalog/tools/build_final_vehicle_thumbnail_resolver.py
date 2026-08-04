import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = ROOT / "dxemb" / "shared" / "catalog" / "data"

BASE_RESOLVER_PATH = DATA_DIR / "vehicle_thumbnail_resolver.json"
OVERRIDES_PATH = DATA_DIR / "vehicle_thumbnail_overrides.json"
OUTPUT_PATH = DATA_DIR / "vehicle_thumbnail_resolver.final.json"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def deep_merge(base, override):
    if isinstance(base, dict) and isinstance(override, dict):
        merged = deepcopy(base)
        for key, value in override.items():
            if key in merged:
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
    return deepcopy(override)


def apply_vehicle_body_override(color_entry: dict, image_name: str):
    body = color_entry.setdefault("vehicle_body", {})
    body["image"] = image_name
    body["source"] = "manual_override"
    body["fallback_used"] = False
    body["is_part_like_body"] = False

    slots = color_entry.setdefault("slots", {})
    for slot_name, slot_entry in slots.items():
        source = slot_entry.get("source")
        if source in {"vehicle_body_fallback", "part_like_body_fallback", "part_like_body_override"}:
            slot_entry["image"] = image_name
            slot_entry["source"] = "vehicle_body_override_fallback"
            slot_entry["fallback_used"] = True
            slot_entry["matched_color"] = slot_entry.get("matched_color") or "override"
            slot_entry["has_exact_color_part"] = False


def apply_family_color_override(resolver: dict, family_key: str, color_key: str, override_data: dict):
    family = resolver.setdefault("families", {}).setdefault(
        family_key,
        {"family_key": family_key, "label": family_key, "variants": {}},
    )
    color_entry = family.setdefault("variants", {}).setdefault(
        color_key,
        {
            "vehicle_body": {
                "image": None,
                "source": None,
                "fallback_used": True,
                "is_part_like_body": False,
            },
            "slots": {},
            "search_chain": [color_key],
        },
    )

    vehicle_body_image = override_data.get("vehicle_body")
    if vehicle_body_image:
        apply_vehicle_body_override(color_entry, vehicle_body_image)

    slot_overrides = override_data.get("slots", {})
    for slot_name, slot_patch in slot_overrides.items():
        slot_entry = color_entry.setdefault("slots", {}).setdefault(
            slot_name,
            {
                "image": None,
                "source": None,
                "fallback_used": True,
                "matched_color": color_key,
                "has_exact_color_part": False,
            },
        )
        color_entry["slots"][slot_name] = deep_merge(slot_entry, slot_patch)

    metadata_patch = {k: v for k, v in override_data.items() if k not in {"vehicle_body", "slots"}}
    if metadata_patch:
        merged_entry = deep_merge(color_entry, metadata_patch)
        family["variants"][color_key] = merged_entry


def build_final_resolver():
    base = load_json(BASE_RESOLVER_PATH, {"families": {}})
    overrides = load_json(OVERRIDES_PATH, {})

    final_resolver = deepcopy(base)
    final_resolver["generated_from"] = str(BASE_RESOLVER_PATH)
    final_resolver["overrides_from"] = str(OVERRIDES_PATH) if OVERRIDES_PATH.exists() else None

    for family_key, family_override in overrides.items():
        for color_key, color_override in family_override.items():
            apply_family_color_override(final_resolver, family_key, color_key, color_override)

    return final_resolver


def print_summary(resolver: dict):
    print(f"Wrote final resolver: {OUTPUT_PATH}")
    print(f"Families: {len(resolver.get('families', {}))}")

    for family_key, family_data in resolver.get("families", {}).items():
        print(f"- {family_key}")
        for color_key, color_data in family_data.get("variants", {}).items():
            body = color_data.get("vehicle_body", {}).get("image") or "none"
            body_source = color_data.get("vehicle_body", {}).get("source") or "none"
            fallback_slots = 0
            exact_slots = 0
            missing_slots = 0

            for slot_data in color_data.get("slots", {}).values():
                if not slot_data.get("image"):
                    missing_slots += 1
                elif slot_data.get("has_exact_color_part"):
                    exact_slots += 1
                else:
                    fallback_slots += 1

            print(
                f"  - {color_key}: "
                f"body={body}; "
                f"body_source={body_source}; "
                f"exact_slots={exact_slots}; "
                f"fallback_slots={fallback_slots}; "
                f"missing_slots={missing_slots}"
            )


def main():
    if not BASE_RESOLVER_PATH.exists():
        raise SystemExit(f"Missing base resolver: {BASE_RESOLVER_PATH}")

    final_resolver = build_final_resolver()
    OUTPUT_PATH.write_text(json.dumps(final_resolver, indent=2), encoding="utf-8")
    print_summary(final_resolver)


if __name__ == "__main__":
    main()