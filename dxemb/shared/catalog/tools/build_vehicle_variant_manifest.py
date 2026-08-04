import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
IMAGES_DIR = ROOT / "dxemb" / "web" / "static" / "items"
OUTPUT_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "vehicle_variant_manifest.json"

KNOWN_FAMILIES = {
    "hatchback_02": {
        "label": "Ada 4x4",
        "aliases": ["hatchback_02", "hatchback02", "ada4x4", "ada44"],
        "parts": {
            "hood": ["hood", "hatchbackhood", "ada4x4hood", "ada44hood"],
            "driver_door": ["door11", "leftdoor", "driverdoor", "hatchbackdoorsdriver", "ada4x4leftdoor", "ada44leftdoor"],
            "codriver_door": ["door12", "rightdoor", "codriverdoor", "co-driverdoor", "hatchbackdoorscodriver", "ada4x4rightdoor", "ada44rightdoor"],
            "trunk": ["door21", "trunk", "trunkdoor", "rear door", "rear_door", "hatchbacktrunk"],
            "wheel": ["wheel", "hatchback02wheel", "ada4x4wheel", "ada44wheel"],
        },
    },
    "civiliansedan": {
        "label": "Olga 24",
        "aliases": ["civiliansedan", "olga24", "civsedan"],
        "parts": {
            "hood": ["hood", "civsedanhood", "olga24hood"],
            "driver_door": ["door11", "frontleftdoor", "driverdoor", "civsedandoorsdriver", "olga24frontleftdoor"],
            "codriver_door": ["door12", "frontrightdoor", "codriverdoor", "civsedandoorscodriver", "olga24frontrightdoor"],
            "rear_left_door": ["door21", "rearleftdoor", "civsedandoorsbackleft", "olga24rearleftdoor"],
            "rear_right_door": ["door22", "rearrightdoor", "civsedandoorsbackright", "olga24rearrightdoor"],
            "trunk": ["trunk", "trunklid", "civsedantrunk", "olga24trunklid"],
            "wheel": ["wheel", "civsedanwheel", "olga24wheel"],
        },
    },
    "sedan_02": {
        "label": "Sarka 120",
        "aliases": ["sedan_02", "sedan02", "sarka120", "sarka"],
        "parts": {
            "hood": ["hood", "sedan02hood", "sarka120hood"],
            "driver_door": ["door11", "frontleftdoor", "driverdoor", "sarka120frontleftdoor"],
            "codriver_door": ["door12", "frontrightdoor", "codriverdoor"],
            "rear_left_door": ["door21", "rearleftdoor", "sarka120rearleftdoor"],
            "rear_right_door": ["door22", "rearrightdoor", "sarka120rearrightdoor"],
            "trunk": ["trunk", "trunkdoor", "sedan02trunk", "sarka120trunkdoor"],
            "wheel": ["wheel", "sedan02wheel", "sarka120wheel"],
        },
    },
    "offroad_02": {
        "label": "Gunter 2",
        "aliases": ["offroad_02", "offroad02", "gunter2", "gunter"],
        "parts": {
            "hood": ["hood", "offroad02hood", "gunter2hood"],
            "driver_door": ["door11", "frontleftdoor", "driverdoor", "gunter2frontleftdoor"],
            "codriver_door": ["door12", "frontrightdoor", "codriverdoor", "gunter2frontrightdoor"],
            "rear_left_door": ["door21", "rearleftdoor", "gunter2rearleftdoor"],
            "rear_right_door": ["door22", "rearrightdoor", "gunter2rearrightdoor"],
            "trunk": ["trunk", "trunkdoor", "gunter2trunkdoor"],
            "wheel": ["wheel", "offroad02wheel", "gunter2wheel"],
        },
    },
    "truck_01": {
        "label": "M3S",
        "aliases": ["truck_01", "truck01", "m3s"],
        "parts": {
            "hood": ["hood", "m3shood"],
            "driver_door": ["leftdoor", "driverdoor", "m3sleftdoor"],
            "codriver_door": ["rightdoor", "codriverdoor", "m3srightdoor"],
            "wheel": ["wheel", "m3swheel"],
        },
    },
    "landrover": {
        "label": "Land Rover",
        "aliases": ["landrover"],
        "parts": {
            "driver_door": ["frontleftdoor"],
            "codriver_door": ["frontrightdoor"],
            "rear_left_door": ["rearleftdoor"],
            "rear_right_door": ["rearrightdoor"],
            "wheel": ["wheel"],
        },
    },
    "uaz_452": {
        "label": "UAZ-452",
        "aliases": ["uaz-452", "uaz452"],
        "parts": {
            "driver_door": ["driverdoor"],
            "codriver_door": ["codriverdoor", "co-driverdoor"],
            "rear_left_door": ["leftreardoor"],
            "rear_right_door": ["rightreardoor"],
            "side_door": ["sidedoor"],
            "wheel": ["wheel"],
        },
    },
    "m1025": {
        "label": "M1025",
        "aliases": ["m1025"],
        "parts": {
            "hood": ["hood"],
            "driver_door": ["frontleftdoor"],
            "codriver_door": ["frontrightdoor"],
            "rear_left_door": ["rearleftdoor"],
            "rear_right_door": ["rearrightdoor"],
            "trunk": ["trunkdoor"],
            "wheel": ["wheel"],
        },
    },
}

