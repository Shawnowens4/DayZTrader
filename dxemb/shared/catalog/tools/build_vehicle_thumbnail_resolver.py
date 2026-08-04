import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = ROOT / "dxemb" / "shared" / "catalog" / "data"

MANIFEST_PATH = DATA_DIR / "vehicle_variant_manifest.json"
OUTPUT_PATH = DATA_DIR / "vehicle_thumbnail_resolver.json"

PART_SLOT_ORDER = [
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
}

MANUAL_COLOR_INHERITANCE = {
    "civiliansedan": {
        "black": ["default"],
        "wine": ["default"],
    },
    "hatchback_02": {
        "blue": ["default"],
        "green": ["default"],
        "white": ["default"],
        "grey": ["default"],
    },
    "sedan_02": {
        "grey": ["default"],
        "red": ["default"],
    },
    "offroad_02": {
        "blue": ["default"],
        "green": ["default"],
        "white": ["default"],
    },
    "truck_01": {
        "blue": ["default"],
        "green": ["default"],
        "orange": ["default"],
        "red": ["default"],
        "red+blue": ["blue", "default"],
        "red+orange": ["orange", "default"],
    },
    "uaz_452": {
        "default": [],
    },
    "m1025": {
        "default": [],
    },
    "landrover": {
        "default": [],
    },
}

MANUAL_BODY_PREFERENCES = {
    "civiliansedan": {
        "default": ["civiliansedan.webp", "olga24.webp", "olga_24.webp"],
        "black": ["civiliansedan_black.webp", "olga24black.webp", "olga_24_black.webp"],
        "wine": ["civiliansedan_wine.webp", "olga24wine.webp", "olga_24_wine.webp"],
    },
    "hatchback_02": {
        "default": ["ada_4_4.webp", "ada4x4.webp", "hatchback_02.webp", "hatchback02.webp"],
        "blue": ["ada_4_4_blue.webp", "ada4x4blue.webp"],
        "green": ["ada_4_4_green.webp", "ada4x4green.webp"],
        "white": ["ada_4_4_white.webp", "ada4x4white.webp"],
        "grey": ["ada_4_4_grey.webp", "ada4x4grey.webp", "ada_4_4_gray.webp"],
    },
    "sedan_02": {
        "default": ["sarka_120.webp", "sarka120.webp", "sedan_02.webp", "sedan02.webp"],
        "grey": ["sarka_120_grey.webp", "sarka120grey.webp"],
        "red": ["sarka_120_red.webp", "sarka120red.webp"],
    },
    "offroad_02": {
        "default": ["gunter_2.webp", "gunter2.webp", "offroad_02.webp", "offroad02.webp"],
        "blue": ["gunter_2_blue.webp", "gunter2blue.webp"],
        "green": ["gunter_2_green.webp", "gunter2green.webp"],
        "white": ["gunter_2_white.webp", "gunter2white.webp"],
    },
    "truck_01": {
        "default": ["m3s.webp", "m3s_covered.webp", "truck_01_covered.webp", "truck_01.webp"],
        "blue": ["truck_01_covered_blue.webp", "m3s_covered_blue.webp", "m3s_blue.webp"],
        "green": ["truck_01_covered_green.webp", "m3s_covered_green.webp", "m3s_green.webp"],
        "orange": ["truck_01_covered_orange.webp", "m3s_covered_orange.webp", "m3s_orange.webp"],
        "red": ["m3s_covered.webp", "truck_01_covered.webp", "m3s.webp"],
        "red+blue": ["truck_01_covered_blue.webp", "m3s_covered_blue.webp"],
        "red+orange": ["truck_01_covered_orange.webp", "m3s_covered_orange.webp"],
    },
    "m1025": {
        "default": ["m1025.webp"],
    },
    "landrover": {
        "default": ["land_rover_range_rover_classic.webp", "landroverrangeroverclassic.webp", "landrover.webp"],
    },
    "uaz_452": {
        "default": ["uaz-452.webp", "uaz452.webp"],
    },
}

PART_TOKENS = [
    "door",
    "hood",
    "trunk",
    "trunkdoor",
    "trunklid",
    "wheel",
    "leftdoor",
    "rightdoor",
    "frontleftdoor",
    "frontrightdoor",
    "rearleftdoor",
    "rearrightdoor",
    "driverdoor",
    "codriverdoor",
    "co-driverdoor",
    "door11",
    "door12",
    "door21",
    "door22",
]


def normalize_color(color: str) -> str:
    return COLOR_ALIASES.get(color, color)


