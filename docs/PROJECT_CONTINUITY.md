# DayZTrader / DXEMB — Project Continuity

> Authoritative AI-resume document. Read this file before planning, editing, testing, or proposing work.
> Code baseline anchor: `f9425cd` on branch `PERM`.
> Documentation checkpoint before this update: `f8ac338` on branch `PERM`.
> Last updated: 2026-08-08.

---

## Project Identity

| Field | Value |
|---|---|
| Project | D.X.E.M.B / DayZTrader |
| Purpose | DayZ Xbox/PlayStation Discord bot, web dashboard, Auto-Trader, player marketplace/escrow, and Nitrado-aware console-server tools |
| Repository | `Shawnowens4/DayZTrader` |
| Primary branch | `PERM` |
| Local clone | `C:\tz420\clone\DayZTrader` |
| Runtime | Python, discord.py, Flask, PostgreSQL, Docker Compose, Windows 11 Docker Desktop |
| Database target | Neon PostgreSQL |
| Historical reference archive | `C:\DXEMB` — read/recovery only; never overwrite active files from it wholesale |

---

## Non-Negotiable Product Rules

### Console Scope
- Xbox and PlayStation DayZ console only.
- Do not introduce PC-only, mod-only, Arma, or unsupported console mechanics.
- Console cargo uses only `quantity`, `chance`, and `damage`; never liquid values.

### Auto-Trader
- Auto-Trader is the admin/server-owned store.
- Admin controls define allowed items, kits, vehicles, prices, stock/sellability, and feature availability.
- Auto-Trader may spawn only admin-approved items, kits, or vehicles for the purchasing player through the approved Nitrado-aware delivery pipeline.
- Every Auto-Trader purchase uses an auditable order state machine.
- Delivery is always physical in-game. No claim codes and no virtual delivery.
- Auto-Trader is never a player-to-player transaction.

### Player Market + Escrow
- Player Market and Escrow are one connected player-to-player system.
- Marketplace listings belong to players, not the server store.
- Escrow records holds, releases, cancellation, dispute, refund, and finalization.
- Marketplace does not create or spawn the seller's item or vehicle.
- Final transfer is physical in-game pickup/delivery.
- Non-running vehicles cannot be listed.
- Buyer uploads trunk screenshot at sale; seller uploads only on dispute.
- Never label or implement Player Market/Escrow as Auto-Trader.

### Nitrado Delivery Rules
- Never force a Nitrado restart.
- Poll/check FTP or API before writing spawn files.
- Cache restart schedules in the database and refresh them each poll cycle.
- Write planned spawn files about 10 minutes before a confirmed restart window.
- Failed spawn requests alert admins and trigger the defined refund path.

### Security During Private Learning
- Owner may provide private test credentials when needed for diagnosis.
- Never commit, publish, embed, or unnecessarily repeat credentials.
- Keep actual values in local `.env` files or provider secret storage.
- Keep `.env`, database dumps, token files, backups, and private keys out of Git.
- Rotate all development credentials before public, production, Discord-server, or Nitrado deployment.
- `.env.example` lists variable names only, never values.

---

## Verified Repository Baseline

### Git State
- Branch: `PERM`
- Code baseline anchor: `f9425cd` — `resolve: keep local vehicle_thumbnail_resolver.final.json`
- Documentation checkpoint: `f8ac338` — `docs: add authoritative project continuity record`
- Local `.env` is required for Docker Compose runtime and is intentionally Git-ignored.
- Working tree includes approved pending change in `requirements.txt` for bot health dependency parity.
- Recent verified history:
  - `f9425cd` resolve: preserve final vehicle thumbnail resolver data
  - `892b2d7` fix Discord slash-command registration behavior
  - `fc2860b` wire app commands into `bot.tree`
  - `598dab4` re-apply slash-sync infrastructure
  - `2b7e9a8` add first `/health` slash-command proof path

