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

## 2026-08-09 Completed Milestone — Run 3 types.xml import foundation

- Completed and validated: local-first `types.xml` importer foundation with secure malformed-XML rejection, dry-run/apply reporting, idempotent `classname` upsert, curated storefront field protection (`buy_price`, `sell_price`, `is_enabled`, `thumbnail_url`), review-required defaults for newly imported items, and source provenance (`source_sha256`, evidence locator) persisted in item notes; validated by `tests.test_types_xml_import_foundation`, `tests.test_schema_contracts`, in-container importer dry-run/apply/idempotency checks, and HTTP 200 route checks for `/catalog`, `/vehicles`, and `/vehicles/Hatchback02`.

---

## 2026-08-09 Full Product + Design Audit Build Plan

This section is the current repository-wide audit and build-plan checkpoint before the next implementation run.

Scope rules for this audit:
- read-only inventory first
- no behavior change implied by this plan
- no live-service enablement implied by this plan
- no vehicle compatibility approval implied by this plan

### A. Design-source inventory

#### Exact in-repo screenshot/reference image paths

Confirmed in-repo image assets:
- `dxemb/web/static/catalog_items/chernarussportshirt.webp`
- `dxemb/web/static/catalog_items/tourist_map.webp`
- `dxemb/web/static/catalog_items/vehicles.webp`
- `dxemb/web/static/ui/thumbnail-fallback.svg`

Confirmed in-repo design/theme sources:
- `dxemb/web/static/css/dayz_admin.css`
- `dxemb/web/static/js/ui_shell.js`
- `dxemb/web/static/ui/asset_manifest.json`
- `dxemb/web/templates/base.html`
- `dxemb/web/templates/dashboard.html`
- `dxemb/web/templates/catalog_list.html`
- `dxemb/web/templates/catalog_detail.html`
- `dxemb/web/templates/vehicle_list.html`
- `dxemb/web/templates/vehicle_builder.html`
- `docs/LOCAL_FINISH_RECOVERY_PLAN.md`

Confirmed archive-only design references documented in repo but not stored in repo:
- `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\web\static\css\admin.css`
- `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\web\static\js\map.js`
- `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\web\static\js\vehicle_card_builder.js`
- `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\web\static\js\trunk_card_builder.js`

Fonts/icons/theme variables confirmed in repo:
- font stack in `dxemb/web/static/css/dayz_admin.css`: `Segoe UI`, `Tahoma`, `Geneva`, `Verdana`, sans-serif
- color variables in `dxemb/web/static/css/dayz_admin.css`:
  - `--primary: #00d4ff`
  - `--primary-dark: #00a8cc`
  - `--bg-main: #0d1524`
  - `--bg-panel: #152035`
  - `--bg-panel-alt: #0f1a2d`
  - `--text: #f7fbff`
  - `--text-muted: #9eb1c8`
  - `--ok: #44ff44`
  - `--warn: #ffaa00`
  - `--error: #ff6b6b`

What is confirmed about the desired green/dark style:
- owner direction in current planning session: cohesive black/charcoal base with toxic/electric-green emphasis
- current repo already supports dark backgrounds and strong status colors
- current repo does not yet implement a green-first visual system or screenshot-matched shell

What is missing or needs owner confirmation:
- no approved screenshot/reference image is stored in this repository
- no in-repo font, icon set, spacing system, or component spec establishes the target green/dark direction
- no confirmed mobile layout reference image is stored in repo
- no explicit owner-approved nav hierarchy mockup is stored in repo

UI comparison: current vs intended direction

Current repo UI evidence:
- dark navy / cyan shell from `dxemb/web/static/css/dayz_admin.css`
- utilitarian admin framing from `dxemb/web/templates/base.html`
- dashboard/catalog/vehicle pages are functional and readable but still admin-foundation oriented
- visual language is closer to blue/cyan control panel than black/charcoal toxic-green product shell

Target direction from owner prompt:
- black/charcoal primary surfaces
- toxic/electric-green highlight color
- strong readable cards and navigation
- mobile-friendly presentation
- fewer generic placeholder/admin-foundation cues

Gap summary:
- current UI is usable and locally tested
- current UI is not yet aligned to the requested screenshot-inspired green/dark product direction
- design implementation should begin with a shell/theme foundation rather than scattered page-level restyling

### B. Feature matrix

