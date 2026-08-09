# DayZTrader / DXEMB — Feature Recovery Ledger

> Permanent completeness checklist.
> Every Copilot/AI session must read this file together with
> `docs/PROJECT_CONTINUITY.md` before planning or editing.
>
> Rule: No feature may be declared removed, obsolete, finished, or replaced
> without an explicit ledger update explaining the decision, evidence, impact,
> and owner approval.
>
> Status labels:
> - Active verified
> - Active partial
> - Archive-only
> - Planned
> - Needs inventory
> - Needs recovery
> - Needs redesign
> - Intentionally deferred
> - Rejected by owner

---

## Required Session Gate

Before any implementation work, the agent must:

1. Read `docs/PROJECT_CONTINUITY.md`.
2. Read this ledger in full.
3. Run Git status/branch/latest-commit checks.
4. Identify which ledger rows are touched by the proposed work.
5. State whether the work can break, replace, duplicate, or defer any ledger row.
6. Update both documents after verified work.
7. Never silently reduce scope because a feature is absent from the active branch.

---

## Product Boundaries

### Auto-Trader
- Admin/server-owned store only.
- Admin controls allowed items, kits, vehicles, prices, availability, and sellability.
- Can physically spawn only approved items/kits/vehicles for the buyer through
  a dedicated, audited, Nitrado-aware Auto-Trader order/spawn pipeline.
- No claim codes or virtual delivery.
- Never represents player-to-player sales.

### Player Market + Escrow
- One connected P2P system.
- Player-owned listings and escrow lifecycle: hold, purchase, cancellation,
  dispute, refund, release, payout, and physical pickup confirmation.
- Never creates or spawns the seller's item or vehicle.
- Non-running vehicles cannot be listed.
- Buyer trunk screenshot at sale; seller screenshot only during dispute.

### Console and Nitrado
- Xbox and PlayStation console DayZ only.
- No PC-only/mod-only/Arma mechanics.
- Cargo uses quantity, chance, and damage only; no liquid values.
- Nitrado is outbound-poll only; never force restarts.
- Spawn writes occur only against confirmed restart timing.

---

## System Inventory