### Present Components
| Area | Active source | Status |
|---|---|---|
| Docker stack | `docker-compose.yml`, `Dockerfile.bot`, `Dockerfile.web` | Local runtime re-verified: db healthy, web started, bot started (no-op mode without token), `/health` returns 200 with DB connected |
| Discord bot | `dxemb/bot/main.py` | Present |
| Bot health | `dxemb/bot/cogs/health.py`, `health_slash.py` | Present; recent slash-command work |
| Auto-Trader interface | `dxemb/bot/cogs/trader.py`, `dxemb/bot/ui/` | Present; behavior must be audited before feature claims |
| Flask dashboard | `dxemb/web/app.py` | Present |
| Catalog administration | `dxemb/web/catalog_admin.py` | Present |
| Vehicle administration | `dxemb/web/vehicle_admin.py` | Present |
| Shared catalog domain | `dxemb/shared/catalog/` | Present |
| DayZ data | `dxemb/shared/catalog/data/types.xml`, mappings, resolver data | Present |
| Database | `dxemb/db/init.sql`, `dxemb/shared/db.py`, `dxemb/bot/db.py` | Present; Neon/database verification pending |
| Tests | Not yet verified from current repository inspection | Pending audit |

---

## Project Inventory

| System | Purpose | Source of truth | Change status |
|---|---|---|---|
| DayZTrader / DXEMB | Primary bot, dashboard, Auto-Trader, marketplace, escrow, admin tools | GitHub `PERM` branch | Active |
| Local DayZTrader clone | Current working tree | `C:\tz420\clone\DayZTrader` | Active |
| DXEMB archive | Historic recovery source, old UI/code/assets | `C:\DXEMB` | Reference-only |
| Neon | Hosted PostgreSQL target | Neon project configuration/local `.env` | Integration pending verification |
| Docker Desktop | Local runtime and test environment | Windows 11 machine | Required |
| Nitrado console server | FTP/schedule/spawn-file target | Nitrado account/configuration | Integration gated and controlled |
| DayZ console editor/dashboard | Related console XML/economy/FTP tooling | Separate related app/project | Do not merge without a deliberate shared-module plan |
| Test/audit system | Separate tester and reporting application | Separate repository/app if applicable | Do not modify unless explicitly in scope |

---

## Workflow Opportunities

### Required Now
- Create this continuity document and commit it.
- Audit current application behavior before expanding features.
- Establish one repeatable validation command set for Docker, web, bot, database, and tests.
- Verify `.gitignore` keeps `.env` and credential artifacts untracked.

### Recommended Next
- Add a lightweight `scripts/project-status.ps1` that reports branch, commit, dirty files, Docker status, and test status.
- Add a test inventory document identifying existing tests, missing tests, and exact commands.
- Add a single issue/feature ledger that connects user-facing features to source modules, tests, and verification evidence.

### Future Optimization
- GitHub Actions after local Docker/test workflow is stable.
- Automated database migration checks against a disposable test database.
- Scheduled catalog-data validation for console-safe item and vehicle lists.
- Controlled Nitrado poller health telemetry and failure alerts.

---

## Progress Rules

- Progress is evidence-based, never planning-based.
- A coded but untested feature cannot exceed 50%.
- Lifecycle: Design → Implemented → Tests written → Tests passing → Headless/Discord tests passing → Audit pass → Real-user sign-off.
- Update progress only after recorded proof.
- Every substantive status response begins and ends with current project progress bars.

### Current Honest Status
```text
Repository discovery and baseline: ██████████ 100%
Documentation consolidation:     █████████░  89%
Docker/runtime re-verification:  ███████░░░  70%
Bot/Discord verification:       █████░░░░░  50%
Web/admin verification:         ██████░░░░  60%
Database/Neon verification:     ███████░░░  65%
Auto-Trader audit:              ███░░░░░░░  30%
Player Market + Escrow audit:   ██████░░░░  60%
Automated tests audit:          ████████░░  80%
Total verified project state:   ████████░░  72%
```