| Area | Existing code/data/docs paths | Actual current implementation status | User-visible status | Backend/data status | Test coverage | Missing dependencies or blockers | Lowest-risk next implementation slice |
|---|---|---|---|---|---|---|---|
| Web shell | `dxemb/web/app.py`, `dxemb/web/templates/base.html`, `dxemb/web/templates/dashboard.html`, `dxemb/web/static/css/dayz_admin.css`, `tests/test_web_visual_foundation_slice_a.py` | Implemented and tested | `/`, `/catalog`, `/vehicles` load locally; shell is functional but visually off-target | Flask shell and blueprint wiring are active | Slice A route tests pass | visual direction mismatch with owner target; no screenshot in repo | green UI design-system foundation and shell restyle without route changes |
| Auth / identity / account linking | `dxemb/shared/profile_onboarding_service.py`, `dxemb/db/migrations/005_profile_onboarding_foundation.sql`, `.env.example`, `docs/MASTER_HANDOFF.md` | Partial / placeholder | no login, no account page, no Discord web sign-in | onboarding/profile persistence exists; no OAuth callback or session auth | `tests/test_profile_onboarding_service.py` passes | missing Discord OAuth flow, session binding, role model, protected web routes | identity/roles/account foundation using existing onboarding schema |
| Discord integration | `dxemb/bot/main.py`, `dxemb/bot/cogs/*.py`, `docs/PROJECT_CONTINUITY.md` | Implemented but unverified / partial | local-safe/admin-oriented commands exist; not owner-verified in live guild | cog loading, slash sync options, admin permission decorators present | bot adapter tests pass across wallet, market, autotrader, games, moderation | no linked web identity, no broad end-user command pass, no confirmed live guild validation | Discord command foundation synchronized to identity and wallet state |
| Wallet / bank / ledger | `dxemb/shared/wallet_ledger_service.py`, `dxemb/db/migrations/001_wallet_ledger_foundation.sql`, `dxemb/web/app.py`, `dxemb/bot/cogs/wallet_local.py`, `docs/WALLET_LEDGER_MARKET_ESCROW_DESIGN.md` | Implemented and tested for wallet ledger core; bank absent | read-only wallet/balance/ledger visibility only; mutation disabled | immutable ledger path and balance safety exist; no bank model seen | `tests/test_wallet_ledger_service.py`, `tests/test_wallet_bot_adapter.py`, `tests/test_wallet_web_routes.py` pass | no bank account subsystem, no authenticated user self-service mutation flows, admin UI absent | wallet/bank/ledger core completion with explicit bank design or documented omission |
| Games | `dxemb/shared/game_economy_service.py`, `dxemb/db/migrations/008_game_economy_foundation.sql`, `dxemb/bot/cogs/games_local.py`, `dxemb/web/app.py` | Implemented but unverified / partial | preview/history surfaces exist; no owner-verified end-user gameplay release | deterministic coin-flip and audited sessions exist; settlement is feature-guarded | `tests/test_game_economy_service.py`, `tests/test_games_tasks_missions_web_routes.py`, `tests/test_games_tasks_missions_bot_adapter.py` pass | no authenticated player-facing flow, no UI productization, settlement still safety-gated | game entry and reward flow using current ledger with safe user-visible history |
| Achievements / progression | `dxemb/shared/task_achievement_service.py`, `dxemb/db/migrations/009_daily_tasks_achievements_foundation.sql`, `docs/MASTER_HANDOFF.md` | Implemented but unverified / partial | limited read-only progress endpoints; no polished progression surface | daily tasks and achievement rewards modeled; no XP/levels model found | `tests/test_task_achievement_service.py`, `tests/test_games_tasks_missions_web_routes.py` pass | no player-facing progression shell, no explicit XP/level subsystem, no Discord user journey | achievements/progression presentation tied to existing task and reward models |
| Clans | none found in repo code, migrations, tests, or docs | Absent | no user-visible clan features | no schema or service layer | none | feature is not present in repository evidence and needs fresh design | clan foundation design and schema proposal only after identity and wallet controls are stable |
| Catalog | `dxemb/shared/catalog/service.py`, `dxemb/web/catalog_admin.py`, `dxemb/web/templates/catalog_*.html`, `dxemb/shared/catalog/data/*`, `docs/DAYZ_IMAGE_AND_VEHICLE_VARIANT_AUDIT.md` | Implemented and tested | browse/detail/filter works locally | catalog item model and resolver-backed thumbnail flow are active | `tests/test_catalog_thumbnail_workflow_slice_b.py` passes | visual polish incomplete; image coverage incomplete; no auth guard | visual/data completion after shell redesign |
| Vehicles | `dxemb/shared/catalog/vehicle_builder_service.py`, `dxemb/shared/catalog/data/vehicle_*`, `dxemb/web/vehicle_admin.py`, `docs/CONSOLE_VEHICLE_*.md` | Implemented and tested for builder shell; blocked for compatibility release | vehicle list/builder render locally with fallback visuals | fail-closed compatibility review process exists; approvals remain blocked | `tests/test_console_vehicle_audit_artifacts.py`, Slice A route tests cover pages indirectly | owner evidence still required for compatibility promotion | continue fail-closed review data process and visual completion only |
| Admin / moderation / audit | `dxemb/shared/moderation_audit_service.py`, `dxemb/shared/ticket_service.py`, `dxemb/web/app.py`, `docs/MODERATION_COMMUNITY_RECOVERY_PLAN.md` | Implemented but unverified / partial | admin-safe read-only or dry-run surfaces exist; no cohesive admin workspace | immutable moderation/ticket foundations exist; action scope remains narrow | `tests/test_moderation_audit_service.py`, `tests/test_moderation_command_adapter.py`, `tests/test_ticket_service.py` pass | no protected admin workspace, no comprehensive review console, limited moderation actions | admin/audit workspace completion after identity/role protection |
| Tests / local quality | `tests/`, `tests/harness/postgres_isolated.py`, `docs/PROJECT_PROGRESS.md`, `docs/TODO_ROADMAP.md` | Implemented and tested / partial | no public-facing test UI; local confidence is real but fragmented | isolated PostgreSQL harness and many targeted suites exist | broad service/route coverage present; no single release acceptance script | no unified acceptance checklist, some live behaviors intentionally deferred | full local acceptance checklist and grouped validation command set |

### C. Data and security audit

#### Existing user/account/role models

Confirmed models/tables:
- `player` in `dxemb/db/init.sql`
- `player_profile`, `onboarding_session`, `onboarding_event` in `dxemb/db/migrations/005_profile_onboarding_foundation.sql`

Confirmed user/account state:
- `player.discord_id` is the authoritative user identifier
- `ProfileOnboardingService` manages profile persistence and onboarding states
- no explicit role table, permission table, clan membership table, or web session identity table found

#### Existing wallet/transaction/balance models and safety

Confirmed wallet/ledger foundations:
- `dxemb/db/migrations/001_wallet_ledger_foundation.sql`
- `dxemb/shared/wallet_ledger_service.py`

Safety characteristics confirmed by code/tests:
- explicit credit/debit/admin_adjust service methods
- idempotent reference handling
- immutable ledger intent
- insufficient funds guard
- disabled mutation endpoint on web path

Current limitation:
- wallet foundation is safe for ledger-like use
- bank balance subsystem is not confirmed in repository evidence
- no evidence of full double-entry accounting model; current pattern is mutable balance + immutable ledger audit

#### Existing Discord token/config handling and command architecture

Confirmed token/config paths:
- `.env.example`
- `docker-compose.yml`
- `dxemb/bot/main.py`

Confirmed architecture:
- prefix and slash bot in `dxemb/bot/main.py`
- cogs loaded from `dxemb/bot/cogs/`
- slash sync mode controlled by `SLASH_SYNC`
- guild targeting controlled by `GUILD_IDS`
- no-op mode when token is blank

#### Existing authorization/permission checks

Confirmed checks:
- slash commands use `@app_commands.default_permissions(administrator=True)` in several cogs
- prefix health command uses `@commands.has_permissions(administrator=True)`
- `MissionBountyService` contains admin actor checks

Missing/weak areas:
- no web auth gate on `/`, `/catalog`, `/vehicles`, or other admin/read-only routes
- no OAuth login/callback route
- no durable role/permission model shared between web and Discord layers

#### Existing migrations and test fixtures

Core migrations found:
- `dxemb/db/init.sql`
- `dxemb/db/migrations/001_wallet_ledger_foundation.sql`
- `dxemb/db/migrations/002_market_escrow_foundation.sql`
- `dxemb/db/migrations/003_moderation_audit_foundation.sql`
- `dxemb/db/migrations/004_ticket_foundation.sql`
- `dxemb/db/migrations/005_profile_onboarding_foundation.sql`
- `dxemb/db/migrations/006_auto_trader_order_foundation.sql`
- `dxemb/db/migrations/007_nitrado_delivery_scheduler_foundation.sql`
- `dxemb/db/migrations/008_game_economy_foundation.sql`
- `dxemb/db/migrations/009_daily_tasks_achievements_foundation.sql`
- `dxemb/db/migrations/010_mission_bounty_foundation.sql`

Test harness/fixtures:
- `tests/harness/postgres_isolated.py`
- route and service suites across wallet, market, autotrader, games, moderation, tickets, profile, scheduler, catalog, vehicles

#### Risks before enabling wallet, games, transfers, clans, or admin actions

