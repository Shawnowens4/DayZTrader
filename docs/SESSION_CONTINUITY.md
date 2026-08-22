# Session Continuity

## Confirmed Current State

- Working branch: `feature/local-finish-ui-recovery`.
- The working tree already contains uncommitted Flask/Jinja simplification work; do not discard or commit it without explicit approval.
- `docs/PROJECT_CONTINUITY.md` remains useful for verified backend history, but its `PERM` branch baseline and former next-work item are not the active session direction.
- `docs/PROJECT_BASELINE_OLDBASE.md` is the frontend product-direction baseline.
- `docs/IMPLEMENTATION_MAP.md` records the integration sequence and backend attachment boundaries.
- Oldbase is the target frontend identity; the current simplified UI is transitional.

## Planned Refactor Direction

- Audit oldbase by section and dependency, not by immediately rewriting it.
- Preserve and repair the vehicle and nested item builders.
- Add Trader in oldbase style using oldbase item-catalog interaction patterns.
- Attach verified repository backends through narrow boundaries.
- Keep simplified routes until working replacements are verified.

## Open Questions

- Exact oldbase section/function inventory and broken-state list.
- Exact backend endpoint/service match for each oldbase data dependency.
- Final player-facing bank/cash language.
- Safe extraction boundary, if any, after oldbase behavior is repaired.

## Next Targeted Task

Create an indexed oldbase audit covering:

1. page regions and visual tokens;
2. vehicle builder state, handlers, and review output;
3. trunk/bag/bundle/nested item state and handlers;
4. item-card and modal patterns reusable by Trader;
5. mock/static data boundaries;
6. backend attachment seams and contract tests.

Use `rg` and bounded line reads. Do not perform a full linear reread unless indexing shows critical behavior that cannot be traced selectively.

## Verified Targeted Audit Anchors

- Oldbase vehicle markup is centered around `vehicleMain`, `vehicleGrid`, and `selectedVehicle`; selection/render logic begins near `renderVehicles`.
- Configure/workbench behavior is spread across the Tab 3 scripts, including quick/workbench rendering, cargo context, nested item addition, modal review, and file-derived catalog rendering.
- Oldbase already renders `catalog-card` item choices for builder use, but this is not the intended Trader.
- Current attachment candidates are catalog search/detail APIs, thumbnail resolvers, vehicle builder payloads, guarded catalog routes, wallet ledger services, Auto-Trader product/order previews, and Trader/wallet/Auto-Trader Discord cogs.
- These anchors are sufficient for a bounded audit; a full linear oldbase reread is not currently required.

## Verified Builder Audit Findings

- Vehicle selection uses static `vehicles`, `selected`, and `selectedColors`; `renderVehicles` rebuilds both card and selected-summary DOM.
- Vehicle confirmation is handled by the base script and again by `dayz-workflow-pass-script`.
- `tab3-clickable-blank-state-script` owns a private `{quick, builds}` state while `dayz-workflow-pass-script` owns `window.__DZBuilderWorkflow`; both target the same Quick Build and Workbench DOM.
- The workflow script binds direct handlers, a capturing document handler, and a 1.5-second rerender loop. This makes ownership and editable input persistence unsafe.
- Chance fields render, but no audited handler writes edited values back to state. Quantity and capacity enforcement are absent.
- Explicit trunk, bag, and bundle symbols/state were not found. Current nesting is gun-child oriented through `gunChildren`.
- Catalog-card nesting derives placeholder children `Attachment` and `Cargo` from spawnable membership rather than authoritative child classnames.
- Restricted/default items and the visible strict/filter labels are not backed by a shared enforcement path.
- The current catalog metadata presents slots and weight, but the builder does not use them for capacity validation.
- Preserve the item-card, modal-confirmation, nested-child rows, selected summary, and workbench review patterns for the later Trader.

## Next Repair Task

Stabilize one oldbase builder controller without changing its visual identity:

1. retire the private competing Tab 3 state/handlers;
2. keep one `window.__DZBuilderWorkflow` state and delegated event path;
3. remove polling rerenders;
4. persist chance edits;
5. block restricted additions;
6. keep unsupported quantity/capacity/trunk/bag/bundle claims explicitly non-enforced;
7. add focused oldbase contract tests before backend attachment.

## Required Session Start Order

1. Read `docs/PROJECT_BASELINE_OLDBASE.md`.
2. Read `docs/IMPLEMENTATION_MAP.md`.
3. Read `docs/SESSION_CONTINUITY.md`.
4. Consult relevant verified history in `docs/PROJECT_CONTINUITY.md`.
5. Check branch/status.
6. Read only source sections needed for the current task.

## Oldbase Controller Repair - In Progress

- Baseline checkpoint: `78882ff` (`ui: checkpoint guided trader visual foundation`).
- Retired the duplicate private Tab 3 controller so it cannot own builder state or bind competing actions.
- `window.__DZBuilderWorkflow` remains the one active state controller.
- Removed direct per-element workflow bindings and the 1.5-second polling rerender.
- Added delegated main-item chance persistence.
- Restricted catalog cards are explicitly disabled and guarded in the action path.
- Spawnable membership is no longer presented as authoritative child compatibility.
- Still unresolved by design: trunk capacity, quantities, bags, bundles, and authoritative nested attachment compatibility.
