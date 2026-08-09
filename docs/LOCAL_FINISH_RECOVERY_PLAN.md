# LOCAL_FINISH_RECOVERY_PLAN.md
# DayZTrader / DXEMB — Local Finish UI Recovery Plan

Date: 2026-08-09
Owner request mode: LOCAL-FINISH autonomous recovery sprint
Status: Plan-only artifact (no code changes in this commit)

---

## 1) Objective and Boundaries

Primary objective:
- Restore and improve the local DayZ visual workflows already present in this repository and validated archive sources, with emphasis on:
  - real DayZ thumbnail cards/selectors
  - functional loot map flow
  - trader catalog recovery
  - vehicle builder recovery

Hard boundaries:
- Do not rebuild project from scratch.
- Prefer adapting verified existing sources over generating replacement systems.
- Preserve Auto-Trader and P2P separation already enforced in active services/routes.
- No live external actions required for this sprint:
  - no Cloudflare changes
  - no Name.com changes
  - no Neon environment changes
  - no Nitrado/FTP/XML live writes
  - no forced restart behavior

---

## 2) Current Route/Surface Matrix (Visual + Functional)

### Active current routes and state

1. Web shell/dashboard
- Source: dxemb/web/app.py
- Current state: inline render_template_string shell; functional admin/status API surface; visually basic and fragmented from recovered DayZ style system.
- Risk: feature routes exist but lack cohesive shared static UI foundation.

2. Trader catalog admin pages
- Source: dxemb/web/catalog_admin.py
- Current state: functional list/detail/enable pages with resolved_thumbnail_url support; inline page CSS only.
- Risk: local static image pipeline is not wired; static/items directory currently empty, so local-first card rendering is incomplete.

3. Vehicle builder pages
- Source: dxemb/web/vehicle_admin.py
- Current state: functional vehicle family list + builder payload rendering from resolver; inline style and no shared JS/static architecture.
- Risk: quality/consistency gap versus richer historic builder interactions.

4. Loot/map interaction
- Source: no active dedicated map UI route in current web module.
- Current state: map behavior missing from active shell.
- Risk: owner-required map flow currently unavailable.

### Existing JSON/API support that must remain reachable

1. /api/vehicles/catalog
2. /api/vehicles/builder/<classname>
3. catalog resolver-backed detail routes
4. existing wallet/market/autotrader/games/tasks/missions read-only and dry-run routes

Constraint:
- Visual restoration must not break existing route contracts or local-safe non-mutation constraints.

---

## 3) Legacy Source Path Manifest (Discovery-Proven Inputs)

### Primary archive candidates (preferred for reuse)

1. UI stylesheet foundation
- C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\web\static\css\admin.css

2. Loot map behavior logic
- C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\web\static\js\map.js

3. Vehicle builder interaction logic
- C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\web\static\js\vehicle_card_builder.js

4. Trunk/cargo builder interaction logic
- C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\web\static\js\trunk_card_builder.js

### Resolver and image-manifest candidates

1. Thumbnail manifest
- C:\DXEMB\web_app\src\static\dayzidb_image_manifest.json

2. Resolver helper
- C:\DXEMB\web_app\src\static\dayzidb_resolver.js

### Asset candidates (image inventory)

1. Map candidates
- C:\DXEMB\items\chernarusmap.webp
- C:\DXEMB\items\tourist_map.webp
- C:\DXEMB\web_app\src\static\items\tourist_map.webp

2. Large DayZ item corpus candidates
- C:\DXEMB\items\ (large source set)
- C:\DXEMB\web_app\src\static\items\ (large source set)

### Ownership/licensing uncertainty flags

- All imported archive visual assets/scripts are treated as project-internal recovery artifacts unless explicitly re-licensed.
- Action: maintain provenance comments in import manifest and avoid external redistribution claims.

---

## 4) Behavior Contracts to Preserve During Recovery

### Trader catalog contract

Required:
1. Use existing catalog service and resolver data as source of truth.
2. Preserve category/search/state filtering behavior.
3. Preserve enable/disable mutation endpoints exactly as current contract.
4. Prefer local static thumbnails when present; fallback to current resolver URL behavior when absent.

Must not:
1. introduce unrelated remote fetch requirements for page rendering.
2. break existing item detail fields or thumbnail status metadata.

### Loot map contract

Required:
1. Add local-safe map page/workflow with explicit read-only or dry-run behavior.
2. Implement deterministic world-coordinate display and map selection UI (based on proven map.js model).
3. Keep map actions non-mutating unless explicitly implemented as dry-run payload preview.