- web routes are currently unguarded; identity/role protection must precede real admin enablement
- no bank subsystem is evidenced, so bank-related product claims should stay blocked or documented as absent
- wallet mutation is intentionally disabled in web routes; re-enabling without auth and audit UX would be unsafe
- game settlement exists in service logic but remains safety-gated and is not yet a fully verified user journey
- clan functionality is absent and should not be implied by current docs or UI
- moderation/ticket foundations exist, but admin actions are not yet exposed through a coherent protected workspace
- fail-closed vehicle compatibility must remain blocked until explicit evidence and owner approval promote rows

### D. Major-commit plan

| Order | Name | Goal | Exact likely files/systems | User-visible outcome | Safety boundaries | Required tests/validation | Exit criteria | Dependencies | Estimated completeness contribution |
|---|---|---|---|---|---|---|---|---|---:|
| 1 | Green UI shell foundation | Move from cyan/navy admin-foundation shell toward the approved black/charcoal + toxic-green product shell | `dxemb/web/templates/base.html`, `dxemb/web/templates/dashboard.html`, `dxemb/web/static/css/dayz_admin.css`, `dxemb/web/static/js/ui_shell.js`, `dxemb/web/ui.py`, UI tests/docs | immediately visible brand/theme improvement across primary pages | no route changes, no schema changes, no behavior changes | route tests, manual mobile page check, `git diff --check` | shell, nav, cards, status colors, spacing, and mobile baseline aligned to target direction | none | 8% |
| 2 | Identity and role foundation | Add safe local authentication, account/profile surface, and Discord-link groundwork | `dxemb/web/app.py`, auth/session helper module(s), `dxemb/shared/profile_onboarding_service.py`, related templates/docs/tests | users/admins can identify who they are and protected pages stop being anonymous | preserve existing routes where possible; additive auth only; no live OAuth secrets committed | auth route tests, profile tests, guarded route tests, `git diff --check` | local sign-in/session guard and protected admin surfaces work safely | 1 | 10% |
| 3 | Wallet/bank/ledger completion | Finish safe transaction controls and decide/document bank support | wallet service/routes/templates, possible additive migration only if bank is truly required by repo evidence, docs/tests | authenticated users can view wallet and safe transaction history with admin-safe controls | no real-money behavior, preserve ledger immutability, additive-only data changes | wallet service/web tests, schema validation, route tests | wallet core is safe, user-visible, and auditable; bank is either implemented safely or explicitly marked absent/deferred | 2 | 10% |
| 4 | Discord identity + wallet foundation | Synchronize Discord command surfaces with the same identity and wallet state used by web | `dxemb/bot/main.py`, `dxemb/bot/cogs/wallet_local.py`, onboarding/profile hooks, command tests/docs | basic Discord identity-aware wallet/account commands become coherent with web state | no live service broadening beyond current bot boundaries | bot adapter tests, identity consistency tests, `git diff --check` | Discord and web identity/wallet paths are consistent and safe | 2, 3 | 8% |
| 5 | Games and rewards integration | Promote one safe game flow into a verified end-user journey tied to ledger records | `dxemb/shared/game_economy_service.py`, `dxemb/bot/cogs/games_local.py`, related web routes/templates/tests | a user can use at least one game flow and see recorded outcome/history | settlement remains feature-controlled; no opportunistic game expansion | game service tests, bot/web route tests, ledger linkage checks | one full game loop is safe, visible, and auditable | 3, 4 | 8% |
| 6 | Achievements and progression integration | Expose tasks/achievements/progression as a real user-facing journey | `dxemb/shared/task_achievement_service.py`, progression templates/routes, bot adapters, docs/tests | user can see progress and achievement rewards tied to existing systems | do not invent XP/levels if not modeled; use existing data first | service tests, route tests, bot tests, manual walkthrough | achievements/progression visible and coherent using current models | 3, 5 | 7% |
| 7 | Clan foundation | Add minimal clan membership/rank system only if it can be safely introduced additively | new additive clan schema/service/routes/bot adapters/docs/tests | user can create/join/leave and view clan membership/rank state | additive migrations only, no shared economy until separately justified | schema tests, service tests, route/bot tests, `git diff --check` | clan membership/rank state exists safely without destabilizing other systems | 2, 3 | 9% |
| 8 | Catalog and vehicle visual/data completion | Finish the main DayZ browsing experience while preserving fail-closed compatibility | catalog/vehicle templates, CSS, image audit docs, compatibility review JSON/docs, resolver/override docs/tests | catalog and vehicle surfaces feel complete and consistent | no guessed compatibility approvals, no hidden missing-image states | catalog/vehicle tests, audit tests, JSON validation, manual visual review | honest, polished catalog/vehicle UX with compatibility still fail-closed where needed | 1, 4 | 9% |
| 9 | Admin/audit/review workspace | Consolidate admin visibility for moderation, transactions, review queues, and safe controls | `dxemb/web/app.py`, admin templates, moderation/ticket/audit services, docs/tests | admin can review transactions/actions and blocked queues from one protected workspace | preserve read-only/dry-run defaults until explicitly verified | moderation/ticket/wallet/market/admin route tests, `git diff --check` | protected admin workspace is usable and auditable | 2, 3, 4, 8 | 10% |
| 10 | Local acceptance and release candidate | Create the polished, reproducible local release candidate | docs, tests, acceptance checklist, startup/rollback/changelog surfaces | owner can run and review a cohesive local release candidate | no live deployment actions without explicit owner approval | full targeted suite, startup checks, acceptance checklist, `git diff --check` | reproducible local candidate with clearly disabled incomplete systems | 1-9 | 6% |

### E. 75-percent readiness definition

The product is "about 75% complete" only when these user journeys are true in the local application and tested at the appropriate layer:

- a user can sign in or link Discord through a real local identity flow
- a user can view wallet and bank state, or bank is explicitly documented as out-of-scope while wallet + ledger are fully usable and auditable
- a user can review safe transaction history with immutable audit visibility
- a user can use at least the basic intended Discord commands tied to real application state
- a user can complete at least one integrated game/reward flow and see the recorded result
- a user can view achievements/progression from real stored data
- a user can create or join a clan and see membership/rank state, or clans are explicitly marked not part of the 75% target if owner scope changes
- a user can browse the catalog and vehicle builder with honest data and fallback states
- an admin can safely review transactions, moderation/ticket actions, and blocked review queues
- the app starts locally through a documented command set and key paths are tested
- known incomplete systems are clearly disabled or blocked, not fake, silently approved, or broken

If these journeys are not true, the product is not yet at 75% readiness regardless of line count or number of migrations.

### F. Immediate recommendation

Recommended next major implementation run:

**Green UI design-system foundation and app shell**

Why this is the best next step:
- highest visible product value with the lowest runtime risk
- no need to alter schemas, routes, or compatibility approvals
- directly addresses the confirmed mismatch between the current cyan/navy admin shell and the requested green/dark product direction
- improves the shell that every later identity, wallet, games, clan, catalog, vehicle, and admin surface will reuse

Visual acceptance gate:
- do not broaden past the shell/theme and vehicle-builder component language until `/`, `/catalog`, `/vehicles`, and the modal/card states match the approved reference direction
- screenshots may guide surface styling, but they do not unlock backend claims, compatibility approvals, or export behavior