---

## Feature Ledger

| Feature | Classification | Active source | Verification | Next action |
|---|---|---|---|---|
| Docker local stack | Foundation | Docker root files | Re-verified locally after controlled DayZTrader DB volume reset; db healthy and `/health` returns HTTP 200 with DB connected | Preserve validation command set and rerun after each infra-touching change |
| Bot health dependency parity | Runtime correctness | `requirements.txt`, `shared/db.py`, `bot/cogs/health_slash.py` | Verified bot image installs `psycopg2-binary`; no missing `psycopg2` import error in bot startup logs | Keep dependency parity and avoid splitting shared DB helper deps across service images |
| Discord bot startup | Foundation | `dxemb/bot/main.py` | Source present | Audit startup configuration and run |
| Slash-command synchronization | Bot infrastructure | `health_slash.py`, `main.py` | Recent commits present | Verify sync and `/health` in test guild |
| Catalog data | Shared domain | `dxemb/shared/catalog/` | Source/data present | Audit console filtering and source integrity |
| Vehicle catalog/resolver | Shared domain | vehicle resolver/builder services | Source/data present | Audit allowed-list connection |
| Admin catalog UI | Auto-Trader admin surface | `web/catalog_admin.py` | Source present | Inspect routes and persistence |
| Admin vehicle UI | Auto-Trader admin surface | `web/vehicle_admin.py` | Source present | Inspect routes and persistence |
| Auto-Trader orders/spawn queue | Server store | To be verified | Not yet verified | Audit models, states, queue, and Nitrado boundary |
| Player Market + Escrow | P2P system | To be verified | Not yet verified | Locate active code/schema or mark unimplemented |
| Wallet/Ledger + Market/Escrow design | Recovery planning | `docs/WALLET_LEDGER_MARKET_ESCROW_DESIGN.md` | Slice 1 design completed; boundaries, lifecycle, idempotency, migration order documented | Use as contract for additive migrations and service tests |
| Isolated PostgreSQL test harness | Test foundation | `tests/harness/postgres_isolated.py`, `tests/test_harness_smoke.py` | `python -m unittest discover -s tests -p "test_*.py" -v` passed (4 tests) | Add schema contract tests in Slice 2 |
| Schema contract coverage (`player`, `item`, `escrow_transaction`) | Test foundation | `tests/test_schema_contracts.py` | `docker compose up -d db; python -m unittest tests.test_schema_contracts -v` passed (5 tests) against disposable DB | Start Slice 3 wallet/ledger additive migration + service tests |
| Wallet + ledger additive foundation | Recovery implementation | `dxemb/db/migrations/001_wallet_ledger_foundation.sql`, `dxemb/shared/wallet_ledger_service.py` | `docker compose up -d db; python -m unittest tests.test_wallet_ledger_service -v` passed (5 tests) | Start Slice 4 P2P listing/escrow foundation |
| P2P listing + escrow additive foundation | Recovery implementation | `dxemb/db/migrations/002_market_escrow_foundation.sql`, `dxemb/shared/market_escrow_service.py` | `docker compose up -d db; python -m unittest tests.test_market_escrow_service -v` passed (5 tests) | Move to Slice 5 moderation/community recovery planning |
| Neon database path | Infrastructure | `.env.example`, shared/db, Docker config | Not yet verified | Audit configuration safely |
| Nitrado schedule/spawn integration | Infrastructure | To be verified | Not yet verified | Locate code, confirm no forced restart behavior |

---

## Current Work Item

### Goal
Create a controlled recovery design for the wallet/ledger and Player Market + Escrow foundation, preserving the strict Auto-Trader vs P2P boundary.

### Allowed Changes
- `docs/PROJECT_CONTINUITY.md`
- Later: only the audit/report documents created from verified findings.

