# CONSOLE_VEHICLE_SOURCE_IMPORT_GUIDE

Purpose: convert owner-review-required vehicle compatibility rows into verified rows using only owner-owned vanilla console evidence.

## Scope And Safety

- Scope is Xbox/PlayStation vanilla only.
- Do not upload or commit original server credentials.
- Do not commit raw owned server files to this repository.
- This guide supports audit-only verification input. It does not change runtime behavior.

## Priority Order For Evidence Inputs

1. types.xml
2. cfgspawnabletypes.xml
3. events.xml
4. cfgeventspawns.xml (only if events and spawnable links are ambiguous)
5. Current owner-owned Xbox/PlayStation mission files (only the minimum vehicle-related blocks)

## Smallest Safe Submission Methods

Use one of the following methods:

1. Temporary local reference folder (preferred for repeatable parsing)
- Create local folder: local_console_reference/
- Copy only needed files into that folder.
- Folder is git-ignored and must stay untracked.

2. Vehicle-only block submission
- Paste or upload only vehicle-related XML blocks.
- Include exact surrounding keys or class names so locators can be recorded.

## Minimum Vehicle Blocks Needed

For each vehicle family under review, provide only these blocks first:

1. Vehicle type block in types.xml
- Classname and nominal/lifetime sections for the vehicle body.

2. Spawnable/attachment compatibility in cfgspawnabletypes.xml
- Attachments or cargo classes tied to each vehicle type.
- Slot-specific attachment references where available.

3. Event linkage in events.xml
- Event entries that reference the vehicle classname.

4. Spawn locator context in cfgeventspawns.xml (if needed)
- Only include sections that resolve ambiguous event vehicle mappings.

## How Evidence Converts Review Rows

A row moves from owner_review_required toward verification only when all required fields can be filled with owner evidence:

- source_type
- source_path
- source_vehicle_type
- evidence_excerpt_locator
- reviewed_by
- review_status

review_status values:

- owner_confirmation_needed
- internally_consistent_no_console_provenance
- direct_console_proof_available
- unknown_or_missing

Only direct_console_proof_available should be used for approving a specific vehicle-to-part rule.

## Locator Format

Use compact locators so a later reviewer can re-open proof quickly:

- xml_path:/types/type[@name='CivilianSedan']
- xml_path:/cfgspawnabletypes/type[@name='CivilianSedan']/attachments
- xml_path:/events/event[@name='VehicleCivilianSedan']

## Review Flow

1. Whole vehicle body eligibility per family.
2. Required default parts by slot.
3. Color-specific parts.
4. Special cargo slot rules.
5. Remaining image-only gaps.

## Explicit Non-Goals

- No approval from image filenames alone.
- No approval from generic resolver guesses.
- No approval from archive JavaScript.
- No approval from generic family aliases or color suffix assumptions.
- No schema changes, migrations, or external integration changes.