---

## Local Screenshot Reference Intake — Not Production Evidence

This folder is local-only design reference material. It is not source code, not proof of functionality, and not a basis for backend claims.

### A. Inventory

All screenshots in `local_console_reference/ScreeniestoUSE` are `.png` files at approximately `4096×2160`.

| File | Ext | Approx. dims | Neutral description | Privacy / secrets flag |
|---|---|---|---|---|
| `Screenshot (75).png` | `.png` | `4096×2160` | Dark vehicle-builder cargo picker with an allowed-item grid and compact card stack. | No secret material observed. |
| `Screenshot (77).png` | `.png` | `4096×2160` | Vehicle part color override matrix for hood and trunk variants. | No secret material observed. |
| `Screenshot (78).png` | `.png` | `4096×2160` | Truck part overrides plus cargo preset controls and item cards. | No secret material observed. |
| `Screenshot (79).png` | `.png` | `4096×2160` | Dense cargo-search and allowed-item view with part selection and search results. | No secret material observed. |
| `Screenshot (81).png` | `.png` | `4096×2160` | Cargo-item search/results view with vehicle-builder controls and preset buttons. | No secret material observed. |
| `Screenshot (83).png` | `.png` | `4096×2160` | Builder export page with top navigation tabs and a blocked generate/export action. | No secret material observed. |
| `Screenshot (84).png` | `.png` | `4096×2160` | Truck part-color override and cargo preset page with selected orange variant. | No secret material observed. |
| `Screenshot (88).png` | `.png` | `4096×2160` | Vehicle selection modal for M3S Covered with color variants and a loot-configuration CTA. | No secret material observed. |
| `Screenshot (91).png` | `.png` | `4096×2160` | Scrollbox-resize preview showing parts list, cargo picker, and allowed-item grid behavior. | No secret material observed. |
| `Screenshot (105).png` | `.png` | `4096×2160` | Near-duplicate of the scrollbox-resize preview; same dense cargo-picker experiment framing. | No secret material observed. |

No screenshot in this folder showed confirmed secrets, tokens, Discord IDs, IPs, live server credentials, private messages, or real account/balance data.

### B. Screenshot grouping

Strong visual-direction references:
- `Screenshot (83).png`
- `Screenshot (84).png`
- `Screenshot (88).png`
- `Screenshot (91).png`
- `Screenshot (105).png`

Useful layout/component references:
- `Screenshot (75).png`
- `Screenshot (77).png`
- `Screenshot (78).png`
- `Screenshot (79).png`
- `Screenshot (81).png`

Feature-intent references that need backend confirmation:
- `Screenshot (79).png`
- `Screenshot (81).png`
- `Screenshot (83).png`
- `Screenshot (84).png`
- `Screenshot (88).png`
- `Screenshot (91).png`
- `Screenshot (105).png`

Obsolete, unclear, or conflicting references:
- `Screenshot (105).png` is a near-duplicate of `Screenshot (91).png` and should not be treated as a separate product direction.
- `Screenshot (75).png` through `Screenshot (81).png` are iterative builder experiments; they are useful for component patterns, but not all of their control labels or density choices should be carried forward unchanged.

Unsafe or private references that must stay local-only:
- none confirmed as secrets or credentials
- the screenshots do show local file paths, browser chrome, and experimental filenames, so they must remain local reference only and must not be republished verbatim

### C. Design extraction

Implementation-ready visual specification from the recurring patterns:

- Palette: near-black and charcoal surfaces first, with a single toxic/electric-green primary accent.
- Secondary accents: orange/amber for alternate variants and warning states; blue only for informational or alternate selection hints when needed; red reserved for destructive or blocked states.
- Cards and panels: dark surfaces, 1px muted borders, 10-12px radius, compact internal padding, and a bright green outline/glow only for selected or active states.
- Buttons: solid green primary actions, dark secondary actions, and clearly labeled blocked/disabled actions in gray with no ambiguity about whether they work.
- Navigation: sticky top shell with compact pill-style navigation and inline back links on detail pages; keep the nav lightweight rather than turning it into a heavy left sidebar.
- Typography: bold but compact headings, muted helper text, monospace only for classnames/IDs/technical values, and no oversized marketing treatment.
- Spacing: use a tight 8px-based rhythm with 12-16px card gutters and 16-24px section spacing; avoid dead whitespace that makes dense admin tools feel empty.
- Borders/shadows/glow: subtle borders by default, stronger green glow only on selected tiles, and no ambient neon haze across entire pages.
- Desktop/mobile behavior: multi-column card grids on desktop, single-column or stacked cards on mobile, with tables and picker lists collapsing gracefully rather than overflowing unpredictably.
- Empty/loading/error/blocked states: empty states should be honest and calm, loading should be muted and lightweight, errors should be red and explicit, and blocked states should look intentionally disabled rather than broken.
- Accessibility: strong contrast, visible focus rings, status text that does not rely on color alone, and touch targets large enough for mobile use.

### D. Product-intent extraction

| Concept | Screenshot evidence | Actual repository evidence | Current status | Safe next step | Dependencies and risk |
|---|---|---|---|---|---|
| Dashboard and navigation | Sticky top shell, tab-like nav, and card sections in `Screenshot (83).png`, `Screenshot (84).png`, `Screenshot (88).png`, `Screenshot (91).png`, `Screenshot (105).png` | `dxemb/web/templates/base.html`, `dxemb/web/templates/dashboard.html`, `dxemb/web/static/css/dayz_admin.css`, `dxemb/web/app.py` | `implemented_and_tested` | Refresh the shell tokens and shared nav styling first. | Low risk; the shell already exists and is locally tested. |
| User profiles / authentication | No dedicated auth screen observed | `dxemb/shared/profile_onboarding_service.py`, `dxemb/db/migrations/005_profile_onboarding_foundation.sql` | `partial_or_placeholder` | Define the intended local auth/session surface before implementation. | Medium-high risk; identity is not yet surfaced as a real user journey. |
| Discord linking and commands | No direct Discord-linking screen observed | `dxemb/bot/main.py`, `dxemb/bot/cogs/*.py`, slash sync helpers and tests | `implemented_unverified` | Verify command flows against the same identity model as the web app. | Medium risk; bot paths exist, but broad live-user validation is still missing. |
| Wallet / banking / transfers / transactions | No wallet/bank screen in the screenshot set | `dxemb/shared/wallet_ledger_service.py`, `dxemb/web/app.py` read-only wallet routes, wallet tests | `partial_or_placeholder` | Keep the local-safe read-only ledger surface and document bank scope explicitly. | High risk if expanded without auth and audit UX. |
| Games and rewards | No game screen observed | `dxemb/shared/game_economy_service.py`, `dxemb/db/migrations/008_game_economy_foundation.sql`, tests and bot adapters | `implemented_unverified` | Expose one safe history/result flow before adding more game UI. | Medium risk; settlement and reward paths are safety-gated. |
| Achievements / progression / tasks | No progression screen observed | `dxemb/shared/task_achievement_service.py`, `dxemb/db/migrations/009_daily_tasks_achievements_foundation.sql`, tests | `implemented_unverified` | Surface existing task/progression data before inventing new ranks or XP. | Medium risk; progress semantics are not yet fully productized. |
| Clans / memberships / ranks | No clan UI or concepts observed | No clan schema or service evidence found | `absent` | Leave this out of the first visual commit and design it only after identity is settled. | High risk; there is no repository proof yet. |
| Catalog browsing | Catalog/list/detail browsing is reflected indirectly by the shared local admin shell, but not emphasized in these screenshots | `dxemb/web/catalog_admin.py`, `dxemb/web/templates/catalog_*.html`, catalog service/tests | `implemented_and_tested` | Keep catalog styling aligned with the new shell while preserving route behavior. | Low-medium risk; already present and tested, but still visually under the old theme. |
| Vehicle builder and export/configuration | The dominant screenshot theme: color matrices, cargo pickers, scrollboxes, modal selection, and blocked export screens | `dxemb/web/vehicle_admin.py`, `dxemb/web/templates/vehicle_*.html`, `dxemb/shared/catalog/vehicle_builder_service.py`, route tests | `partial_or_placeholder` | Rebuild the visual shell and component language first; keep export and backend claims blocked until proven. | High risk; screenshots show richer UI than the current repository behavior. |
| DayZ server / admin / map / evidence tools | No map or evidence workflow screen observed in this intake folder | `docs/LOCAL_FINISH_RECOVERY_PLAN.md` says the map slice is paused; no active map route evidence in current web module | `blocked` | Do not advance the paused map/evidence slice from screenshots alone. | High risk; no active implementation evidence. |
| Moderation / admin / audit tools | No dedicated moderation dashboard observed | Moderation/audit services, ticket foundations, and docs exist in repo | `documented_only` | Keep admin/audit work in the docs until a protected workspace is intentionally designed. | Medium risk; existing foundations are not yet unified into a visible console. |

