# PHASE2_CHECKLIST.md
# DXEMB — Phase 2 Epic A–E Checklist (Docker-Gated)

---

## Deployment Gate (must pass before ANY public/Cloudflare work)

- [ ] Phase 2 E6 sign-off complete
- [ ] Auto-Trader pipeline audit complete (separate checklist — NOT YET STARTED)
- [ ] `docker-compose up` clean boot confirmed on Windows 11 Docker Desktop
- [ ] Discord OAuth2 local redirect confirmed working
- [ ] Nitrado integration confirmed outbound-poll only (no inbound webhooks)
- [ ] Discord bot confirmed Gateway/WebSocket mode only (no HTTP callbacks)

---

## 7-Stage Completion Lifecycle

| Stage | Label | Max Weight if Only This Stage Done |
|---|---|---|
| 1 | Design | 10% |
| 2 | Implementation | 40–50% (coded-but-untested NEVER exceeds 50%) |
| 3 | Automated tests written | 60% |
| 4 | Automated tests passing | 70% |
| 5 | Headless browser / Discord tests passing | 80% |
| 6 | Full audit pass | 90% |
| 7 | Real user testing + sign-off | 100% |

**Weighting rule:** A feature coded but with zero passing tests is capped at 40–50% regardless of polish.

---

## Epic A — Implementation Wiring Issues

### A0 — Docker-Local Stack Verification (GATE ISSUE)
- [ ] A0.1 — `docker-compose up` boots all containers cleanly
- [ ] A0.2 — Flask `/health` returns 200 OK
- [ ] A0.3 — Bot logs "online" to console with no crash
- [ ] A0.4 — DB container accepts connections, schema applies cleanly
- [ ] A0.5 — `.env.example` documents every required variable
- [ ] A0.6 — README quick-start confirmed accurate

### A1 — TZ-Credits Wallet Model
- [ ] A1.1 — `Wallet` model created with balance, user_id, ledger relation
- [ ] A1.2 — `WalletLedgerEntry` model (amount, reason, timestamp, actor)
- [ ] A1.3 — Credit/debit service functions with audit trail
- [ ] A1.4 — Negative balance guard enforced at service layer
- Dependencies: A0

### A2 — User Model & Discord Identity Link
- [ ] A2.1 — `User` model stores discord_id, username, joined_at
- [ ] A2.2 — Auto-create user on first bot interaction
- [ ] A2.3 — Flask session ties to Discord OAuth2 identity
- Dependencies: A0

### A3 — FeatureToggle System
- [ ] A3.1 — `FeatureToggle` model (key, enabled, description)
- [ ] A3.2 — Toggle check helper used by all subsystems
- [ ] A3.3 — Admin Flask UI to flip toggles without restart
- [ ] A3.4 — Default toggles seeded in migration
- Dependencies: A0, A2

### A4 — Auto-Trader Product Catalog
- [ ] A4.1 — `AutoTraderProduct` model (class_name, display_name, price, category, enabled)
- [ ] A4.2 — Sellability toggle per product (admin-controlled)
- [ ] A4.3 — types.xml import/sync service
- [ ] A4.4 — DayZIDB thumbnail resolver wired to product cards
- Dependencies: A0, A3

### A5 — TraderOrder State Machine
- [ ] A5.1 — `TraderOrder` model (user, product, quantity, state, created_at)
- [ ] A5.2 — States: pending_payment → paid → queued_for_next_restart → spawn_requested → spawn_complete / spawn_failed
- [ ] A5.3 — Restart-schedule awareness (FTP/API check, write spawn files ~10 min before restart)
- [ ] A5.4 — Never force a Nitrado restart
- [ ] A5.5 — spawn_failed triggers admin alert and wallet refund
- Dependencies: A1, A4, A9

### A6 — Player Marketplace (Escrow)
- [ ] A6.1 — `MarketplaceListing` model (seller, item_class, condition, price, state, escrow_held)
- [ ] A6.2 — Escrow hold on listing creation, release on sale/cancellation
- [ ] A6.3 — Non-running vehicles blocked from listing
- [ ] A6.4 — Trunk screenshot: buyer uploads at sale, seller only on dispute
- [ ] A6.5 — Physical in-game pickup only
- Dependencies: A1, A2, A3

### A7 — SupportTicket System
- [ ] A7.1 — `SupportTicket` model (user, category, description, state, assigned_admin, created_at)
- [ ] A7.2 — Discord slash command opens private thread
- [ ] A7.3 — Admin Flask view to list/assign/close
- [ ] A7.4 — States: open → in_progress → resolved / closed
- Dependencies: A2, A3