COLOR_HINTS = [
    "black", "white", "grey", "gray", "red", "green", "blue", "wine", "yellow", "orange", "beige", "brown", "camo"
]

RUST_HINTS = ["rust", "rustr", "rusty", "bluerust", "greenrust", "whiterust", "blackrust", "winerust", "greyrust", "redrust", "yellowrust"]


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def split_tokens(stem: str):
    return re.split(r"[_\-\s]+", stem.lower())


def find_family(stem: str):
    n = normalize_name(stem)
    best_family = None
    best_len = -1
    for family_key, meta in KNOWN_FAMILIES.items():
        for alias in meta["aliases"]:
            a = normalize_name(alias)
            if a in n and len(a) > best_len:
                best_family = family_key
                best_len = len(a)
    return best_family


def detect_color(stem: str):
    s = stem.lower()
    found = []
    for color in COLOR_HINTS:
        if color in s:
            found.append(color)
    if not found:
        return "default"
    found = sorted(set(found), key=lambda x: s.index(x))
    return "+".join(found)


def detect_rust_state(stem: str):
    s = stem.lower()
    return any(hint in s for hint in RUST_HINTS)


def detect_part_slot(stem: str, family_key: str):
    s = stem.lower()
    if family_key not in KNOWN_FAMILIES:
        return "body"
    for slot, patterns in KNOWN_FAMILIES[family_key]["parts"].items():
        for pattern in patterns:
            if normalize_name(pattern) in normalize_name(s):
                return slot
    return "body"


def collect_images():
    return sorted(IMAGES_DIR.glob("*.webp"))


def build_manifest():
    manifest = {
        "generated_from": str(IMAGES_DIR),
        "families": {},
        "unknown_vehicle_like_files": [],
    }

    family_groups = defaultdict(list)

    for path in collect_images():
        stem = path.stem
        family_key = find_family(stem)
        if family_key:
            family_groups[family_key].append(path)
        else:
            n = normalize_name(stem)
            if any(token in n for token in ["door", "hood", "trunk", "wheel", "rearleft", "rearright", "frontleft", "frontright", "driverdoor", "codriverdoor"]):
                manifest["unknown_vehicle_like_files"].append(path.name)

    for family_key, paths in family_groups.items():
        meta = KNOWN_FAMILIES[family_key]
        family_entry = {
            "label": meta["label"],
            "family_key": family_key,
            "aliases": meta["aliases"],
            "parts_configured": sorted(meta["parts"].keys()),
            "variants": defaultdict(lambda: {
                "vehicle_images": [],
                "parts": defaultdict(list),
                "all_files": [],
            }),
        }

        for path in paths:
            stem = path.stem
            color = detect_color(stem)
            rust = detect_rust_state(stem)
            slot = detect_part_slot(stem, family_key)

            item = {
                "file": path.name,
                "slot": slot,
                "color": color,
                "rust": rust,
                "stem": stem,
            }

            variant = family_entry["variants"][color]
            variant["all_files"].append(item)

            if slot == "body":
                variant["vehicle_images"].append(path.name)
            else:
                variant["parts"][slot].append(path.name)

        final_variants = {}
        for color, variant_data in family_entry["variants"].items():
            final_variants[color] = {
                "vehicle_images": sorted(set(variant_data["vehicle_images"])),
                "parts": {slot: sorted(set(files)) for slot, files in sorted(variant_data["parts"].items())},
                "all_files": sorted(variant_data["all_files"], key=lambda x: x["file"]),
                "completeness": {
                    "has_body_image": bool(variant_data["vehicle_images"]),
                    "part_slots_found": sorted(variant_data["parts"].keys()),
                    "missing_configured_slots": sorted(
                        set(meta["parts"].keys()) - set(variant_data["parts"].keys())
                    ),
                },
            }

        family_entry["variants"] = dict(sorted(final_variants.items()))
        manifest["families"][family_key] = family_entry

    manifest["families"] = dict(sorted(manifest["families"].items()))
    manifest["unknown_vehicle_like_files"] = sorted(set(manifest["unknown_vehicle_like_files"]))

    return manifest


def main():
    manifest = build_manifest()
    OUTPUT_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote manifest: {OUTPUT_PATH}")
    print(f"Families: {len(manifest['families'])}")
    print(f"Unknown vehicle-like files: {len(manifest['unknown_vehicle_like_files'])}")

    for family_key, family in manifest["families"].items():
        print(f"- {family_key}: {len(family['variants'])} variant groups")
        for color, variant in family["variants"].items():
            slots = ", ".join(variant["completeness"]["part_slots_found"]) or "none"
            print(f"  - {color}: body={len(variant['vehicle_images'])} part_slots={slots}")


if __name__ == "__main__":
    main()