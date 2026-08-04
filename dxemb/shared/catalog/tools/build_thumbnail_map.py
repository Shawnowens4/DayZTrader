from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TYPES_XML_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "types.xml"
IMAGES_DIR = ROOT / "dxemb" / "web" / "static" / "items"
OUTPUT_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "dayzidb_map.json"
SEED_PATH = ROOT / "dxemb" / "shared" / "catalog" / "data" / "classname_displayname_map.seed.json"

EXCLUDE_PREFIXES = (
    "zmbf_", "zmbm_", "animal_", "land_wreck_", "staticobj_", "static_",
    "land_container_", "land_train_", "land_boat_",
)

GENERIC_FAMILY_FALLBACK = {
    "flag_": "flag_pole",
    "armband_": "armband",
}

SIMPLE_VARIANT_SUFFIXES = (
    "black", "green", "camo", "blue", "red", "white", "brown",
    "autumn", "spring", "summer", "winter", "orange", "pink",
    "yellow", "gray", "grey", "olive", "tan", "dark", "light",
    "wood", "plastic", "rail", "folding", "violet", "khaki",
    "beige", "navy", "lime", "maroon", "purple", "gold", "silver",
)

COMPOUND_VARIANT_PATTERNS = (
    r"_(" + "|".join(SIMPLE_VARIANT_SUFFIXES) + r")(pattern|check|checker|skull|rock|punk|bright|dark)?$",
    r"_(darkgrey|lightgrey|darkblue|lightblue|navyblue|skyblue|bluedark)$",
    r"_(pautrev|flat|threat|sunburst)$",
    r"_(rust)$",
)

# vehicle_prefix -> the base vehicle image to use as last-resort fallback for parts
VEHICLE_PART_BASE_FALLBACK = {
    "hatchback_02_": "hatchback_02",
    "sedan_02_": "sedan_02",
    "truck_01_": "truck_01",
    "offroad_02_": "offroad_02",
    "civiliansedan_": "civiliansedan",
}

AMMO_CALIBER_PATTERN = re.compile(r"^ammo_([a-z0-9]+)", re.IGNORECASE)


def normalize(name: str) -> str:
    name = name.lower()
    name = re.sub(r"\.(webp|png|jpg|jpeg)$", "", name)
    name = re.sub(r"[^a-z0-9]", "", name)
    return name


def strip_variant_suffix(classname: str):
    for pattern in COMPOUND_VARIANT_PATTERNS:
        base = re.sub(pattern, "", classname, flags=re.IGNORECASE)
        if base != classname:
            return base
    return None


def is_excluded(classname: str) -> bool:
    low = classname.lower()
    return any(low.startswith(p) for p in EXCLUDE_PREFIXES)


def generic_family_image(classname: str, images: dict):
    low = classname.lower()
    for prefix, generic_key in GENERIC_FAMILY_FALLBACK.items():
        if low.startswith(prefix):
            return images.get(normalize(generic_key))
    return None


def vehicle_part_fallback(classname: str, images: dict):
    low = classname.lower()
    for prefix, base_key in VEHICLE_PART_BASE_FALLBACK.items():
        if low.startswith(prefix):
            return images.get(normalize(base_key))
    return None


def ammo_box_fallback(classname: str, images: dict):
    low = classname.lower()
    m = AMMO_CALIBER_PATTERN.match(low)
    if not m:
        return None
    caliber = m.group(1)
    caliber_norm = re.sub(r"[^a-z0-9]", "", caliber)
    for norm_name, filename in images.items():
        if norm_name.startswith("ammobox" + caliber_norm):
            return filename
    return None


def load_classnames() -> list[str]:
    tree = ET.parse(TYPES_XML_PATH)
    root = tree.getroot()
    return [el.attrib["name"] for el in root.findall("type") if "name" in el.attrib]


def load_images() -> dict[str, str]:
    out = {}
    for file in IMAGES_DIR.glob("*.webp"):
        out[normalize(file.name)] = file.name
    return out


def load_seed() -> dict[str, str]:
    if not SEED_PATH.exists():
        return {}
    data = json.loads(SEED_PATH.read_text(encoding="utf-8-sig"))
    mappings = data.get("mappings", {})
    return {k: v["display_name"] for k, v in mappings.items()}


def main():
    classnames = load_classnames()
    images = load_images()
    seed = load_seed()

    existing = {}
    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8-sig"))

    mapped = dict(existing)
    matched, unmatched, excluded = [], [], []
    seed_matched = 0
    variant_matched = 0
    generic_matched = 0
    vehicle_part_matched = 0
    ammo_box_matched = 0

    for cls in classnames:
        key = cls.strip().lower()
        if key in mapped:
            continue

        if is_excluded(cls):
            excluded.append(cls)
            continue

        norm_cls = normalize(cls)
        image_name = images.get(norm_cls)

        if not image_name:
            base = strip_variant_suffix(cls)
            if base:
                image_name = images.get(normalize(base))
                if image_name:
                    variant_matched += 1

        if not image_name:
            display_name = seed.get(cls)
            if not display_name:
                base = strip_variant_suffix(cls)
                if base:
                    display_name = seed.get(base)
            if display_name:
                norm_display = normalize(display_name)
                image_name = images.get(norm_display)
                if image_name:
                    seed_matched += 1

        if not image_name:
            image_name = ammo_box_fallback(cls, images)
            if image_name:
                ammo_box_matched += 1

        if not image_name:
            image_name = generic_family_image(cls, images)
            if image_name:
                generic_matched += 1

        if not image_name:
            image_name = vehicle_part_fallback(cls, images)
            if image_name:
                vehicle_part_matched += 1

        if image_name:
            mapped[key] = image_name
            matched.append(cls)
        else:
            unmatched.append(cls)

    OUTPUT_PATH.write_text(json.dumps(mapped, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Total classnames: {len(classnames)}")
    print(f"Excluded (zombies/animals/wrecks/statics): {len(excluded)}")
    print(f"Matched this run: {len(matched)}")
    print(f"  (via variant-suffix strip: {variant_matched})")
    print(f"  (via seed lookup: {seed_matched})")
    print(f"  (via ammo box fallback: {ammo_box_matched})")
    print(f"  (via generic family fallback: {generic_matched})")
    print(f"  (via vehicle part base fallback: {vehicle_part_matched})")
    print(f"Total mapped now: {len(mapped)}")
    print(f"Unmatched: {len(unmatched)}")

    if unmatched:
        unmatched_path = OUTPUT_PATH.parent / "unmatched_classnames.txt"
        unmatched_path.write_text("\n".join(sorted(unmatched)), encoding="utf-8")
        print(f"Unmatched list written to: {unmatched_path}")

    if excluded:
        excluded_path = OUTPUT_PATH.parent / "excluded_classnames.txt"
        excluded_path.write_text("\n".join(sorted(excluded)), encoding="utf-8")
        print(f"Excluded list written to: {excluded_path}")


if __name__ == "__main__":
    main()