### E. Conflict decisions

- Preserve as visual ideas: dark charcoal surfaces, the toxic-green active state, compact card grids, pill navigation, modal selectors, explicit blocked/export states, and dense but readable utility panels.
- Treat as obsolete or lower priority: the cyan/navy admin tone in the current shell, any blue-first primary treatment, and any over-decorated browser-like experiment framing that is not actually part of the product UI.
- Require owner choice before implementation: whether export/code-generation controls stay read-only and blocked, whether the vehicle-builder modal flow should become a first-class web path, and whether the cargo/preset density should be reduced for clarity on small screens.
- Do not reconstruct from screenshots alone: backend export behavior, compatibility approvals, hidden data values, exact classnames that appear only in screenshots, or any live account/transaction state.

### F. Design-system brief

Approved-for-first-implementation direction:

- Token proposal: charcoal base, dark panel layers, electric-green primary, muted green secondary, amber warning, red error, and gray disabled tokens.
- Semantic color meanings: green = active/selected/success; amber = warning/alternate variant; red = blocked/error/destructive; gray = disabled/unavailable; blue = informational only.
- Convert first: shell, header/nav, shared panel/card styles, status pills, primary/secondary buttons, modal chrome, and scrollbox styling.
- Screens/routes to convert first: `/`, `/catalog`, `/vehicles`, and the vehicle detail/builder cards that share those surfaces.
- Non-goals for the first visual commit: no backend changes, no route additions, no database migrations, no export execution, no auth rollout, no wallet changes, and no map slice activation.
- Validation plan: run `git diff --check`, load the local shell plus `/`, `/catalog`, and `/vehicles`, confirm mobile wrapping and focus visibility, and compare the result against the recurring screenshot patterns.

### G. Major-commit sequencing update

