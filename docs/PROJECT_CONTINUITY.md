# DayZTrader / DXEMB — Project Continuity

> Authoritative AI-resume document. Read this file before planning, editing, testing, or proposing work.
> Code baseline anchor: `f9425cd` on branch `PERM`.
> Documentation checkpoint before this update: `f8ac338` on branch `PERM`.
> Last updated: 2026-08-10.

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
Documentation consolidation:     ██████████ 100%
Docker/runtime re-verification:  ████████░░  78%
Bot/Discord verification:       ████████░░  79%
Web/admin verification:         ████████░░  81%
Database/Neon verification:     ███████░░░  65%
Auto-Trader audit:              ██████░░░░  58%
Player Market + Escrow audit:   ████████░░  78%
Automated tests audit:          ██████████  97%
Total verified project state:   █████████░  92%
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
| Auto-Trader order foundation | Server store | `dxemb/db/migrations/006_auto_trader_order_foundation.sql`, `dxemb/shared/auto_trader_order_service.py`, `tests/test_auto_trader_order_service.py` | `docker compose up -d db; python -m unittest tests.test_auto_trader_order_service -v` passed (5 tests) | Extend toward controlled delivery scheduler design (no server writes yet) |
| Auto-Trader wallet bridge foundation | Server store | `dxemb/shared/auto_trader_wallet_bridge.py`, `tests/test_auto_trader_wallet_bridge.py` | `docker compose up -d db; python -m unittest tests.test_auto_trader_wallet_bridge -v` passed (3 tests) | Add delivery-preparation orchestration after restart-window design |
| Auto-Trader local bot/web previews | Server store | `dxemb/bot/cogs/autotrader_local.py`, `dxemb/web/app.py`, `tests/test_auto_trader_bot_adapter.py`, `tests/test_auto_trader_web_routes.py` | `docker compose up -d db; python -m unittest tests.test_auto_trader_bot_adapter tests.test_auto_trader_web_routes -v` passed (7 tests) | Keep read-only/dry-run; add auth/session controls later |
| Nitrado delivery scheduler design | Design-only | `docs/NITRADO_DELIVERY_SCHEDULER_DESIGN.md` | Design-only sprint completed with read-only archive reference review; no runtime integration/actions executed | Begin additive scheduler schema/service implementation slice only after explicit owner approval |
| Nitrado scheduler foundation (fake-provider) | Recovery implementation | `dxemb/db/migrations/007_nitrado_delivery_scheduler_foundation.sql`, `dxemb/shared/nitrado_delivery_decision_engine.py`, `dxemb/shared/nitrado_delivery_interfaces.py`, `dxemb/shared/nitrado_delivery_fakes.py`, `dxemb/shared/nitrado_delivery_scheduler_service.py`, `tests/test_nitrado_delivery_*` | `docker compose up -d db; python -m unittest tests.test_nitrado_delivery_scheduler_schema tests.test_nitrado_delivery_decision_engine tests.test_nitrado_delivery_scheduler_service tests.test_nitrado_delivery_fake_boundaries tests.test_nitrado_delivery_web_routes tests.test_auto_trader_web_routes -v` passed (31 tests) | Keep fake-only mode; require explicit owner approval before any live provider/file transport integration |
| Player Market + Escrow | P2P system | To be verified | Not yet verified | Locate active code/schema or mark unimplemented |
| Wallet/Ledger + Market/Escrow design | Recovery planning | `docs/WALLET_LEDGER_MARKET_ESCROW_DESIGN.md` | Slice 1 design completed; boundaries, lifecycle, idempotency, migration order documented | Use as contract for additive migrations and service tests |
| Isolated PostgreSQL test harness | Test foundation | `tests/harness/postgres_isolated.py`, `tests/test_harness_smoke.py` | `python -m unittest discover -s tests -p "test_*.py" -v` passed (4 tests) | Add schema contract tests in Slice 2 |
| Schema contract coverage (`player`, `item`, `escrow_transaction`) | Test foundation | `tests/test_schema_contracts.py` | `docker compose up -d db; python -m unittest tests.test_schema_contracts -v` passed (5 tests) against disposable DB | Start Slice 3 wallet/ledger additive migration + service tests |
| Wallet + ledger additive foundation | Recovery implementation | `dxemb/db/migrations/001_wallet_ledger_foundation.sql`, `dxemb/shared/wallet_ledger_service.py` | `docker compose up -d db; python -m unittest tests.test_wallet_ledger_service -v` passed (5 tests) | Start Slice 4 P2P listing/escrow foundation |
| P2P listing + escrow additive foundation | Recovery implementation | `dxemb/db/migrations/002_market_escrow_foundation.sql`, `dxemb/shared/market_escrow_service.py` | `docker compose up -d db; python -m unittest tests.test_market_escrow_service -v` passed (5 tests) | Move to Slice 5 moderation/community recovery planning |
| Moderation/community recovery plan | Design-only planning | `docs/MODERATION_COMMUNITY_RECOVERY_PLAN.md` | Slice 5 read-only inventory completed (archive modules, duplicate-generation evidence, test/dependency scan, integration sequencing) | Next sprint: moderation/tickets implementation slices |
| Moderation immutable audit foundation | Recovery implementation | `dxemb/db/migrations/003_moderation_audit_foundation.sql`, `dxemb/shared/moderation_audit_service.py` | `docker compose up -d db; python -m unittest tests.test_moderation_audit_service -v` passed (5 tests) | Slice B command adapters (warn/status/preview only) |
| Local moderation command adapter | Recovery implementation | `dxemb/bot/cogs/moderation_local.py`, `dxemb/bot/main.py` | `docker compose up -d db; python -m unittest tests.test_moderation_command_adapter -v` passed (3 tests) | Slice C ticket foundation |
| Local ticket lifecycle foundation | Recovery implementation | `dxemb/db/migrations/004_ticket_foundation.sql`, `dxemb/shared/ticket_service.py` | `docker compose up -d db; python -m unittest tests.test_ticket_service -v` passed (3 tests) | Slice D profile/onboarding persistence + dry-run |
| Profile/onboarding persistence + dry-run | Recovery implementation | `dxemb/db/migrations/005_profile_onboarding_foundation.sql`, `dxemb/shared/profile_onboarding_service.py` | `docker compose up -d db; python -m unittest tests.test_profile_onboarding_service -v` passed (4 tests) | Slice E reconciliation and final evidence summary |
| Wallet bot read-only integration | Recovery implementation | `dxemb/bot/cogs/wallet_local.py`, `dxemb/bot/main.py` | `docker compose up -d db; python -m unittest tests.test_wallet_bot_adapter -v` passed (3 tests) | Slice B wallet web read-only routes |
| Wallet web read-only integration | Recovery implementation | `dxemb/web/app.py` (`/wallet/*` read-only + preview + disabled adjust), `tests/test_wallet_web_routes.py` | `docker compose up -d db; python -m unittest tests.test_wallet_web_routes -v` passed (4 tests) | Slice C p2p bot local-safe workflows |
| P2P bot local-safe workflows | Recovery implementation | `dxemb/bot/cogs/market_local.py`, `dxemb/bot/main.py`, `tests/test_market_bot_adapter.py` | `docker compose up -d db; python -m unittest tests.test_market_bot_adapter -v` passed (3 tests) | Slice D p2p web read-only browse/detail/status timeline |
| P2P web read-only workflows | Recovery implementation | `dxemb/web/app.py` (`/market/*` browse/detail/preview/escrow status+timeline), `tests/test_market_web_routes.py` | `docker compose up -d db; python -m unittest tests.test_market_web_routes -v` passed (4 tests) | Slice E reconciliation + final sprint report |
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