Must not:
1. perform spawn writes, restart actions, or Nitrado operations.
2. conflate map selection with live delivery execution.

### Vehicle builder contract

Required:
1. Preserve current resolver-backed API payloads.
2. Restore richer selector UX (vehicle family, colors, slots, trunk/card selection) using existing archive behavior patterns.
3. Maintain console-safe constraints and existing fallback semantics for thumbnails.

Must not:
1. alter business boundaries between Auto-Trader and P2P.
2. add live XML/upload/restart execution paths in this local finish sprint.

---

## 5) Prioritized 4-Slice Implementation Sequence

## Slice A — UI foundation and local asset registry

Scope:
1. Establish shared static asset structure under dxemb/web/static for css/js/map/items used by recovered pages.
2. Add deterministic asset registry/manifest to track source and fallback rules.
3. Introduce shared DayZ visual shell (base layout/static css) replacing fragmented inline-only visual approach where safe.

Acceptance criteria:
1. Existing pages still render and routes remain reachable.
2. Shared stylesheet/js loads from local static path.
3. Broken-image behavior replaced with explicit fallback image logic.
4. Tests added/updated for route reachability and non-regression.

Commit target:
- ui-sliceA: restore verified DayZ visual foundation

## Slice B — Trader thumbnail catalog workflow restoration

Scope:
1. Move catalog page rendering to shared templates/static (or equivalent reusable view structure) while preserving existing catalog service behavior.
2. Wire local-first thumbnail resolution path with resolver fallback.
3. Improve card/detail browsing for real DayZ image cards.

Acceptance criteria:
1. Catalog list/detail show real thumbnails for available local assets.
2. Enable/disable controls keep current behavior.
3. Search/filter/page behavior unchanged functionally.
4. Route tests pass and include thumbnail/fallback assertions.

Commit target:
- ui-sliceB: restore trader thumbnail catalog workflow

## Slice C — Interactive local loot map workflow restoration

Scope:
1. Add map route + template + static JS integration using proven map coordinate model.
2. Implement local click-to-coordinate, grid display, and read-only or dry-run output panel.
3. Integrate map page into dashboard navigation.

Acceptance criteria:
1. Map renders locally and supports click selection.
2. Coordinate conversion and grid label output are stable.
3. No mutation/live actions occur.
4. Tests cover route availability and safe behavior.

Commit target:
- ui-sliceC: restore interactive local loot map workflow

## Slice D — Vehicle builder workflow restoration and dashboard finish

Scope:
1. Upgrade vehicle builder UX using existing resolver APIs and archive interaction patterns.
2. Add trunk/cargo builder panel in local-safe mode (preview/export local artifact only).
3. Final dashboard integration: trader, map, vehicle builder unified nav + consistency pass.

Acceptance criteria:
1. Vehicle family/color/slot selection is functional.
2. Trunk/cargo preview validates locally with no live side effects.
3. Existing vehicle API endpoints remain compatible.
4. End-to-end local UI tests for routes/pages pass.

Commit target:
- ui-sliceD: restore console-safe vehicle builder workflow

---

## 6) Validation Strategy per Slice

Required per slice:
1. git diff --check
2. git diff --stat
3. targeted unittest route/adapter tests
4. any updated UI route tests for non-mutation guarantees
5. git status --short

End-of-sprint validation:
1. consolidated tests for all affected web routes
2. explicit check that no Nitrado/FTP/XML/live tokens were introduced
3. docs reconciliation in PROJECT_CONTINUITY and FEATURE_RECOVERY_LEDGER after functional slices are complete

---

## 7) Rollback/Restore Plan

1. Keep each slice in isolated commit(s) with clear prefix.
2. If regression appears, revert only the failing slice commit(s) rather than mixed rollback.
3. Preserve source-of-truth data files and existing APIs; avoid destructive rewrites.
4. Maintain branch-level safety by validating clean diff boundaries before each commit.

---

## 8) Branch and Continuity Note

Observed current head during planning:
- feature/local-finish-ui-recovery at same head lineage as origin/PERM in prior session summary context.

Action:
- Continue this sprint on current active branch unless owner requests explicit branch switch.

---

## 9) Immediate Execution After This Plan Commit

1. Commit this file only.
2. Begin Slice A implementation immediately.
3. Keep boundary checks active (no live external integrations, no forced restart paths, no Auto-Trader/P2P boundary erosion).

---

End of plan.