- Keep the first implementation slice focused on a reusable green design system and the existing app shell; the screenshots only strengthen that order, they do not move any backend feature ahead of it.
- Add a visual acceptance gate before any broad dashboard or feature UI rebuild: approve the shell, nav, cards, modal states, and mobile behavior first, then expand outward.
- Preserve the current 10-commit plan order unless later evidence proves a backend or data dependency has changed; no screenshot in this intake justifies promoting a blocked backend slice.

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
| CORE-04 | Test framework | Repeatable isolated automated tests | Added unittest harness with disposable PostgreSQL test-db utilities and passing smoke tests (`tests/harness/postgres_isolated.py`, `tests/test_harness_smoke.py`); schema contracts pass in `tests/test_schema_contracts.py`; moderation audit tests pass in `tests/test_moderation_audit_service.py`; ticket lifecycle tests pass in `tests/test_ticket_service.py`; onboarding/profile tests pass in `tests/test_profile_onboarding_service.py` | `C:\DXEMB\tests` (integration/service/cog tests including economy/escrow/marketplace) | Active partial | Expand with bot/web integration contracts in future sprint | Use archive tests as recovery reference; adapt to current PERM architecture |
| BOT-01 | Discord bot startup | Bot loads safely and reports state | Present; no-op safe mode verified | Unknown | Active partial | Preserve/audit | Live token/guild test pending |
| BOT-02 | Health commands | Prefix + slash health diagnostics | Present | Unknown | Active partial | Preserve/audit | Live Discord sync pending |
| BOT-03 | Trader browsing | Guided item catalog/trader navigation | Present | Unknown | Active partial | Audit | Not purchase/delivery pipeline |
| BOT-04 | Moderation bot | Warnings, staff actions, roles, logs, permission checks | Slice A/B local moderation foundation implemented: immutable audit service + local command adapter (`dxemb/bot/cogs/moderation_local.py`) with warn, local status query, and dry-run preview only | `C:\DXEMB\discord_bot\src\cogs\moderation.py`; `C:\DXEMB\core\services\moderation_service.py`; `C:\DXEMB\core\services\audit_service.py` | Active partial | Build ticket foundation next | No kick/ban/timeout/role/channel/webhook/message mutation behavior added |
| BOT-05 | Channel automation | Welcome, announcements, staff logs, private threads, configured IDs | Not verified in active PERM runtime | `C:\DXEMB\discord_bot\src\cogs\user.py`; `C:\DXEMB\core\services\user_service.py` | Needs inventory | Recover if present | Slice 5 found no dedicated archive tests for channel automation |
| BOT-06 | Onboarding/profile/stats | User creation, starter info, profile, reputation, stats | Slice D added persistence + dry-run evaluator foundation (`dxemb/db/migrations/005_profile_onboarding_foundation.sql`, `dxemb/shared/profile_onboarding_service.py`) with passing tests | `C:\DXEMB\discord_bot\src\cogs\user.py`; `C:\DXEMB\core\services\user_service.py`; `C:\DXEMB\tests\test_user_cog.py`; `C:\DXEMB\tests\test_user_service.py` | Active partial | Build bot adapters later | Persistence/dry-run only; no role/channel/welcome/permission Discord actions added |
| BOT-07 | Support tickets | Private ticket/thread, category, assignment, close/resolve | Slice C added local-only ticket lifecycle foundation (`dxemb/db/migrations/004_ticket_foundation.sql`, `dxemb/shared/ticket_service.py`) with passing transition/audit tests | No direct module match found in `C:\DXEMB` or ZIP inventory | Active partial | Build bot/web adapters later | Local-only service implemented; no guild/channel/thread writes added |
| ECON-01 | Wallet | User balances and safe credit/debit services | Additive foundation migration and service implemented: `dxemb/db/migrations/001_wallet_ledger_foundation.sql`, `dxemb/shared/wallet_ledger_service.py`, `tests/test_wallet_ledger_service.py` | `C:\DXEMB\discord_bot\src\cogs\economy.py`; `C:\DXEMB\discord_bot\src\cogs\wallet.py`; `C:\DXEMB\core\services\economy_service.py`; `C:\DXEMB\database\migrations\004_economy_tables.sql` | Active partial | Build then integrate | Structured modules are preferred source over `BACKUP_PHASE*` monolith snapshots |
| ECON-02 | Ledger | Immutable audit for every wallet change | Immutable ledger table + no-update/no-delete triggers in additive migration; service tests pass for audit/idempotency flows | `C:\DXEMB\database\migrations\004_economy_tables.sql`; `C:\DXEMB\database\migrations\001_initial_schema.sql`; `C:\DXEMB\tests\test_economy_service.py` | Active partial | Build then integrate | Build ledger as authoritative audit layer before game/reward payouts |
| ECON-04 | Wallet bot read-only surface | Local-safe balance/history visibility and dry-run credit/debit previews | Added `dxemb/bot/cogs/wallet_local.py` with adapter tests in `tests/test_wallet_bot_adapter.py`; no live mutation command exposed | `C:\DXEMB\discord_bot\src\cogs\wallet.py`; `C:\DXEMB\core\services\economy_service.py` | Active partial | Expand with user-facing integration later | No Discord role/channel/permission/webhook/message mutation APIs used |
| ECON-05 | Wallet web read-only surface | Local-safe HTTP balance/ledger visibility with dry-run previews | Added routes in `dxemb/web/app.py` + route tests in `tests/test_wallet_web_routes.py`; mutation endpoint returns disabled response | `C:\DXEMB\admin_panel\app\routes\economy.py`; `C:\DXEMB\core\services\economy_service.py` | Active partial | Expand with auth/session constraints later | Route set is non-mutating except explicit disabled mutation endpoint |
| ECON-03 | Admin economy tools | Adjust balances with reason/audit trail | Not verified | Needs inventory | Needs inventory | Recover/adapt | Must use ledger |
| GAME-01 | Casino/games | Server-side deterministic RNG, wager/payout records | Additive game foundation implemented in `dxemb/db/migrations/008_game_economy_foundation.sql` and `dxemb/shared/game_economy_service.py` with deterministic coin-flip engine + tests in `tests/test_game_economy_service.py` | `C:\DXEMB\discord_bot\src\cogs\games.py`; `C:\DXEMB\core\services\game_service.py`; `C:\DXEMB\tests\test_end_to_end.py` | Active partial | Preserve and expand | Feature-flag guarded settlement; dry-run mode supported |
| GAME-02 | Game sessions | Wager, outcome, payout, seed, timestamp audit | `game_session` schema + idempotency and ledger-link fields implemented in migration `008_game_economy_foundation.sql`; read/history surfaces added in `dxemb/web/app.py` and `dxemb/bot/cogs/games_local.py` | Needs inventory | Active partial | Preserve and expand | Wallet ledger integration enforced via service |
| GAME-03 | Daily tasks | Definitions, progress, rewards, reset cycle | Additive task foundation implemented in `dxemb/db/migrations/009_daily_tasks_achievements_foundation.sql` + service/tests (`dxemb/shared/task_achievement_service.py`, `tests/test_task_achievement_service.py`) | `C:\DXEMB\discord_bot\src\cogs\economy.py`; `C:\DXEMB\core\services\game_service.py` | Active partial | Preserve and expand | Midnight UTC cycle behavior tested |
| GAME-04 | Achievements | Definitions, unlocks, one-time rewards | Additive achievement foundation implemented in migration `009_daily_tasks_achievements_foundation.sql` + unlock/reward idempotency tests in `tests/test_task_achievement_service.py` | `C:\DXEMB\core\models\achievement.py`; `C:\DXEMB\core\services\achievement_service.py`; `C:\DXEMB\tests\test_user_service.py` | Active partial | Preserve and expand | Wallet ledger-linked rewards and duplicate guardrails |
| GAME-05 | Missions/bounties | Create, track, reward, claim, admin moderation | Additive mission foundation implemented in `dxemb/db/migrations/010_mission_bounty_foundation.sql` + feature-flagged service/tests (`dxemb/shared/mission_bounty_service.py`, `tests/test_mission_bounty_service.py`) | Needs inventory | Active partial | Preserve and expand | Admin rule, expiry/cancel, claim idempotency validated |
| GAME-06 | Raffles/events | Tickets, winners, audit, announcements | Not verified | Needs inventory | Needs inventory | Recover/adapt | Feature-toggle gated |
| AUTO-01 | Admin catalog | Allowed items, price, enabled/sellable controls | Catalog/admin routes present | Needs inventory | Active partial | Audit/extend | Console-safe only |
| AUTO-02 | Vehicle builder | Admin-approved vehicle presets and valid parts/cargo | Present | Needs inventory | Active partial | Audit/extend | No PC/mod content |
| AUTO-03 | Auto-Trader products | Admin-owned items/kits/vehicles/hordes/airdrops | Additive product schema in `dxemb/db/migrations/006_auto_trader_order_foundation.sql` with item/kit/vehicle references, sellability/stock controls, and console-safe metadata | `C:\DXEMB\core\services\admin_service.py`; `C:\DXEMB\database\migrations\005_product_tables.sql` | Active partial | Build then integrate | Separate from market; no P2P table coupling |
| AUTO-04 | Trader orders | Payment to completion state machine | Additive `trader_order` + immutable `trader_order_event` schema and service/tests: `dxemb/shared/auto_trader_order_service.py`, `tests/test_auto_trader_order_service.py` | `C:\DXEMB\core\services\trader_service.py`; `C:\DXEMB\database\migrations\006_order_tables.sql` | Active partial | Build then integrate | Dedicated `TraderOrder` domain with auditable transitions |
| AUTO-05 | Spawn queue | Audited physical spawn request/attempt/failure/refund | Not present | Needs inventory | Needs recovery | Design then build | No claim codes |
| AUTO-06 | Custom kits | Console-valid attachment/nesting builder | Not verified | Needs inventory | Needs inventory | Recover/adapt | Validate build-time |
| AUTO-07 | Zombie hordes | Admin product and controlled spawn flow | Not verified | Needs inventory | Needs inventory | Recover/adapt | Feature-toggle gated |
| AUTO-08 | Airdrops | Buyer location, randomized contents, warning/announcement | Not verified | Needs inventory | Needs inventory | Recover/adapt | Location player-chosen |
| MARKET-01 | Player listings | P2P item/vehicle listings with lifecycle | Additive foundation migration/service implemented: `dxemb/db/migrations/002_market_escrow_foundation.sql`, `dxemb/shared/market_escrow_service.py`, `tests/test_market_escrow_service.py` | `C:\DXEMB\discord_bot\src\cogs\marketplace.py`; `C:\DXEMB\core\services\marketplace_service.py`; `C:\DXEMB\database\migrations\002_marketplace_tables.sql`; `C:\DXEMB\tests\test_marketplace_service.py` | Active partial | Build then integrate | Never server-spawn; delivery mode constrained to `P2P_PHYSICAL` |
| MARKET-02 | P2P escrow | Holds, release, cancel, refund, dispute, payout | Foundation lifecycle and audit events implemented in additive schema/service with tests for hold/release/dispute/refund | `C:\DXEMB\discord_bot\src\cogs\escrow.py`; `C:\DXEMB\core\services\escrow_service.py`; `C:\DXEMB\database\migrations\003_escrow_schema.sql`; `C:\DXEMB\tests\test_escrow_service.py`; `C:\DXEMB\tests\test_dispute_service.py` | Active partial | Build then integrate | No Auto-Trader behavior; no runtime spawn path added |
| MARKET-04 | P2P bot local-safe workflows | Local-safe preview/create/hold/status flows for listings and escrow | Added `dxemb/bot/cogs/market_local.py` and adapter tests in `tests/test_market_bot_adapter.py` | `C:\DXEMB\discord_bot\src\cogs\marketplace.py`; `C:\DXEMB\core\services\marketplace_service.py` | Active partial | Expand with web parity and auth checks | Explicit preview returns `spawn_behavior=not-supported` and `delivery_mode=P2P_PHYSICAL` |
| MARKET-05 | P2P web read-only workflows | Local-safe browse/detail/preview/status timeline routes | Added routes in `dxemb/web/app.py` and tests in `tests/test_market_web_routes.py` | `C:\DXEMB\admin_panel\app\routes\marketplace.py`; `C:\DXEMB\core\services\marketplace_service.py` | Active partial | Expand with auth/session constraints later | Includes escrow timeline endpoint and explicit no-spawn preview behavior |
| MARKET-03 | Marketplace moderation | Admin review and dispute actions | Not verified | Needs inventory | Needs inventory | Recover/adapt | Audit every action |
| NIT-01 | Nitrado/FTP client | Console file pull/upload/backup actions | Design reference candidates reviewed only; no runtime integration in active PERM | `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\bot\services\nitrado_client.py`; `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\bot\services\ftp_client.py`; `C:\DXEMB\REPO CLONE\DayZTrader\dayz-console-trader-bot\dayz-console-trader-bot\bot\services\xml_generator.py`; `dayz-console-trader-bot.zip: dayz-console-trader-bot/bot/services/nitrado_client.py`; `dayz-console-trader-bot.zip: dayz-console-trader-bot/bot/services/ftp_client.py`; `dayz-console-trader-bot.zip: dayz-console-trader-bot/bot/services/xml_generator.py` | Planned | Design then build | Outbound only; credentials by secret reference only |
| NIT-02 | Restart scheduler | Poll/cached restart windows | Additive scheduler foundation implemented with fake-provider flow only: `dxemb/db/migrations/007_nitrado_delivery_scheduler_foundation.sql`, `dxemb/shared/nitrado_delivery_decision_engine.py`, `dxemb/shared/nitrado_delivery_scheduler_service.py`, `tests/test_nitrado_delivery_scheduler_schema.py`, `tests/test_nitrado_delivery_decision_engine.py`, `tests/test_nitrado_delivery_scheduler_service.py` | `docs/NITRADO_DELIVERY_SCHEDULER_DESIGN.md` | Active partial | Build then integrate | Never force restart; no live provider calls enabled |
| NIT-03 | Spawn-file writer | Controlled writes before confirmed restart | Dry-run artifact metadata only (no file write): `trader_spawn_artifact` + `prepare_artifact_metadata_dry_run` and tests in `tests/test_nitrado_delivery_scheduler_service.py` | `docs/NITRADO_DELIVERY_SCHEDULER_DESIGN.md` | Active partial | Build then integrate | No XML generation/upload/write/delete in active code |
| NIT-04 | Status scheduler | 5-minute status checks and 30-minute file pulls | Not verified | Needs inventory | Needs inventory | Recover/adapt | Separate tool if needed |
| WEB-01 | Flask dashboard | Health/status/admin shell | Present | Needs inventory | Active partial | Preserve/audit | Browser route test pending |
| WEB-02 | Catalog administration | Item cards, prices, availability | Present | Needs inventory | Active partial | Preserve/audit | Bulk tools pending |
| WEB-03 | Vehicle administration | Vehicle catalog/builder endpoints | Present | Needs inventory | Active partial | Preserve/audit | Validate console data |
| WEB-04 | Economy dashboard | Wallet/ledger/admin adjustments | Not verified | Needs inventory | Needs recovery | Recover/adapt | Requires ECON tables |
| WEB-05 | Ticket dashboard | View/assign/close tickets | Not verified | Needs inventory | Needs inventory | Recover/adapt | Requires BOT-07 |
| WEB-06 | Order dashboard | Auto-Trader order/spawn management | Local-safe read-only/dry-run routes added in `dxemb/web/app.py` with route tests `tests/test_auto_trader_web_routes.py` | `C:\DXEMB\admin_panel\app\routes\trader.py`; `C:\DXEMB\core\services\trader_service.py` | Active partial | Expand with auth/session constraints then controlled delivery orchestration | Namespace separated under `/autotrader/*` |
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