### 2026-08-10 — Admin Operations + Evidence Workspace (Cross-Project Safe Slice)
- Added read-only admin operations workspace with explicit admin-role guardrail:
  - route: `GET /admin/operations` in `dxemb/web/app.py`
  - template: `dxemb/web/templates/admin_operations.html`
  - nav wiring: `dxemb/web/ui.py`
- Workspace provides cross-system visibility without mutation behavior:
  - moderation-action evidence table (`moderation_action`)
  - support-ticket evidence table (`support_ticket` + latest `support_ticket_event`)
  - scheduler evidence table (`trader_delivery_request` + attempts/alerts rollups)
  - environment-presence snapshot (key-only, no secret values rendered)
  - game/mission feature-flag snapshot (`game_feature_flag`, `mission_feature_flag`)
- Added/updated validation coverage:
  - new suite `tests/test_admin_operations_web_routes.py`
  - migration-contract alignment for wallet additive schema in web suites:
    - `tests/test_nitrado_delivery_web_routes.py`
    - `tests/test_games_tasks_missions_web_routes.py`
    - `tests/test_market_web_routes.py`
    - each now applies `011_wallet_ledger_run5_additive_upgrade.sql`
  - catalog sync DB URL resolution hardened in `dxemb/shared/catalog/service.py` to read env at call-time and prevent cross-suite stale-connection leakage
