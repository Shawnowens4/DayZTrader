# DayZTrader / DXEMB — Project Continuity

> Authoritative AI-resume document. Read this file before planning, editing, testing, or proposing work.
> Code baseline anchor: `1f90a668` on branch `feature/local-finish-ui-recovery`.
> Last updated: 2026-08-13.

---

## Project Identity

| Field | Value |
|---|---|
| Project | D.X.E.M.B / DayZTrader → Zed420 (rename deferred) |
| Purpose | DayZ Xbox/PlayStation Discord bot, web dashboard, Auto-Trader, player marketplace/escrow, and Nitrado-aware console-server tools |
| Repository | `Shawnowens4/DayZTrader` |
| Active branch | `feature/local-finish-ui-recovery` |
| Rollback reference | `main-clean` @ `71fcee09` |
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

## Copilot Policy

User is **out of Copilot credits until August 31, 2026.**
- Do not invoke Copilot coding agents.
- Do not give broad Copilot prompts by default.
- Prefer direct evidence-based inspection, implementation, tests, and narrow patches.

---

## Verified Repository Baseline

### Git State
- Active branch: `feature/local-finish-ui-recovery`
- Code baseline anchor: `1f90a668` — `assets: audit DayZ images and console vehicle variants`
- Rollback reference: `main-clean` @ `71fcee09`
- Known branches:
  - `main` (default)
  - `main-clean` (PERM rollback reference)
  - `dayz-trader-full`
  - `feature/local-finish-ui-recovery` ← **active lane**

### Neon State
- `tz420-audit-suite` — confirmed active (944s active_time during reconciliation audit)
- `neon-amber-tree` — confirmed present, idle (0s active_time)
- **Do not assume which project maps to which branch or app until docker-compose.yml / .env.example DATABASE_URL evidence is reviewed.**
- Do not make any database change until config and schema evidence prove the relationship.

### Present Components
| Area | Active source | Status |
|---|---|---|
| Docker stack | `docker-compose.yml`, `Dockerfile.bot`, `Dockerfile.web` | Present; DATABASE_URL target unverified — next task |
| Discord bot | `dxembbot/` | Present |
| Flask web app | `dxembweb/` | Present |
| Shared services | `dxembshared/` | Present |
| Database init | `dxembdb/` | Present |
| Tests | `tests/` | Present; inventory pending |
| Docs | `docs/` | Present |
| oldbase.html | Committed on active branch | Canonical UX reference — do not paste over templates |

---

## Reconciliation Audit — 2026-08-13

### Baseline Chosen
- Branch: `feature/local-finish-ui-recovery`
- Commit: `1f90a668`
- Why: Active working lane, most recent commit (2026-08-13), contains oldbase.html as committed canonical UX reference artifact
- Rollback reference: `main-clean` @ `71fcee09`

### First Implementation Slice
- User-visible goal: Reconciliation audit complete — baseline confirmed, Neon projects identified, stream separation confirmed
- Files changed: `docs/PROJECT_CONTINUITY.md` only
- Explicitly not changed: templates, routes, schema, Docker, bot
- Validation: Branch map matches known branches; `tz420-audit-suite` confirmed active; `neon-amber-tree` confirmed present
- Result: Audit complete, no code changes made

### Next Exact Task
Inspect `docker-compose.yml` and `dxembweb/` app config on `feature/local-finish-ui-recovery` to confirm which Neon project (if any) is referenced in `DATABASE_URL` or equivalent env var. This determines which Neon project is the live target and whether schema evidence exists.

---

## Active Stream Separation

Keep these distinct unless an explicit task joins them:

1. **Oldbase UX rebuild** — primary active stream
2. **DXEMB → Zed420 rename** — later, separate migration
3. **Vehicle XML/compatibility review** — data-validation stream, not UI proof
4. **Neon Audit Suite work** — separate until config/schema proves a connection

---

## Progress Rules

- Progress is evidence-based, never planning-based.
- A coded but untested feature cannot exceed 50%.
- Lifecycle: Design → Implemented → Tests written → Tests passing → Headless/Discord tests passing → Audit pass → Real-user sign-off.
- Update progress only after recorded proof.

### Current Honest Status
```text
Repository discovery and baseline: ██████████ 100%
Documentation consolidation:       ██████████ 100%
Docker/runtime re-verification:    ████████░░  78%
Bot/Discord verification:          ████████░░  79%
Web/admin verification:            ████████░░  81%
Database/Neon verification:        ███████░░░  65%
Auto-Trader audit:                 ██████░░░░  58%
Player Market + Escrow audit:      ████████░░  78%
Automated tests audit:             ██████████  97%
Total verified project state:      █████████░  92%
```