def normalize_stem(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def has_part_token(filename: str) -> bool:
    n = normalize_stem(filename)
    return any(normalize_stem(token) in n for token in PART_TOKENS)


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def find_part_image(variant_data: dict, slot: str):
    part_files = variant_data.get("parts", {}).get(slot, [])
    return part_files[0] if part_files else None


def build_color_search_chain(family_key: str, color: str, all_variant_keys: list[str]):
    color = normalize_color(color)
    chain = [color]

    inheritance = MANUAL_COLOR_INHERITANCE.get(family_key, {}).get(color, [])
    for inherited in inheritance:
        inherited = normalize_color(inherited)
        if inherited not in chain:
            chain.append(inherited)

    if "default" in all_variant_keys and "default" not in chain:
        chain.append("default")

    return [c for c in chain if c in all_variant_keys]


def candidate_body_images(variant_data: dict):
    return variant_data.get("vehicle_images", [])


def pick_best_body_image_for_color(family_key: str, requested_color: str, variants: dict, search_chain: list[str]):
    preferences = MANUAL_BODY_PREFERENCES.get(family_key, {}).get(requested_color, [])
    normalized_preferences = [normalize_stem(p) for p in preferences]

    all_candidates = []
    for idx, color in enumerate(search_chain):
        for img in candidate_body_images(variants[color]):
            all_candidates.append((idx, color, img))

    if not all_candidates:
        return None, None, True

    for idx, color, img in all_candidates:
        if normalize_stem(img) in normalized_preferences:
            source = "exact_color_body" if idx == 0 and color == requested_color else f"{color}_body_fallback"
            fallback_used = not (idx == 0 and color == requested_color)
            return img, source, fallback_used

    non_part_candidates = [(idx, color, img) for idx, color, img in all_candidates if not has_part_token(img)]
    if non_part_candidates:
        idx, color, img = non_part_candidates[0]
        source = "exact_color_body" if idx == 0 and color == requested_color else f"{color}_body_fallback"
        fallback_used = not (idx == 0 and color == requested_color)
        return img, source, fallback_used

    idx, color, img = all_candidates[0]
    source = "part_like_body_fallback"
    return img, source, True


def build_family_resolver(family_key: str, family_data: dict):
    variants = family_data.get("variants", {})
    variant_keys = list(variants.keys())

    requested_colors = set(variant_keys)
    requested_colors.update(MANUAL_COLOR_INHERITANCE.get(family_key, {}).keys())
    requested_colors.update(MANUAL_BODY_PREFERENCES.get(family_key, {}).keys())

    if not requested_colors:
        requested_colors = {"default"}

    family_output = {
        "label": family_data.get("label", family_key),
        "family_key": family_key,
        "variants": {},
    }

    for requested_color in sorted(requested_colors):
        search_chain = build_color_search_chain(family_key, requested_color, variant_keys)

        selected_body, body_source, body_fallback_used = pick_best_body_image_for_color(
            family_key, requested_color, variants, search_chain
        )

        slots_output = {}

        for slot in PART_SLOT_ORDER:
            chosen_image = None
            source = None
            fallback_used = False
            matched_color = None

            for idx, candidate_color in enumerate(search_chain):
                candidate_variant = variants[candidate_color]
                candidate_part = find_part_image(candidate_variant, slot)
                if candidate_part:
                    chosen_image = candidate_part
                    matched_color = candidate_color
                    source = "exact_color_part" if idx == 0 and candidate_color == requested_color else f"{candidate_color}_part_fallback"
                    fallback_used = not (idx == 0 and candidate_color == requested_color)
                    break

            if not chosen_image and selected_body:
                chosen_image = selected_body
                matched_color = search_chain[0] if search_chain else requested_color
                source = "vehicle_body_fallback"
                fallback_used = True

            slots_output[slot] = {
                "image": chosen_image,
                "source": source,
                "fallback_used": fallback_used,
                "matched_color": matched_color,
                "has_exact_color_part": source == "exact_color_part",
            }

        family_output["variants"][requested_color] = {
            "vehicle_body": {
                "image": selected_body,
                "source": body_source,
                "fallback_used": body_fallback_used,
                "is_part_like_body": bool(selected_body and has_part_token(selected_body)),
            },
            "slots": slots_output,
            "search_chain": search_chain,
        }

    return family_output


def build_resolver(manifest: dict):
    resolver = {
        "generated_from": str(MANIFEST_PATH),
        "families": {},
    }

    families = manifest.get("families", {})
    for family_key, family_data in sorted(families.items()):
        resolver["families"][family_key] = build_family_resolver(family_key, family_data)

    return resolver


def print_summary(resolver: dict):
    print(f"Wrote resolver: {OUTPUT_PATH}")
    print(f"Families: {len(resolver['families'])}")

    for family_key, family_data in resolver["families"].items():
        print(f"- {family_key}")
        for color, color_data in family_data["variants"].items():
            exact_parts = []
            fallback_parts = []
            missing_parts = []

            for slot, slot_data in color_data["slots"].items():
                if not slot_data["image"]:
                    missing_parts.append(slot)
                elif slot_data["has_exact_color_part"]:
                    exact_parts.append(slot)
                else:
                    fallback_parts.append(slot)

            body = color_data["vehicle_body"]["image"] or "none"
            body_flag = " part-like-body" if color_data["vehicle_body"]["is_part_like_body"] else ""

            print(
                f"  - {color}: "
                f"body={body}; "
                f"exact_parts={len(exact_parts)}; "
                f"fallback_parts={len(fallback_parts)}; "
                f"missing_parts={len(missing_parts)}; "
                f"body_source={color_data['vehicle_body']['source']}{body_flag}"
            )


def main():
    if not MANIFEST_PATH.exists():
        raise SystemExit(f"Missing manifest file: {MANIFEST_PATH}")

    manifest = load_manifest()
    resolver = build_resolver(manifest)

    OUTPUT_PATH.write_text(json.dumps(resolver, indent=2), encoding="utf-8")
    print_summary(resolver)


if __name__ == "__main__":
    main()