- Validation after changes:
  - `c:/tz420/clone/DayZTrader/.venv/Scripts/python.exe -m pytest tests/test_admin_operations_web_routes.py tests/test_nitrado_delivery_web_routes.py tests/test_wallet_web_routes.py tests/test_games_tasks_missions_web_routes.py tests/test_market_web_routes.py tests/test_auto_trader_web_routes.py -q` (pass, 30 tests)
  - `c:/tz420/clone/DayZTrader/.venv/Scripts/python.exe -m pytest tests/test_wallet_schema_contracts.py tests/test_wallet_ledger_service.py tests/test_wallet_web_routes.py tests/test_wallet_bot_adapter.py tests/test_auto_trader_wallet_bridge.py tests/test_admin_operations_web_routes.py tests/test_nitrado_delivery_web_routes.py tests/test_market_web_routes.py tests/test_games_tasks_missions_web_routes.py -q` (pass, 51 tests)
  - `git diff --check` clean (line-ending warnings only on existing docs files)
  - `git diff --stat`, `git status --short` captured
- Scope boundary maintained:
  - no migration-history rewrites
  - no destructive schema changes
  - no live provider/network/file-transport writes
  - no wallet/payment monetization expansion
  - no commit/push/reset/clean/stash actions

### 2026-08-10 — Wallet Operator Hardening + Investigation Ergonomics
- Preserved prior uncommitted Run 5 wallet work by running baseline checks before changes:
  - `git status --short`
  - `git diff --stat`
  - `git diff --check`
  - `.venv/Scripts/python.exe -m pytest tests/test_wallet_schema_contracts.py tests/test_wallet_ledger_service.py tests/test_wallet_web_routes.py tests/test_wallet_bot_adapter.py tests/test_auto_trader_wallet_bridge.py -q` (pass, 32 tests)
- Added additive wallet safety/ergonomics improvements:
  - bounded parsing fallback for numeric wallet query/form inputs in `dxemb/web/app.py` and `dxemb/web/wallet_admin.py`
  - explicit non-integer rejection for `/wallet/<discord_user_id>/preview` amount input
  - admin POST redirect filter-state preservation (`direction`, `status`, `entry_type`, `reference_query`, `created_after`, `created_before`)
  - actor identity consistency guard (`actor_id` must match `X-DXEMB-ACTOR-ID` when header is provided)
  - wallet pagination URL encoding for player/admin templates
  - reconciliation mismatch visual emphasis in wallet admin detail
  - reversal/refund lineage metadata fix in `dxemb/shared/wallet_ledger_service.py` (`original_reference_type` / `original_reference_id` mapping)
