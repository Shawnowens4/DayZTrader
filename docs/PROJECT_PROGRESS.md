# PROJECT_PROGRESS

Single source of truth: dxemb/shared/catalog/data/project_progress.json

## Weight Rationale

Higher weights are assigned to compatibility safety, vehicle builder readiness, map readiness, catalog workflow, and regression health.
Cosmetic-only or deferred live-phase work does not inflate local-finish progress.

## Local-Finish Progress Bars

- Project safety and repository health          [########--]  80%  locally_tested
- Docker/local startup and database health      [########--]  80%  locally_tested
- Web visual foundation and responsive design   [########--]  80%  locally_tested
- Trader catalog browsing, search, filters, and [########--]  80%  locally_tested
- DayZ image/thumbnail coverage                 [#---------]  10%  discovery
- Console vehicle image/color coverage          [#---------]  10%  discovery
- Console vehicle compatibility and part valida [#---------]  10%  blocked
- Vehicle builder local preview                 [####------]  40%  blocked
- Loot/Chernarus map local preview              [----------]   0%  not_started
- Auto-Trader admin-stock workflow              [#---------]  10%  discovery
- Player Market and P2P escrow separation       [#---------]  10%  discovery
- Wallet/immutable ledger                       [#---------]  10%  discovery
- Games/tasks/missions local workflows          [#---------]  10%  discovery
- Discord bot prefix commands                   [#---------]  10%  discovery
- Discord slash-command/local dashboard entry   [#---------]  10%  discovery
- Local test coverage and regression health     [########--]  80%  locally_tested
- Documentation, recovery ledger, and manual te [######----]  60%  implemented_unverified

- Overall local-finish                          [####------]  41%  medium confidence

## Calculation Inputs

| ID | Product Area | Weight | Percent | Weighted Contribution |
|---|---|---:|---:|---:|
| 1 | Project safety and repository health | 7 | 80 | 560 |
| 2 | Docker/local startup and database health | 5 | 80 | 400 |
| 3 | Web visual foundation and responsive design | 8 | 80 | 640 |
| 4 | Trader catalog browsing, search, filters, and item thumbnails | 10 | 80 | 800 |
| 5 | DayZ image/thumbnail coverage | 6 | 10 | 60 |
| 6 | Console vehicle image/color coverage | 6 | 10 | 60 |
| 7 | Console vehicle compatibility and part validation | 12 | 10 | 120 |
| 8 | Vehicle builder local preview | 10 | 40 | 400 |
| 9 | Loot/Chernarus map local preview | 8 | 0 | 0 |
| 10 | Auto-Trader admin-stock workflow | 3 | 10 | 30 |
| 11 | Player Market and P2P escrow separation | 3 | 10 | 30 |
| 12 | Wallet/immutable ledger | 3 | 10 | 30 |
| 13 | Games/tasks/missions local workflows | 2 | 10 | 20 |
| 15 | Discord bot prefix commands | 3 | 10 | 30 |
| 16 | Discord slash-command/local dashboard entry | 2 | 10 | 20 |
| 17 | Local test coverage and regression health | 8 | 80 | 640 |
| 18 | Documentation, recovery ledger, and manual test checklist | 4 | 60 | 240 |

Overall formula: sum(weight * percent_complete) / sum(active weights) = 4080 / 100 = 41%

## Deferred/Live Phase (Excluded From Local-Finish Denominator)

| ID | Product Area | Status | Weight |
|---|---|---|---:|
| 14 | Nitrado delivery/scheduler design | intentionally_disabled | 0 |
| 19 | Public hosting/Cloudflare/DNS | intentionally_disabled | 0 |
| 20 | Real Nitrado/FTP/XML/server write integration | intentionally_disabled | 0 |

## What Changed Since Last Verified Commit

### Newly Completed
- None in this audit-only slice.

### Percentage Increases/Decreases And Why
- Added measurable baseline percentages tied to verified Slice A/B and audit evidence.
- Compatibility and vehicle-color areas remain discovery/blocked pending owner console evidence.

### New Blockers
- Owner console XML/mission evidence required to verify compatibility mappings.

### Owner Actions Needed
- Provide console XML files or vehicle-only blocks listed in docs/CONSOLE_VEHICLE_SOURCE_IMPORT_GUIDE.md

### Next Highest-Value Slice
- Import owner console evidence into review records, then promote specific rows from owner_review_required toward verified mappings.

## Owner Action Queue

- Provide owner-owned console vehicle evidence inputs listed in docs/CONSOLE_VEHICLE_SOURCE_IMPORT_GUIDE.md.
- Resolve grouped queue rows in docs/CONSOLE_VEHICLE_OWNER_REVIEW_QUEUE.md in listed priority order.