Prepare owner-reviewed next slice after games/tasks/achievements foundation:
- add auth/session controls for new local preview surfaces
- expand reconciliation/reporting rollups across wallet, game sessions, tasks, achievements, and missions

Do not connect live Nitrado/FTP/API flows without explicit owner approval.

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
- Slice B completed: local moderation command adapter added in `dxemb/bot/cogs/moderation_local.py` and loaded via `dxemb/bot/main.py`.
- Slice B command scope enforced: warn, local moderation-action query/status, and dry-run moderation preview only.
- Slice B validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_moderation_command_adapter -v`, `docker compose config`, `docker compose down`.
- Slice C completed: ticket foundation added via `dxemb/db/migrations/004_ticket_foundation.sql` and `dxemb/shared/ticket_service.py`.
- Slice C validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_ticket_service -v`, `docker compose config`, `docker compose down`.
- Slice D completed: profile/onboarding persistence and dry-run evaluator added via `dxemb/db/migrations/005_profile_onboarding_foundation.sql` and `dxemb/shared/profile_onboarding_service.py`.
- Slice D validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_profile_onboarding_service -v`, `docker compose config`, `docker compose down`.
- Slice E completed: ledger/continuity/plan reconciliation updated with exact Slice A-D evidence and residual gaps.
- No external Discord, Neon, Nitrado, `.env`, or deployment setting actions were performed in Slices A-E.
- Recommended next autonomous sprint: **Bot/web integration for wallet plus Player Market/Escrow foundations** (current foundations are implemented/tested but not wired into active bot/web flows).
- Wallet+P2P integration Slice A completed: local-safe wallet bot adapter/cog added with read-only balance/history and dry-run credit/debit previews.
- Wallet+P2P Slice A validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_wallet_bot_adapter -v`, `docker compose config`, `docker compose down`.
- Wallet+P2P integration Slice B completed: wallet web read-only routes for balance/ledger and dry-run preview added; mutation route hard-disabled (`403`).
- Wallet+P2P Slice B validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_wallet_web_routes -v`, `docker compose config`, `docker compose down`.
- Wallet+P2P integration Slice C completed: local-safe market bot adapter/cog for preview/create/hold/status workflows with P2P physical-only constraints.
- Wallet+P2P Slice C validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_market_bot_adapter -v`, `docker compose config`, `docker compose down`.
- Wallet+P2P integration Slice D completed: local-safe market web routes for browse/detail/preview plus escrow status/timeline.
- Wallet+P2P Slice D validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_market_web_routes -v`, `docker compose config`, `docker compose down`.
- Wallet+P2P integration Slice E completed: final reconciliation and consolidated A-D regression run passed (`14` tests).
- Wallet+P2P Slice E evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_wallet_bot_adapter tests.test_wallet_web_routes tests.test_market_bot_adapter tests.test_market_web_routes -v`, `docker compose config`, `docker compose down`.
- Auto-Trader sprint Slice A completed: additive product/order/order-event schema and order service implemented with transition/idempotency/allow-list/P2P-separation tests.
- Auto-Trader Slice A evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_auto_trader_order_service -v`, `docker compose config`, `docker compose down`.
- Auto-Trader sprint Slice B completed: atomic wallet-to-order bridge with idempotent debit and refund behavior implemented.
- Auto-Trader Slice B evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_auto_trader_wallet_bridge -v`, `docker compose config`, `docker compose down`.
- Auto-Trader sprint Slice C completed: local-safe bot/web preview surfaces added under separate Auto-Trader namespace.
- Auto-Trader Slice C evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_auto_trader_bot_adapter tests.test_auto_trader_web_routes -v`, `docker compose config`, `docker compose down`.
- Auto-Trader sprint Slice D completed: reconciliation and consolidated sprint regression run passed (`15` tests).
- Auto-Trader Slice D evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_auto_trader_order_service tests.test_auto_trader_wallet_bridge tests.test_auto_trader_bot_adapter tests.test_auto_trader_web_routes -v`, `docker compose config`, `docker compose down`.
- Nitrado scheduler design-only sprint completed: implementation-ready design contract added at `docs/NITRADO_DELIVERY_SCHEDULER_DESIGN.md`.
- Nitrado design sprint evidence recorded: required boundary mapping, data-model proposal, scheduler behavior, failure/refund policy, DayZ artifact rules, security/ops controls, test plan, and additive implementation sequence documented with read-only archive candidate references.
- Nitrado design sprint confirmed: no Nitrado/FTP/API calls, no scheduler runtime, no file writes, no restart actions, and no source changes outside approved docs files.
- Fake-provider scheduler foundation Slice A completed: additive migration `dxemb/db/migrations/007_nitrado_delivery_scheduler_foundation.sql` with strict FK/idempotency/immutability constraints.
- Fake-provider scheduler foundation Slice A tests completed: `tests/test_nitrado_delivery_scheduler_schema.py` (6 tests).
- Fake-provider scheduler foundation Slice B completed: pure decision engine in `dxemb/shared/nitrado_delivery_decision_engine.py` with fake-clock timing tests in `tests/test_nitrado_delivery_decision_engine.py` (11 tests).
- Fake-provider scheduler foundation Slice C completed: interfaces/fakes/scaffolding in `dxemb/shared/nitrado_delivery_interfaces.py`, `dxemb/shared/nitrado_delivery_fakes.py`, `dxemb/shared/nitrado_delivery_scheduler_service.py` with service/boundary tests (`tests/test_nitrado_delivery_scheduler_service.py`, `tests/test_nitrado_delivery_fake_boundaries.py`).
- Fake-provider scheduler foundation Slice D completed: read-only local operator visibility routes in `dxemb/web/app.py` with route tests in `tests/test_nitrado_delivery_web_routes.py`.
- Scheduler consolidated validation evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_nitrado_delivery_scheduler_schema tests.test_nitrado_delivery_decision_engine tests.test_nitrado_delivery_scheduler_service tests.test_nitrado_delivery_fake_boundaries tests.test_nitrado_delivery_web_routes tests.test_auto_trader_web_routes -v`, `docker compose config`, `docker compose down` (31 tests passed).
- Scheduler sprint boundary compliance confirmed: no real network clients or calls, no scheduler daemon/background process, no XML/DayZ file writes, no restart actions, no P2P behavior/table modifications.
- Games sprint Slice A completed: additive game economy foundation (`dxemb/db/migrations/008_game_economy_foundation.sql`, `dxemb/shared/game_economy_service.py`) with deterministic coin-flip and ledger-gated settlement tests in `tests/test_game_economy_service.py`.
- Games sprint Slice A evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_game_economy_service -v`, `docker compose config`, `docker compose down`.
- Games sprint Slice B completed: additive daily tasks + achievements foundation (`dxemb/db/migrations/009_daily_tasks_achievements_foundation.sql`, `dxemb/shared/task_achievement_service.py`) with reset/idempotent reward tests in `tests/test_task_achievement_service.py`.
- Games sprint Slice B evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_game_economy_service tests.test_task_achievement_service -v`, `docker compose config`, `docker compose down`.
- Games sprint Slice C completed: additive mission/bounty foundation (`dxemb/db/migrations/010_mission_bounty_foundation.sql`, `dxemb/shared/mission_bounty_service.py`) with admin/cancel/expiry/claim-idempotency coverage in `tests/test_mission_bounty_service.py`.
- Games sprint Slice C evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_game_economy_service tests.test_task_achievement_service tests.test_mission_bounty_service -v`, `docker compose config`, `docker compose down`.
- Games sprint Slice D completed: local-safe read-only/dry-run preview surfaces for games/tasks/achievements/missions in `dxemb/web/app.py` and `dxemb/bot/cogs/games_local.py` with route/adapter coverage in `tests/test_games_tasks_missions_web_routes.py` and `tests/test_games_tasks_missions_bot_adapter.py`.
- Games sprint Slice D evidence recorded: `git diff --check`, `docker compose up -d db; python -m unittest tests.test_game_economy_service tests.test_task_achievement_service tests.test_mission_bounty_service tests.test_games_tasks_missions_bot_adapter tests.test_games_tasks_missions_web_routes -v`, `docker compose config`, `docker compose down`.

---
End of permanent feature recovery ledger.