- Added regression coverage:
  - `tests/test_wallet_ledger_service.py`: reversal metadata lineage assertions
  - `tests/test_wallet_web_routes.py`: invalid numeric fallback, preview integer validation, filter-preserving redirects, and actor-header mismatch rejection
- Validation after changes:
  - `.venv/Scripts/python.exe -m pytest tests/test_wallet_ledger_service.py tests/test_wallet_web_routes.py -q` (pass, 29 tests)
  - `.venv/Scripts/python.exe -m pytest tests/test_wallet_schema_contracts.py tests/test_wallet_ledger_service.py tests/test_wallet_web_routes.py tests/test_wallet_bot_adapter.py tests/test_auto_trader_wallet_bridge.py -q` (pass, 37 tests)
  - `git diff --check` clean
- Scope boundary maintained:
  - no migration-history rewrites
  - no destructive schema changes
  - no business/payment/paywall/subscription features
  - no commit/push/reset/clean/stash actions

### 2026-08-08 — Fake-Provider Delivery Scheduler Foundation Sprint (Slices A-D)
- Slice A completed: additive scheduler schema migration `dxemb/db/migrations/007_nitrado_delivery_scheduler_foundation.sql` added:
  - `delivery_poll_run`
  - `restart_window_cache`
  - `trader_delivery_request`
  - `trader_scheduler_event` (immutable)
  - `trader_spawn_artifact` (immutable)
  - `trader_delivery_attempt` (immutable)
  - `trader_delivery_alert`
  - `trader_delivery_refund_link` (immutable)
- Slice A tests completed: `tests/test_nitrado_delivery_scheduler_schema.py` validated FK scope/idempotency/immutability/P2P-separation constraints.
- Slice B completed: pure decision engine added in `dxemb/shared/nitrado_delivery_decision_engine.py` with fake-clock timing coverage in `tests/test_nitrado_delivery_decision_engine.py`.
- Slice C completed: interfaces/fakes/service scaffolding added:
  - `dxemb/shared/nitrado_delivery_interfaces.py`
  - `dxemb/shared/nitrado_delivery_fakes.py`
  - `dxemb/shared/nitrado_delivery_scheduler_service.py`
  - tests: `tests/test_nitrado_delivery_scheduler_service.py`, `tests/test_nitrado_delivery_fake_boundaries.py`
- Slice D completed: read-only local operator visibility routes added in `dxemb/web/app.py`:
  - `GET /autotrader/scheduler/requests`
  - `GET /autotrader/scheduler/orders/<order_id>/status`
  - tests: `tests/test_nitrado_delivery_web_routes.py`
- Consolidated scheduler regression evidence:
  - `git diff --check`
  - `docker compose up -d db; python -m unittest tests.test_nitrado_delivery_scheduler_schema tests.test_nitrado_delivery_decision_engine tests.test_nitrado_delivery_scheduler_service tests.test_nitrado_delivery_fake_boundaries tests.test_nitrado_delivery_web_routes tests.test_auto_trader_web_routes -v`
  - `docker compose config`
  - `docker compose down`
- Scope compliance confirmed:
  - no `.env`/credential edits
  - no real network client usage (HTTP/FTP/SFTP)
  - no daemon/background scheduler
  - no XML/DayZ file writes/uploads/deletes
  - no restart actions
  - no Player Market + Escrow behavior/table changes