| ID | System / feature | Required behavior | Current PERM evidence | Archive/ZIP evidence | Status | Recovery decision | Notes |
|---|---|---|---|---|---|---|---|
| CORE-01 | Docker local stack | Bot, web, DB boot locally and stop cleanly | Verified at `503be4b` | Unknown | Active verified | Preserve | `/health` returns HTTP 200 with DB connected |
| CORE-02 | PostgreSQL local DB | Clean initialization from `init.sql` | Verified at `503be4b`; schema contract tests pass on disposable DB (Slice 2) | Unknown | Active verified | Preserve | Local dev DB volume is disposable |
| CORE-03 | Neon PostgreSQL | Hosted DB configuration and safe deployment path | Not verified | Unknown | Planned | Audit later | Never expose credentials |
| CORE-04 | Test framework | Repeatable isolated automated tests | Added unittest harness with disposable PostgreSQL test-db utilities and passing smoke tests (`tests/harness/postgres_isolated.py`, `tests/test_harness_smoke.py`); schema contracts pass in `tests/test_schema_contracts.py`; moderation audit tests pass in `tests/test_moderation_audit_service.py` | `C:\DXEMB\tests` (integration/service/cog tests including economy/escrow/marketplace) | Active partial | Expand with moderation adapters, ticket service, and onboarding dry-run contracts | Use archive tests as recovery reference; adapt to current PERM architecture |
| BOT-01 | Discord bot startup | Bot loads safely and reports state | Present; no-op safe mode verified | Unknown | Active partial | Preserve/audit | Live token/guild test pending |
| BOT-02 | Health commands | Prefix + slash health diagnostics | Present | Unknown | Active partial | Preserve/audit | Live Discord sync pending |
| BOT-03 | Trader browsing | Guided item catalog/trader navigation | Present | Unknown | Active partial | Audit | Not purchase/delivery pipeline |
| BOT-04 | Moderation bot | Warnings, staff actions, roles, logs, permission checks | Slice A added local moderation data contract + immutable audit service (`dxemb/db/migrations/003_moderation_audit_foundation.sql`, `dxemb/shared/moderation_audit_service.py`) with passing tests | `C:\DXEMB\discord_bot\src\cogs\moderation.py`; `C:\DXEMB\core\services\moderation_service.py`; `C:\DXEMB\core\services\audit_service.py` | Active partial | Build safe command adapters next | Duplicate-generation moderation file confirmed; split/adapt before enabling any commands |
| BOT-05 | Channel automation | Welcome, announcements, staff logs, private threads, configured IDs | Not verified in active PERM runtime | `C:\DXEMB\discord_bot\src\cogs\user.py`; `C:\DXEMB\core\services\user_service.py` | Needs inventory | Recover if present | Slice 5 found no dedicated archive tests for channel automation |
| BOT-06 | Onboarding/profile/stats | User creation, starter info, profile, reputation, stats | Design inventory completed in Slice 5 (`docs/MODERATION_COMMUNITY_RECOVERY_PLAN.md`) | `C:\DXEMB\discord_bot\src\cogs\user.py`; `C:\DXEMB\core\services\user_service.py`; `C:\DXEMB\tests\test_user_cog.py`; `C:\DXEMB\tests\test_user_service.py` | Needs recovery | Recover/adapt | Needs wallet boundary and PERM-compatible service contracts |
| BOT-07 | Support tickets | Private ticket/thread, category, assignment, close/resolve | No active PERM implementation verified | No direct module match found in `C:\DXEMB` or ZIP inventory | Needs inventory | Design first | Slice 5 gap: ticket-specific archive modules/tests were not identified |
| ECON-01 | Wallet | User balances and safe credit/debit services | Additive foundation migration and service implemented: `dxemb/db/migrations/001_wallet_ledger_foundation.sql`, `dxemb/shared/wallet_ledger_service.py`, `tests/test_wallet_ledger_service.py` | `C:\DXEMB\discord_bot\src\cogs\economy.py`; `C:\DXEMB\discord_bot\src\cogs\wallet.py`; `C:\DXEMB\core\services\economy_service.py`; `C:\DXEMB\database\migrations\004_economy_tables.sql` | Active partial | Build then integrate | Structured modules are preferred source over `BACKUP_PHASE*` monolith snapshots |
| ECON-02 | Ledger | Immutable audit for every wallet change | Immutable ledger table + no-update/no-delete triggers in additive migration; service tests pass for audit/idempotency flows | `C:\DXEMB\database\migrations\004_economy_tables.sql`; `C:\DXEMB\database\migrations\001_initial_schema.sql`; `C:\DXEMB\tests\test_economy_service.py` | Active partial | Build then integrate | Build ledger as authoritative audit layer before game/reward payouts |
| ECON-03 | Admin economy tools | Adjust balances with reason/audit trail | Not verified | Needs inventory | Needs inventory | Recover/adapt | Must use ledger |
| GAME-01 | Casino/games | Server-side deterministic RNG, wager/payout records | Not present in active audit | `C:\DXEMB\discord_bot\src\cogs\games.py`; `C:\DXEMB\core\services\game_service.py`; `C:\DXEMB\tests\test_end_to_end.py` | Needs inventory | Recover/adapt | Feature-toggle gated |
| GAME-02 | Game sessions | Wager, outcome, payout, seed, timestamp audit | Not present in schema | Needs inventory | Needs recovery | Design then build | Wallet ledger integration |
| GAME-03 | Daily tasks | Definitions, progress, rewards, reset cycle | Not verified | `C:\DXEMB\discord_bot\src\cogs\economy.py`; `C:\DXEMB\core\services\game_service.py` | Needs inventory | Recover/adapt | Midnight UTC rule |
| GAME-04 | Achievements | Definitions, unlocks, one-time rewards | Not verified | `C:\DXEMB\core\models\achievement.py`; `C:\DXEMB\core\services\achievement_service.py`; `C:\DXEMB\tests\test_user_service.py` | Needs inventory | Recover/adapt | Wallet ledger integration |
| GAME-05 | Missions/bounties | Create, track, reward, claim, admin moderation | Not verified | Needs inventory | Needs inventory | Recover/adapt | Preserve legacy behavior if valid |
| GAME-06 | Raffles/events | Tickets, winners, audit, announcements | Not verified | Needs inventory | Needs inventory | Recover/adapt | Feature-toggle gated |
| AUTO-01 | Admin catalog | Allowed items, price, enabled/sellable controls | Catalog/admin routes present | Needs inventory | Active partial | Audit/extend | Console-safe only |
| AUTO-02 | Vehicle builder | Admin-approved vehicle presets and valid parts/cargo | Present | Needs inventory | Active partial | Audit/extend | No PC/mod content |
| AUTO-03 | Auto-Trader products | Admin-owned items/kits/vehicles/hordes/airdrops | Not schema-backed | Needs inventory | Needs recovery | Design then build | Separate from market |
| AUTO-04 | Trader orders | Payment to completion state machine | Not present | Needs inventory | Needs recovery | Design then build | Dedicated `TraderOrder` domain |
| AUTO-05 | Spawn queue | Audited physical spawn request/attempt/failure/refund | Not present | Needs inventory | Needs recovery | Design then build | No claim codes |
| AUTO-06 | Custom kits | Console-valid attachment/nesting builder | Not verified | Needs inventory | Needs inventory | Recover/adapt | Validate build-time |
| AUTO-07 | Zombie hordes | Admin product and controlled spawn flow | Not verified | Needs inventory | Needs inventory | Recover/adapt | Feature-toggle gated |
| AUTO-08 | Airdrops | Buyer location, randomized contents, warning/announcement | Not verified | Needs inventory | Needs inventory | Recover/adapt | Location player-chosen |
| MARKET-01 | Player listings | P2P item/vehicle listings with lifecycle | Additive foundation migration/service implemented: `dxemb/db/migrations/002_market_escrow_foundation.sql`, `dxemb/shared/market_escrow_service.py`, `tests/test_market_escrow_service.py` | `C:\DXEMB\discord_bot\src\cogs\marketplace.py`; `C:\DXEMB\core\services\marketplace_service.py`; `C:\DXEMB\database\migrations\002_marketplace_tables.sql`; `C:\DXEMB\tests\test_marketplace_service.py` | Active partial | Build then integrate | Never server-spawn; delivery mode constrained to `P2P_PHYSICAL` |
| MARKET-02 | P2P escrow | Holds, release, cancel, refund, dispute, payout | Foundation lifecycle and audit events implemented in additive schema/service with tests for hold/release/dispute/refund | `C:\DXEMB\discord_bot\src\cogs\escrow.py`; `C:\DXEMB\core\services\escrow_service.py`; `C:\DXEMB\database\migrations\003_escrow_schema.sql`; `C:\DXEMB\tests\test_escrow_service.py`; `C:\DXEMB\tests\test_dispute_service.py` | Active partial | Build then integrate | No Auto-Trader behavior; no runtime spawn path added |
| MARKET-03 | Marketplace moderation | Admin review and dispute actions | Not verified | Needs inventory | Needs inventory | Recover/adapt | Audit every action |
| NIT-01 | Nitrado/FTP client | Console file pull/upload/backup actions | Not verified | `dayz-console-trader-bot.zip: dayz-console-trader-bot/bot/services/nitrado_client.py`; `dayz-console-trader-bot.zip: dayz-console-trader-bot/bot/services/ftp_client.py`; `dayz-console-trader-bot.zip: dayz-console-trader-bot/bot/services/xml_generator.py` | Needs inventory | Recover/adapt | Outbound only |
| NIT-02 | Restart scheduler | Poll/cached restart windows | Not present in active audit | Needs inventory | Needs recovery | Design then build | Never force restart |
| NIT-03 | Spawn-file writer | Controlled writes before confirmed restart | Not present | Needs inventory | Needs recovery | Design then build | Failure alerts/refunds |
| NIT-04 | Status scheduler | 5-minute status checks and 30-minute file pulls | Not verified | Needs inventory | Needs inventory | Recover/adapt | Separate tool if needed |
| WEB-01 | Flask dashboard | Health/status/admin shell | Present | Needs inventory | Active partial | Preserve/audit | Browser route test pending |
| WEB-02 | Catalog administration | Item cards, prices, availability | Present | Needs inventory | Active partial | Preserve/audit | Bulk tools pending |
| WEB-03 | Vehicle administration | Vehicle catalog/builder endpoints | Present | Needs inventory | Active partial | Preserve/audit | Validate console data |
| WEB-04 | Economy dashboard | Wallet/ledger/admin adjustments | Not verified | Needs inventory | Needs recovery | Recover/adapt | Requires ECON tables |
| WEB-05 | Ticket dashboard | View/assign/close tickets | Not verified | Needs inventory | Needs inventory | Recover/adapt | Requires BOT-07 |
| WEB-06 | Order dashboard | Auto-Trader order/spawn management | Not verified | Needs inventory | Needs recovery | Design then build | Requires AUTO-04 |
| WEB-07 | Market dashboard | Listing/dispute moderation | Not verified | Needs inventory | Needs recovery | Design then build | Requires MARKET-01 |
| WEB-08 | Tester/audit dashboard | Bugs, feature checks, tester workflow | Separate related app | Needs inventory | Needs inventory | Keep separate unless approved | Do not merge blindly |
| DATA-01 | DayZ item catalog | types.xml, display names, thumbnails, pricing/categories | Present | Needs inventory | Active partial | Preserve/audit | Console validation needed |
| DATA-02 | Vehicle thumbnails/resolver | Variant-safe vehicle visuals | Present | Needs inventory | Active partial | Preserve/audit | Latest resolver committed |
| DATA-03 | Legacy archives | ZIP and `C:\DXEMB` recovery sources | Present/not yet inventoried | `C:\DXEMB`; `dayz-console-trader-bot.zip`; `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot` | Needs inventory | Read-only inventory | ZIP overlaps archive clone and is not automatically newest; use source-by-source comparison and never bulk-copy |
| OPS-01 | Backups/recovery | DB/file backup and restore procedure | Not verified | Needs inventory | Needs inventory | Design later | No secrets in Git |
| OPS-02 | CI/GitHub Actions | Automated checks after local workflow stable | Not present/verified | Unknown | Planned | Later | Local test path first |
| OPS-03 | Project status script | One-command branch/container/test status | Not present | Unknown | Planned | Build soon | Fast workflow aid |

