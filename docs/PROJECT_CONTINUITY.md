# DayZTrader / DXEMB — Project Continuity

> Authoritative AI-resume document. Read this file before planning, editing, testing, or proposing work.
> Last verified repository baseline: `f9425cd` on branch `PERM`.
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
- Baseline commit: `f9425cd` — `resolve: keep local vehicle_thumbnail_resolver.final.json`
- Working tree: clean at last verification on 2026-08-08.
- Recent verified history:
  - `f9425cd` resolve: preserve final vehicle thumbnail resolver data
  - `892b2d7` fix Discord slash-command registration behavior
  - `fc2860b` wire app commands into `bot.tree`
  - `598dab4` re-apply slash-sync infrastructure
  - `2b7e9a8` add first `/health` slash-command proof path

### Present Components
| Area | Active source | Status |
|---|---|---|
| Docker stack | `docker-compose.yml`, `Dockerfile.bot`, `Dockerfile.web` | Present; must be re-tested before claiming current runtime health |
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
Documentation consolidation:     ██████░░░░  60%
Docker/runtime re-verification:  ███░░░░░░░  30%
Bot/Discord verification:       ████░░░░░░  40%
Web/admin verification:         ████░░░░░░  40%
Database/Neon verification:     ██░░░░░░░░  20%
Auto-Trader audit:              ███░░░░░░░  30%
Player Market + Escrow audit:   ██░░░░░░░░  20%
Automated tests audit:          ██░░░░░░░░  20%
Total verified project state:   ████░░░░░░  35%
```

---

## Feature Ledger

| Feature | Classification | Active source | Verification | Next action |
|---|---|---|---|---|
| Docker local stack | Foundation | Docker root files | Historical A0 evidence only; re-check required | Run stack and capture health output |
| Discord bot startup | Foundation | `dxemb/bot/main.py` | Source present | Audit startup configuration and run |
| Slash-command synchronization | Bot infrastructure | `health_slash.py`, `main.py` | Recent commits present | Verify sync and `/health` in test guild |
| Catalog data | Shared domain | `dxemb/shared/catalog/` | Source/data present | Audit console filtering and source integrity |
| Vehicle catalog/resolver | Shared domain | vehicle resolver/builder services | Source/data present | Audit allowed-list connection |
| Admin catalog UI | Auto-Trader admin surface | `web/catalog_admin.py` | Source present | Inspect routes and persistence |
| Admin vehicle UI | Auto-Trader admin surface | `web/vehicle_admin.py` | Source present | Inspect routes and persistence |
| Auto-Trader orders/spawn queue | Server store | To be verified | Not yet verified | Audit models, states, queue, and Nitrado boundary |
| Player Market + Escrow | P2P system | To be verified | Not yet verified | Locate active code/schema or mark unimplemented |
| Neon database path | Infrastructure | `.env.example`, shared/db, Docker config | Not yet verified | Audit configuration safely |
| Nitrado schedule/spawn integration | Infrastructure | To be verified | Not yet verified | Locate code, confirm no forced restart behavior |

---

## Current Work Item

### Goal
Establish a complete, evidence-based application audit and create the authoritative continuation baseline.

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

---
End of authoritative continuity record.