### 2026-08-08 — Nitrado Delivery Scheduler Sprint (Design-Only)
- Added `docs/NITRADO_DELIVERY_SCHEDULER_DESIGN.md` as implementation-ready design contract for future Auto-Trader delivery orchestration.
- Documented:
  - Auto-Trader-to-delivery boundary states and explicit P2P prohibitions
  - future additive scheduler data model (tables/retention/audit rules)
  - 5-minute status polling and 30-minute file-pull cadence model
  - restart-window caching, stale/unknown/conflict handling, and no-restart rule
  - write-window timing contract (about 10 minutes before confirmed restart)
  - failure/retry/alert policy and idempotent refund-link rules
  - DayZ console artifact constraints and checksum/atomic-write strategy (future)
  - security, redaction, manual hold/approve/cancel controls, and dry-run plan
  - test strategy with fake clock/provider/FTP adapters and integration boundaries
  - additive future implementation sequence with explicit approval gates
- Read-only reference candidates reviewed from archive clone paths only:
  - `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\bot\services\nitrado_client.py`
  - `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\bot\services\ftp_client.py`
  - `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\bot\services\xml_generator.py`
- Confirmed scope compliance:
  - no Nitrado/FTP/API calls
  - no scheduler process start
  - no XML/spawn file writes
  - no restart actions
  - no Docker/database/network commands in this sprint
  - no source-code changes outside approved docs files

### 2026-08-08 — Auto-Trader Order Foundation Sprint Slice A
- Added additive schema foundation `dxemb/db/migrations/006_auto_trader_order_foundation.sql` for:
  - admin-owned Auto-Trader products with item/kit/vehicle references, sellability, stock fields, and console-safe metadata
  - `trader_order` state machine with auditable lifecycle states (`draft`, `pending_payment`, `paid`, `queued_for_delivery`, `awaiting_restart_window`, `delivery_written`, `delivered`, `failed`, `refunded`, `cancelled`)
  - immutable `trader_order_event` audit log
- Added `dxemb/shared/auto_trader_order_service.py` and tests `tests/test_auto_trader_order_service.py` covering transitions, idempotent order creation, allow-list enforcement, and P2P table separation.
- Slice A validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_auto_trader_order_service -v` (pass, 5 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network in-use warning remained non-fatal)

### 2026-08-08 — Auto-Trader Order Foundation Sprint Slice B
- Added atomic wallet bridge `dxemb/shared/auto_trader_wallet_bridge.py` to create paid Auto-Trader orders and apply one wallet debit in a single transaction path using idempotent debit references.
- Added refund flow for failed/cancelled orders with idempotent refund behavior.
- Added tests `tests/test_auto_trader_wallet_bridge.py` covering duplicate-call no-double-debit guarantees, refund behavior, and P2P escrow non-interference.
- Slice B validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_auto_trader_wallet_bridge -v` (pass, 3 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network in-use warning remained non-fatal)

### 2026-08-08 — Auto-Trader Order Foundation Sprint Slice C
- Added local-safe bot preview surface `dxemb/bot/cogs/autotrader_local.py` with product browse, dry-run order preview, and read-only order history.
- Added local-safe web preview routes in `dxemb/web/app.py` under `/autotrader/*`:
  - `GET /autotrader/products`
  - `POST /autotrader/orders/preview`
  - `GET /autotrader/orders`
  - `GET /autotrader/orders/<order_id>`
  - `GET /autotrader/orders/<order_id>/history`