---

## Non-Negotiable Completion Rules

- A feature is not complete because it appears in an archive, roadmap, or chat.
- A feature becomes **Active verified** only after implementation, tests, and
  recorded evidence.
- A feature coded without passing tests cannot exceed 50% completion.
- Before a new subsystem is built, compare this ledger, current PERM source,
  archive source, ZIP source, schema, routes, cogs, tests, and dependencies.
- If a prior feature is recovered, record:
  - source path
  - active destination
  - adaptations made
  - validation evidence
  - commit hash
  - remaining limitations
- Never delete an archive-only feature row merely because it is not active yet.

---

## Required Reconciliation

At the end of each major milestone, the agent must:
1. Re-read this ledger.
2. Compare changed files against affected ledger IDs.
3. Identify omissions, regressions, duplicates, and stale references.
4. Update row status and notes with evidence.
5. Update `PROJECT_CONTINUITY.md` with the next highest-value ledger item.
6. Commit documentation updates with the implementation checkpoint.

---

## Current Next Action

Perform the strict read-only **Legacy Feature Recovery Inventory** across:
- Current `PERM` repository
- `C:\DXEMB`
- `dayz-console-trader-bot.zip`

Do not edit or restore anything until the inventory identifies the most complete,
newest, and compatible source for every missing system.

