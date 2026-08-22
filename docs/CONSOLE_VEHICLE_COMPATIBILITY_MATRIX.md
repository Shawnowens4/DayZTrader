# CONSOLE_VEHICLE_COMPATIBILITY_MATRIX

Fail-closed policy: selection is blocked unless vehicle + slot + variant mapping are explicitly approved.

## Totals

- approved: 0
- owner_review_required: 10
- excluded: 1
- review_rows_grouped: 60
- review_rows_raw: 104

## Vehicle Family Matrix

| Family | Display Name | Status | Confidence | Variant Count |
|---|---|---|---|---|
| boat_01 | Boat | owner_review_required | owner_review_required | 4 |
| civiliansedan | Olga | owner_review_required | owner_review_required | 3 |
| hatchback_02 | Ada 4x4 | owner_review_required | owner_review_required | 1 |
| landrover | Land Rover | owner_review_required | owner_review_required | 1 |
| m1025 | Humvee | owner_review_required | owner_review_required | 1 |
| offroad_02 | Gunter | owner_review_required | owner_review_required | 1 |
| offroadhatchback | OffroadHatchback (resolver placeholder) | owner_review_required | unknown_or_missing | 0 |
| sedan_02 | Sarka | owner_review_required | owner_review_required | 1 |
| truck_01 | M3S | owner_review_required | owner_review_required | 7 |
| uaz_452 | UAZ-452 | owner_review_required | owner_review_required | 1 |
| v3s | V3S / VS3 | excluded | owner_review_required | 0 |

## Evidence Rule Summary

- source exists but needs owner confirmation: owner_confirmation_needed
- internally consistent but lacks console provenance: internally_consistent_no_console_provenance
- source directly proves vehicle-to-part rule: direct_console_proof_available
- unknown/missing: unknown_or_missing

## Builder Consumption Rule

The future vehicle builder must consume only console_vehicle_compatibility.review.json and fail closed.
Default message: Not available until console compatibility is verified.