### A8 — Zombie Horde Product Type
- [ ] A8.1 — `ZombieHordeProduct` model (wave_count, difficulty, location_class, price)
- [ ] A8.2 — Admin card-selector UI
- [ ] A8.3 — TraderOrder pipeline adapted for horde spawn
- [ ] A8.4 — FeatureToggle guard
- Dependencies: A4, A5

### A9 — Nitrado Restart-Schedule Integration
- [ ] A9.1 — Nitrado API/FTP poller for restart schedule
- [ ] A9.2 — Schedule cached in DB, refreshed each poll cycle
- [ ] A9.3 — TraderOrder queue checks schedule before writing spawn files
- [ ] A9.4 — Spawn files written ~10 min before confirmed restart window
- [ ] A9.5 — Admin dashboard shows restart schedule status
- Dependencies: A0

### A10 — Airdrop Product Type
- [ ] A10.1 — `AirdropProduct` model (contents_pool, price, anonymous_by_default)
- [ ] A10.2 — Map picker for buyer-chosen drop location
- [ ] A10.3 — Randomized contents only (location is player-chosen)
- [ ] A10.4 — Public #airdrops @here announcement at spawn_requested
- [ ] A10.5 — ~125m radius warning in announcement
- [ ] A10.6 — dzmap POI-based region label in announcement
- [ ] A10.7 — Anonymous buyer by default; FeatureToggle to reveal
- Dependencies: A4, A5, A15

### A11 — Custom Kit Product Type
- [ ] A11.1 — `CustomKitProduct` model (item_list, price, kit_name)
- [ ] A11.2 — Admin card-selector UI for kit contents
- [ ] A11.3 — Attachment/nesting rules validated at build time
- [ ] A11.4 — TraderOrder pipeline adapted for kit spawn
- Dependencies: A4, A5

### A12 — Casino — GameSession & RNG
- [ ] A12.1 — `GameSession` model (user, game_type, wager, outcome, payout, seed, created_at)
- [ ] A12.2 — Deterministic server-side RNG only
- [ ] A12.3 — WalletLedgerEntry for every wager and payout
- [ ] A12.4 — FeatureToggle guard
- Dependencies: A1, A3

### A13 — Casino — Flask Web Views
- [ ] A13.1 — Flask route per game type
- [ ] A13.2 — Discord launcher embed with Play button
- [ ] A13.3 — Discord summary embed after session ends
- [ ] A13.4 — No game logic in Discord — launcher/summary only
- Dependencies: A12

### A14 — Daily Tasks & Achievements
- [ ] A14.1 — `DailyTaskDefinition` model
- [ ] A14.2 — `AchievementDefinition` model
- [ ] A14.3 — `UserDailyTask` and `UserAchievement` progress tracking
- [ ] A14.4 — Daily reset job (midnight UTC)
- [ ] A14.5 — Discord embed on task/achievement completion
- [ ] A14.6 — FeatureToggle guard
- Dependencies: A1, A2, A3

### A15 — Map Picker / dzmap Integration
- [ ] A15.1 — dzmap self-hosted tile source (NOT xam.nu CDN)
- [ ] A15.2 — Map picker modal in Flask dashboard
- [ ] A15.3 — Coordinate → dzmap POI region label lookup
- [ ] A15.4 — Location result passed to Airdrop flow
- Dependencies: A0

### A16 — Admin Vehicle Builder (Card Selector)
- [ ] A16.1 — Vehicle list from events.xml / cfgspawnabletypes.xml
- [ ] A16.2 — Card thumbnail selector for base vehicle
- [ ] A16.3 — Card selector for each vehicle part
- [ ] A16.4 — Color/variant swapping for valid same-family variants
- [ ] A16.5 — Enable/disable individual parts per preset
- [ ] A16.6 — DayZIDB WebP thumbnails throughout
- Dependencies: A0, A4

### A17 — Vehicle Trunk Loadout Builder
- [ ] A17.1 — Trunk/cargo builder per vehicle preset
- [ ] A17.2 — Card-based cargo item selector (quantity, chance, damage)
- [ ] A17.3 — Attachment/nesting rules enforced (no liquid values on console)
- [ ] A17.4 — Distinction: installed parts vs loose cargo vs nested kits
- [ ] A17.5 — Invalid combinations blocked or flagged
- Dependencies: A16

### A18 — Admin Sellability Toggle
- [ ] A18.1 — Per-product `sellable` flag
- [ ] A18.2 — Admin Flask UI toggle (card-based)
- [ ] A18.3 — Bot hides unsellable items from browse/buy
- Dependencies: A4

### A19 — Discord Bot Command Layer
- [ ] A19.1 — /buy → guided browse flow
- [ ] A19.2 — /balance → wallet embed
- [ ] A19.3 — /market list → marketplace browse
- [ ] A19.4 — /market sell → listing creation
- [ ] A19.5 — /ticket → support ticket
- [ ] A19.6 — /airdrop → map picker → order
- [ ] A19.7 — All commands respect FeatureToggle guards
- Dependencies: A1–A18