### Inventory Notes (2026-08-08)
- Preferred recovery candidates are structured modules under `C:\DXEMB\core`, `C:\DXEMB\discord_bot\src`, and `C:\DXEMB\database\migrations`, not `BACKUP_PHASE*` monolith snapshots.
- `C:\DXEMB\discord_bot\src\cogs\moderation.py` contains duplicate generations and requires controlled adaptation by slice.
- ZIP evidence is useful reference but overlaps with `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot`; do not assume ZIP is newest.

### Recovery Sprint Updates (2026-08-08)
- Slice 1 completed: added design-only domain/model plan at `docs/WALLET_LEDGER_MARKET_ESCROW_DESIGN.md`.
- Slice 1 completed: added minimal isolated test harness utilities in `tests/harness/postgres_isolated.py`.
- Slice 1 completed: harness smoke tests passed via `python -m unittest discover -s tests -p "test_*.py" -v`.
- Slice 1 validation evidence recorded: `git diff --check`, `docker compose config`, `docker compose down`.
- Slice 2 completed: schema contract tests added in `tests/test_schema_contracts.py` for `player`, `item`, and `escrow_transaction` plus catalog query compatibility.
- Slice 2 validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_schema_contracts -v`, `docker compose config`, `docker compose down`.
- Slice 3 completed: additive wallet+ledger foundation added via `dxemb/db/migrations/001_wallet_ledger_foundation.sql` and `dxemb/shared/wallet_ledger_service.py`.
- Slice 3 completed: service tests added in `tests/test_wallet_ledger_service.py` covering credit, debit, insufficient funds, duplicate reference idempotency, and audit history.
- Slice 3 validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_wallet_ledger_service -v`, `docker compose config`, `docker compose down`.
- Slice 4 completed: additive P2P listing+escrow foundation added via `dxemb/db/migrations/002_market_escrow_foundation.sql` and `dxemb/shared/market_escrow_service.py`.
- Slice 4 completed: service tests added in `tests/test_market_escrow_service.py` covering running-vehicle guard, hold, release-with-pickup, dispute, refund, and delivery-mode no-spawn enforcement.
- Slice 4 validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_market_escrow_service -v`, `docker compose config`, `docker compose down`.
- Slice 5 completed (design-only): moderation/community inventory and integration plan documented in `docs/MODERATION_COMMUNITY_RECOVERY_PLAN.md`.
- Slice 5 confirmed: `C:\DXEMB\discord_bot\src\cogs\moderation.py` contains duplicate generation patterns and requires modular adaptation.
- Slice 5 confirmed: archive tests exist for user/admin domains but no explicit ticket-automation test suite was identified.
- Slice A completed: moderation data contract + immutable audit foundation added via `dxemb/db/migrations/003_moderation_audit_foundation.sql` and `dxemb/shared/moderation_audit_service.py`.
- Slice A validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_moderation_audit_service -v`, `docker compose config`, `docker compose down`.
- Next slice: moderation command adapters limited to warn, local status query, and dry-run preview only (no Discord mutation actions).

---
End of permanent feature recovery ledger.