- Added tests `tests/test_auto_trader_bot_adapter.py` and `tests/test_auto_trader_web_routes.py` validating read-only/dry-run behavior, no Discord mutation APIs, no external delivery side-effect tokens, and namespace separation from P2P routes.
- Slice C validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_auto_trader_bot_adapter tests.test_auto_trader_web_routes -v` (pass, 7 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network in-use warning remained non-fatal)

### 2026-08-08 — Auto-Trader Order Foundation Sprint Slice D Reconciliation
- Ran consolidated Auto-Trader sprint regression set:
  - `docker compose up -d db; python -m unittest tests.test_auto_trader_order_service tests.test_auto_trader_wallet_bridge tests.test_auto_trader_bot_adapter tests.test_auto_trader_web_routes -v`
  - Result: 15 tests passed.
- Confirmed hard-boundary adherence for this sprint:
  - no Nitrado/FTP/XML/restart scheduler/server write behavior added
  - Player Market + Escrow services/routes/tables remained separate
  - no real Discord/Neon/.env/deployment operations
  - additive migration approach preserved

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

### 2026-08-08 — Slice 5: Moderation + Community Recovery Plan (Design-Only)
- Added `docs/MODERATION_COMMUNITY_RECOVERY_PLAN.md` with read-only inventory and safe integration design for moderation, staff logs, roles/channels, onboarding/profile, and tickets.
- Confirmed archive moderation duplication risk in `C:\DXEMB\discord_bot\src\cogs\moderation.py` (mixed legacy/new sections and setup patterns).
- Confirmed archive module/test/dependency evidence used for planning:
  - modules: `C:\DXEMB\discord_bot\src\cogs\moderation.py`, `C:\DXEMB\discord_bot\src\cogs\user.py`, `C:\DXEMB\core\services\moderation_service.py`, `C:\DXEMB\core\services\user_service.py`, `C:\DXEMB\core\services\audit_service.py`
  - tests: `C:\DXEMB\tests\test_user_cog.py`, `C:\DXEMB\tests\test_user_service.py`, `C:\DXEMB\tests\test_admin_service_integration.py`, `C:\DXEMB\tests\test_discord_bot.py`
  - dependencies: `C:\DXEMB\requirements.txt`, `C:\DXEMB\discord_bot\requirements.txt`
- Gap identified: no explicit archive ticket-automation module/test set was identified by filename/content scan.
- Slice 5 remained design-only; no moderation/community runtime code was restored and no Discord/server settings were changed.

### 2026-08-08 — Slice A: Moderation Data Contract + Immutable Action Audit
- Added additive migration `dxemb/db/migrations/003_moderation_audit_foundation.sql` for immutable moderation action audit rows with idempotent reference constraints.
- Added local service `dxemb/shared/moderation_audit_service.py` for warn recording, local status-query logging, non-mutating dry-run previews, and target status lookups.
- Added tests `tests/test_moderation_audit_service.py` for warn recording, idempotency, target status aggregation, dry-run non-mutation, and immutability enforcement.
- Slice A required validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_moderation_audit_service -v` (pass, 5 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Slice B: Moderation Command Adapters (Local Guardrails)
- Added `dxemb/bot/cogs/moderation_local.py` with local-only slash command adapters:
  - warn
  - local moderation-action status query
  - dry-run moderation preview
- Added `LocalModerationAdapter` unit-tested behavior and loaded the cog in `dxemb/bot/main.py`.
- Explicitly excluded: kick, ban, timeout, role changes, channel changes, webhook activity, message deletion, and any Discord mutation behavior.
- Explicitly excluded from this slice: marketplace moderation actions (`suspend listing`, `resolve dispute`).
- Slice B required validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_moderation_command_adapter -v` (pass, 3 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Slice C: Ticket Foundation (Local-Only)
- Added additive migration `dxemb/db/migrations/004_ticket_foundation.sql` for:
  - `support_ticket` lifecycle state model (`OPEN`, `ASSIGNED`, `CLOSED`)
  - `support_ticket_event` immutable audit history (`OPENED`, `ASSIGNED`, `CLOSED`, `REOPENED`)
- Added local-only service `dxemb/shared/ticket_service.py` with open/assign/close/reopen transitions.
- Added tests `tests/test_ticket_service.py` validating lifecycle transitions, invalid transition guardrails, and immutable ticket-event history.
- Slice C required validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_ticket_service -v` (pass, 3 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Slice D: Profile/Onboarding Persistence + Dry-Run Evaluator
- Added additive migration `dxemb/db/migrations/005_profile_onboarding_foundation.sql` for:
  - `player_profile` persistence
  - `onboarding_session` state machine persistence
  - `onboarding_event` transition audit history
- Added local-only service `dxemb/shared/profile_onboarding_service.py` for:
  - profile upsert/idempotency
  - onboarding state transitions
  - dry-run evaluator output only
- Added tests `tests/test_profile_onboarding_service.py` validating idempotent profile upsert, valid/invalid onboarding transitions, and dry-run non-mutation behavior.
- Slice D required validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_profile_onboarding_service -v` (pass, 4 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Slice E: Reconciliation + Evidence Consolidation
- Reconciled `docs/FEATURE_RECOVERY_LEDGER.md`, `docs/PROJECT_CONTINUITY.md`, and `docs/MODERATION_COMMUNITY_RECOVERY_PLAN.md` with Slice A-D implementation evidence.
- Confirmed strict scope adherence throughout Slices A-E:
  - no real Discord mutations (roles/channels/permissions/webhooks/messages)
  - no token/`.env`/secret edits
  - no Neon/Nitrado/production setting changes
  - no destructive Docker volume or database reset actions
- Consolidated tested moderation/community foundation coverage:
  - moderation immutable audit foundation
  - local moderation warn/status/preview adapters
  - local ticket lifecycle foundation
  - profile/onboarding persistence with dry-run evaluator only
- Recommended next autonomous sprint selected:
  - **Bot/web integration for wallet plus Player Market/Escrow foundations**

### 2026-08-08 — Wallet+P2P Integration Slice A: Wallet Bot Read-Only Surface
- Added local-safe wallet bot cog/adapter at `dxemb/bot/cogs/wallet_local.py` with:
  - balance view
  - transaction history view
  - dry-run credit/debit preview only
- Added isolated adapter tests at `tests/test_wallet_bot_adapter.py` including a contract check that disallows common Discord mutation API usage in this module.
- Slice A required validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_wallet_bot_adapter -v` (pass, 3 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Wallet+P2P Integration Slice B: Wallet Web Read-Only Surface
- Added local-safe wallet routes in `dxemb/web/app.py`:
  - `GET /wallet/<discord_user_id>` (balance)
  - `GET /wallet/<discord_user_id>/ledger` (history)
  - `POST /wallet/<discord_user_id>/preview` (dry-run only)
  - `POST /wallet/<discord_user_id>/adjust` (explicitly disabled, 403)
- Added isolated route tests in `tests/test_wallet_web_routes.py`.
- Slice B required validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_wallet_web_routes -v` (pass, 4 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Wallet+P2P Integration Slice C: P2P Bot Local-Safe Workflows
- Added local-safe P2P bot cog/adapter in `dxemb/bot/cogs/market_local.py` with:
  - dry-run listing preview
  - listing create (P2P physical mode only)
  - escrow hold
  - listing/escrow status reads
- Added isolated adapter tests at `tests/test_market_bot_adapter.py`.
- Fixed a real schema contract issue in tests by seeding the referenced `item.classname` fixture before listing creation.
- Slice C required validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_market_bot_adapter -v` (pass, 3 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Wallet+P2P Integration Slice D: P2P Web Read-Only Workflows
- Added local-safe market web routes in `dxemb/web/app.py`:
  - `GET /market/listings`
  - `GET /market/listings/<listing_id>`
  - `POST /market/listings/preview` (dry-run only)
  - `GET /market/escrow/<escrow_id>`
  - `GET /market/escrow/<escrow_id>/timeline`
- Added isolated route tests in `tests/test_market_web_routes.py`.
- Slice D required validation completed:
  - `git diff --check` (pass)
  - `docker compose up -d db; python -m unittest tests.test_market_web_routes -v` (pass, 4 tests)
  - `docker compose config` (pass)
  - `docker compose down` (completed; compose network removal reported in-use warning only)

### 2026-08-08 — Wallet+P2P Integration Slice E: Reconciliation + Final Sprint Report
- Consolidated Wallet+P2P integration test run passed:
  - `docker compose up -d db; python -m unittest tests.test_wallet_bot_adapter tests.test_wallet_web_routes tests.test_market_bot_adapter tests.test_market_web_routes -v`
  - Result: 14 tests passed.
- Final sprint slice commit chain:
  - `40a3e8a` — wallet-sliceA: add local wallet bot read-only surface
  - `ea5b60a` — wallet-sliceB: add local web wallet read-only routes
  - `e39bd3c` — market-sliceC: add local p2p bot workflows
  - `59ae5ce` — market-sliceD: add local web p2p read-only routes
- Boundary checks reaffirmed for this sprint:
  - Auto-Trader code path left untouched.
  - No P2P spawn/server-transfer behavior added.
  - No external Discord/Neon/Nitrado/.env/deployment operations performed.
  - Additive schema strategy preserved (no migration rewrites/destructive DB actions).
- Compose teardown note remains non-blocking in local env:
  - `docker compose down` reports `Network dayztrader_default Resource is still in use` warning; treated as non-fatal, consistent with prior runs.

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

### 2026-08-08 — Games + Tasks + Achievements Foundation Sprint (Slices A-D)
- Slice A completed: additive game economy foundation in `dxemb/db/migrations/008_game_economy_foundation.sql` and `dxemb/shared/game_economy_service.py` with deterministic coin-flip RNG audit, idempotent session replay, and feature-flag gated wallet settlement.
- Slice A tests completed: `tests/test_game_economy_service.py` covering determinism, wager validation, disable flags, live payout gate, idempotency, and wallet SQL boundary checks.
- Slice B completed: additive daily task + achievement foundation in `dxemb/db/migrations/009_daily_tasks_achievements_foundation.sql` and `dxemb/shared/task_achievement_service.py` with UTC cycle reset, progress tracking, unlock flow, and reward idempotency.
- Slice B tests completed: `tests/test_task_achievement_service.py` covering progress completion, duplicate reward prevention, midnight UTC split behavior, achievement idempotency, and ledger-only mutation checks.
- Slice C completed: additive mission/bounty foundation in `dxemb/db/migrations/010_mission_bounty_foundation.sql` and `dxemb/shared/mission_bounty_service.py` with local feature flags, admin-only create/activate/cancel rules, progress eligibility, claim idempotency, and expiry/cancel protections.
- Slice C tests completed: `tests/test_mission_bounty_service.py` covering creator/admin rules, claim idempotency, cancellation blocking, expiry blocking, feature-flag claim guards, and wallet SQL boundary checks.
- Slice D completed: local-safe preview and reconciliation surfaces added:
  - bot adapter/cog: `dxemb/bot/cogs/games_local.py`, loaded via `dxemb/bot/main.py`
  - web routes: `dxemb/web/app.py` (`/games/sessions`, `/games/coinflip/preview`, `/tasks/progress/<discord_user_id>`, `/achievements/unlocks/<discord_user_id>`, `/missions`, `/missions/progress/<discord_user_id>`)
  - route/adapter tests: `tests/test_games_tasks_missions_web_routes.py`, `tests/test_games_tasks_missions_bot_adapter.py`
- Consolidated Slice D validation completed:
  - `git diff --check`
  - `docker compose up -d db; python -m unittest tests.test_game_economy_service tests.test_task_achievement_service tests.test_mission_bounty_service tests.test_games_tasks_missions_bot_adapter tests.test_games_tasks_missions_web_routes -v`
  - `docker compose config`
  - `docker compose down`
  - Result: 24 tests passed.
- Scope compliance confirmed:
  - no `.env` or credential edits
  - no external provider/FTP/API calls
  - no direct wallet balance SQL writes
  - no Auto-Trader/P2P behavior coupling changes

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
- First future implementation slice requiring explicit owner approval: controlled live-provider adapter integration for test-server read operations and guarded transport preflight contracts, still with writes/restarts disabled unless separately approved.

---
End of authoritative continuity record.