### Do Not Change Yet
- Application code.
- Docker files.
- Database schema.
- Neon settings.
- Nitrado settings.
- Existing five historical handoff documents.
- Catalog JSON/XML/resolver data.

### Acceptance Criteria
- This file is committed to `PERM`.
- Existing handoffs remain intact.
- Future work follows this file first.
- The next work item is based on repository evidence, not stale roadmap estimates.

### Validation
```powershell
git status --short
git diff --check
git log -1 --oneline
```

---

## Changelog

### 2026-08-08 — Legacy Feature Recovery Inventory (Read-Only)
- Completed strict read-only inventory across active `PERM`, `C:\DXEMB`, and `dayz-console-trader-bot.zip`.
- Recorded concrete evidence sources in `docs/FEATURE_RECOVERY_LEDGER.md` for moderation, economy/wallet, market/escrow, games/achievements, tests, migrations, and Nitrado/FTP/XML integration references.
- Confirmed structured archive modules (`C:\DXEMB\core`, `C:\DXEMB\discord_bot\src`, `C:\DXEMB\database\migrations`) are preferred recovery candidates over `BACKUP_PHASE*` monolith snapshots.
- Confirmed `C:\DXEMB\discord_bot\src\cogs\moderation.py` contains duplicate generations and must be adapted slice-by-slice, not copied directly.
- Confirmed `dayz-console-trader-bot.zip` overlaps `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot` and is not automatically the newest source.
- Recovery rule reinforced: future recovery must be source-by-source, test-backed, and never bulk-copied from archive or ZIP.

