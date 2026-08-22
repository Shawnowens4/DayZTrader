# DAYZ_IMAGE_AND_VEHICLE_VARIANT_AUDIT

Scope: Xbox/PlayStation vanilla console only. No PC/mod/Arma/workshop/future content is approved.

## Reproducible Inventory Instructions

1. Run: python dxemb/shared/catalog/tools/audit_console_vehicle_assets.py
2. Read generated files in docs/ and dxemb/shared/catalog/data/.
3. No image copying/downloading is performed by this audit.

## Numeric Totals

- catalog classnames: 1661
- vehicle families (variant manifest): 8
- vehicle families (resolver final): 3
- vehicle variants (variant manifest): 16
- repository local images: 4
- reference corpus images (C:/DXEMB/items): 0
- exact_local_image: 0
- family_fallback_only: 0
- generic_fallback_only: 13
- missing: 3
- evidence owner_confirmation_needed: 13
- evidence internally_consistent_no_console_provenance: 0
- evidence direct_console_proof_available: 0
- evidence unknown_or_missing: 3
- part_only images (repo): 0
- part_only images (reference corpus): 0
- excluded images (repo): 0
- excluded images (reference corpus): 0

## Source Paths

- dxemb/shared/catalog/data/dayzidb_map.json
- dxemb/shared/catalog/data/vehicle_thumbnail_resolver.final.json
- dxemb/shared/catalog/data/vehicle_variant_manifest.json
- dxemb/shared/catalog/data/excluded_classnames.txt
- dxemb/web/static/catalog_items
- dxemb/web/static/ui
- C:/DXEMB/items (read-only reference corpus)

## Vehicle Color/Variant Coverage

| Family | Variant | Coverage | Evidence State | Body Candidates | Evidence Paths |
|---|---|---|---|---|---|
| civiliansedan | black | generic_fallback_only | owner_confirmation_needed | civiliansedan_black.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| civiliansedan | default | generic_fallback_only | owner_confirmation_needed | civiliansedan.webp, olga_24.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| civiliansedan | wine | generic_fallback_only | owner_confirmation_needed | civiliansedan_wine.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| hatchback_02 | default | generic_fallback_only | owner_confirmation_needed | ada_4_4.webp, hatchback_02.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| landrover | default | missing | unknown_or_missing | land_rover_range_rover_classic.webp | - |
| m1025 | default | missing | unknown_or_missing | m1025.webp | - |
| offroad_02 | default | generic_fallback_only | owner_confirmation_needed | gunter_2.webp, offroad_02.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| sedan_02 | default | generic_fallback_only | owner_confirmation_needed | sarka_120.webp, sedan_02.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| truck_01 | blue | generic_fallback_only | owner_confirmation_needed | truck_01_door_1_1_blue.webp, truck_01_door_1_1_bluerust.webp, truck_01_door_2_1_blue.webp, truck_01_door_2_1_bluerust.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| truck_01 | default | generic_fallback_only | owner_confirmation_needed | truck_01_door_1_1.webp, truck_01_door_2_1.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| truck_01 | green | generic_fallback_only | owner_confirmation_needed | truck_01_door_1_1_greenrust.webp, truck_01_door_2_1_greenrust.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| truck_01 | orange | generic_fallback_only | owner_confirmation_needed | truck_01_door_1_1_orange.webp, truck_01_door_1_1_orangerust.webp, truck_01_door_2_1_orange.webp, truck_01_door_2_1_orangerust.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| truck_01 | red | generic_fallback_only | owner_confirmation_needed | m3s_covered.webp, truck_01_covered.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| truck_01 | red+blue | generic_fallback_only | owner_confirmation_needed | truck_01_covered_blue.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| truck_01 | red+orange | generic_fallback_only | owner_confirmation_needed | truck_01_covered_orange.webp | dxemb/shared/catalog/data/dayzidb_map.json |
| uaz_452 | default | missing | unknown_or_missing | uaz-452.webp, uaz_452.webp | - |

## Wrong/Mixed/Missing Color Mapping Findings

- OffroadHatchback in resolver final is a placeholder family unrelated to full console family manifest coverage.
- truck_01 manifest variants include mixed labels (red+blue, red+orange) that need owner verification before exposure.
- sedan_02 default variant has missing codriver_door mapping in manifest completeness metadata.
- resolver final currently contains only 3 concrete families plus note placeholder; this is incomplete against variant manifest.

## Evidence Maturity Interpretation

- owner_confirmation_needed: source exists in project artifacts but console-owned XML/mission evidence is not attached.
- internally_consistent_no_console_provenance: variant and slot structure is internally coherent across manifest/resolver, but still unproven for console rules.
- direct_console_proof_available: reserved for owner-attached console files proving exact vehicle-to-slot rule (none present in this run).
- unknown_or_missing: source is absent or contradictory in current local project artifacts.

## Candidate Corrections (CANDIDATE ONLY, NOT APPLIED)

- Replace placeholder resolver entries with reviewed console-only family/classname/color set from compatibility review JSON.
- Normalize family keys to manifest-backed keys after owner supplies console XML evidence.
- Keep all uncertain rows blocked until evidence records are populated and reviewed.

## Review Queue Totals

- grouped checklist rows: 66
- raw unresolved rows: 112