### A20 — Flask Admin Dashboard
- [ ] A20.1 — Auth-gated (Discord OAuth2, role-check)
- [ ] A20.2 — Economy editor (set/adjust wallet/bank, reason, audit log)
- [ ] A20.3 — Order management view
- [ ] A20.4 — Marketplace moderation view
- [ ] A20.5 — Ticket management view
- [ ] A20.6 — Feature toggle panel
- [ ] A20.7 — Vehicle builder UI
- [ ] A20.8 — Casino session log view
- Dependencies: A1–A19

### A21 — Onboarding Flow
- [ ] A21.1 — /start or join-event triggers onboarding sequence
- [ ] A21.2 — Creates User + Wallet with starter credits
- [ ] A21.3 — Explains Auto-Trader vs Player Marketplace
- [ ] A21.4 — Explains TZ-Credits
- [ ] A21.5 — FeatureToggle guard
- Dependencies: A1, A2, A3, A19

---

## Epic B — Automated Tests

### B0 — Docker Test Runner Setup (GATE ISSUE)
- [ ] B0.1 — `docker-compose run tests` executes full suite
- [ ] B0.2 — Test DB isolated from dev DB
- [ ] B0.3 — Test results written for CI inspection
- [ ] B0.4 — All tests fail-fast cleanly

### B1–B13
- [ ] B1 — Wallet/ledger unit tests
- [ ] B2 — User model and auto-create tests
- [ ] B3 — FeatureToggle tests
- [ ] B4 — AutoTraderProduct CRUD and sellability tests
- [ ] B5 — TraderOrder state machine tests (all valid + invalid paths)
- [ ] B6 — Restart-schedule integration tests (mock Nitrado API)
- [ ] B7 — Player Marketplace escrow tests
- [ ] B8 — SupportTicket lifecycle tests
- [ ] B9 — Airdrop order + announcement tests (mock Discord)
- [ ] B10 — Casino RNG determinism tests (same seed = same outcome)
- [ ] B11 — Daily task reset and achievement unlock tests
- [ ] B12 — Vehicle builder preset persistence tests
- [ ] B13 — Onboarding flow integration tests

---

## Epic C — Headless Browser / Discord UI Tests

### C0 — Playwright Harness Setup (GATE ISSUE)
- [ ] C0.1 — Playwright installed and runnable in Docker
- [ ] C0.2 — Can load Flask dashboard headlessly
- [ ] C0.3 — Screenshot capture works on failure

### C1–C6 — Flask Dashboard UI tests
- [ ] C1 — Login and auth-gate
- [ ] C2 — Economy editor UI
- [ ] C3 — Feature toggle flip UI
- [ ] C4 — Order management state override UI
- [ ] C5 — Vehicle builder card selector flow UI
- [ ] C6 — Ticket management UI

### C7 — Discord Test Harness Setup (GATE ISSUE)
- [ ] C7.1 — Test bot token for isolated test guild
- [ ] C7.2 — Test guild seeded with required roles/channels

### C8–C11 — Discord command tests
- [ ] C8 — /buy guided flow
- [ ] C9 — /balance embed
- [ ] C10 — /ticket open → thread creation
- [ ] C11 — /airdrop → #airdrops announcement

---

## Epic D — Audit Pass
> Requires all A1–A21 complete first.

- [ ] D1 — Feature-completeness audit
- [ ] D2 — Stale assumptions audit
- [ ] D3 — Schema drift audit
- [ ] D4 — Orphaned endpoints audit
- [ ] D5 — Dead code audit
- [ ] D6 — Compiled audit report → `docs/AUDIT_REPORT.md`

---

## Epic E — Real User Testing & Sign-Off

### E0 — Docker-Local Staging Confirmation (GATE ISSUE)
> Cloudflare NOT involved at this stage.
- [ ] E0.1 — Full stack running locally via docker-compose
- [ ] E0.2 — No Cloudflare tunnel active during E testing
- [ ] E0.3 — Test users via local network only

### E1–E6
- [ ] E1 — Recruit testers and prepare test scripts
- [ ] E2 — Happy-path playtest
- [ ] E3 — Edge-case playtest
- [ ] E4 — Triage and fix E2/E3 findings
- [ ] E5 — Regression pass after E4 fixes
- [ ] E6 — **Phase 2 Sign-Off** ✅

---

## Open Flags
- 🚩 Auto-Trader pipeline needs its own Epic A–E checklist — NOT STARTED
- 🚩 Casino/Tasks/Achievements needs its own Epic A–E checklist — NOT STARTED
- 🚩 Cloudflare gated behind E6 AND Auto-Trader sign-off

---
*End of PHASE2_CHECKLIST.md*