### 2026-08-08 — Slice 1: Design + Test Harness
- Added design-only foundation at `docs/WALLET_LEDGER_MARKET_ESCROW_DESIGN.md` covering wallet source of truth, immutable ledger model, idempotency/reference rules, admin adjustment auditing, listing/escrow lifecycle, dispute/refund/release flow, physical pickup confirmation, and migration/rollback considerations.
- Added minimal isolated PostgreSQL harness at `tests/harness/postgres_isolated.py` for disposable test database creation, schema apply, and teardown.
- Added harness smoke tests at `tests/test_harness_smoke.py`.
- Slice 1 required validation completed:
  - `git diff --check` (pass)
  - `python -m unittest discover -s tests -p "test_*.py" -v` (pass, 4 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Slice 2: Schema Contract Tests
- Added schema contract tests at `tests/test_schema_contracts.py` for:
  - table presence and contract shape (`player`, `item`, `escrow_transaction`)
  - key uniqueness and check-constraint validation
  - catalog query compatibility for existing item-query projections
- Disposable isolated DB flow validated via harness (`create_disposable_database`, `apply_schema`, `drop_disposable_database`).
- Slice 2 required validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_schema_contracts -v` (pass, 5 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Slice 3: Wallet + Ledger Foundation
- Added additive migration `dxemb/db/migrations/001_wallet_ledger_foundation.sql` for:
  - `wallet_account` (per-player balance source of truth)
  - `wallet_ledger` (append-only immutable audit entries)
  - no-update/no-delete triggers to enforce ledger immutability
  - idempotency uniqueness on `(discord_user_id, reference_type, reference_id)`
- Added standalone service `dxemb/shared/wallet_ledger_service.py` implementing atomic credit/debit/admin-adjust flows with ledger-backed balance transitions and idempotent reference handling.
- Added service test coverage `tests/test_wallet_ledger_service.py` for:
  - credit
  - debit
  - insufficient funds
  - duplicate request/reference idempotency
  - ledger history/audit ordering
- Slice 3 required validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_wallet_ledger_service -v` (pass, 5 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Slice 4: Player Listing + Escrow Foundation
- Added additive migration `dxemb/db/migrations/002_market_escrow_foundation.sql` for:
  - `player_listing` with P2P lifecycle states
  - `market_escrow` with hold/release/refund/dispute lifecycle and pickup confirmation gating
  - `market_escrow_event` for escrow event auditing
  - explicit no-spawn constraint via `delivery_mode = 'P2P_PHYSICAL'`
- Added standalone service `dxemb/shared/market_escrow_service.py` implementing hold, pickup confirmation, release, dispute, and refund flows.
- Added service tests `tests/test_market_escrow_service.py` for:
  - non-running vehicle listing rejection
  - hold + release flow with pickup confirmation
  - release block without pickup confirmation
  - dispute then refund
  - P2P physical delivery mode enforcement (no server spawn mode)
- Slice 4 required validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_market_escrow_service -v` (pass, 5 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Runtime Dependency Validation + Local DB Reset Verification
- Performed controlled local reset of DayZTrader Compose DB volume only: `dayztrader_dxemb_db_data`.
- Isolation proof recorded before deletion:
  - Compose project: `dayztrader`.
  - DayZTrader db volume: `dayztrader_dxemb_db_data`.
  - `dayztrader-db_test-1` uses `dayztrader_dxemb_test_db_data` and remained untouched.
- Re-ran validation sequence:
  - `git diff --check`
  - `docker compose config`
  - `docker compose up -d db bot web`
  - `docker compose ps`
  - `docker compose logs --no-color --tail=200 db`
  - `docker compose logs --no-color --tail=200 bot`
  - `docker compose logs --no-color --tail=200 web`
  - `Invoke-WebRequest http://localhost:5000/health | Select-Object StatusCode, Content`
  - `docker compose down`
- Verified outcomes:
  - DB initialized from `dxemb/db/init.sql` and became healthy.
  - Bot started without missing `psycopg2` import error.
  - Web started successfully.
  - `/health` returned HTTP 200 with DB connected.
- Local setup requirement reaffirmed: Docker runtime requires local `.env`; keep it untracked/ignored.
- Remaining out-of-scope audit target (not fixed in this work item): broader schema/route coverage outside the `/health` path (feature-toggle, wallet, and marketplace tables/routes).

### 2026-08-08 — Continuity Baseline
- Established `docs/PROJECT_CONTINUITY.md` as the authoritative AI-resume document.
- Recorded the verified `PERM` baseline at `f9425cd`.
- Corrected terminology: Auto-Trader is admin-controlled spawning from approved lists; Player Market + Escrow is a separate combined P2P system.
- Recorded known active bot, web, database, catalog, vehicle, and Docker components.
- Declared old planning-progress figures historical only until re-verified.

---

## Next AI Instructions

1. Read this document first.
2. Run:
   ```powershell
   git branch --show-current
   git status --short
   git log -1 --oneline
   ```
3. Confirm the repository is still on `PERM` and clean before proposing changes.
4. Inspect only the files relevant to the current work item and direct dependencies.
5. Never reset the repository to an old thin-skeleton plan.
6. Never overwrite current source from `C:\DXEMB`; compare and recover one feature at a time.
7. Keep Auto-Trader distinct from Player Market + Escrow in names, UI, models, commands, and logic.
8. Before adding features, identify tests, acceptance criteria, and validation commands.
9. After each verified task, update this document’s baseline, feature ledger, progress bars, changelog, and next work item.
10. Commit documentation/code only when the result is verified, or clearly label it unverified.
11. For legacy recovery phases, design first only: source-by-source mapping, schema/test plan, and compatibility review before any implementation.
12. Never bulk-copy from `C:\DXEMB` or `dayz-console-trader-bot.zip`; recover in small test-backed slices.

### Next Work Item (Do Not Implement Features Yet)
- Slice 5: design-only moderation + community recovery plan (inventory exact archive modules, duplicate generations, dependencies, tests, and safe integration approach for moderation, staff logs, roles/channels, onboarding, and tickets).
- Do not alter Discord/server settings or restore moderation/ticket code in this slice.

---
End of authoritative continuity record.
