# MASTER_HANDOFF.md
# D.X.E.M.B — Master Project Handoff Document

---

## Project Identity

| Field | Value |
|---|---|
| Full Name | D.X.E.M.B (DayZ Xbox/PlayStation Escrow Marketplace Bot) |
| Package Name | `dxemb` |
| Platform Targets | Xbox Console, PlayStation Console (no PC-specific mechanics) |
| Core Stack | Python, discord.py, Flask, PostgreSQL, Docker |
| Currency | TZ-Credits |
| Repo Owner | Shawnowens4 |

### What it is
A Discord bot + Flask admin dashboard for a DayZ console server providing:
- **Auto-Trader**: admin-stocked item purchase pipeline, spawn-queue driven, Nitrado-aware
- **Player Marketplace**: player-to-player escrow listings with physical in-game pickup
- **TZ-Credits**: server economy currency
- **Admin Tooling**: vehicle builder, economy editor, feature toggles, support tickets
- **Entertainment**: casino games, daily tasks, achievements

---

## Locked Rules (Non-Negotiable)

### Delivery Rule
- No non-spawn/claim-code delivery. Every item must physically spawn in-game.
- Valid methods: ground spawn at map coordinate, vehicle cargo spawn.

### Auto-Trader vs Player Marketplace — Terminology Lock
- **Auto-Trader**: admin-stocked products, bot is seller, price fixed by admin, fulfilled via TraderOrder spawn pipeline.
- **Player Marketplace**: player-to-player only, bot is escrow agent only, physical in-game pickup.
- Strictly separate in terminology, UI, code, and user-facing language. Never conflate.

### Console Constraints
- No liquid values in cargo/trunk configs.
- Cargo items use: quantity, chance, damage only.
- Attachment/nesting must follow valid console DayZ rules.

### Vehicle Rules (Player Marketplace)
- Non-running vehicles cannot be listed. Running condition required.
- Admin-built vehicle presets (Auto-Trader) are exempt.

### Trunk Screenshot Rules
- Buyer uploads trunk screenshot at time of sale.
- Seller uploads trunk screenshot only on dispute.

### Nitrado Restart-Schedule Rules
- FTP/API check before writing any spawn files.
- Spawn files written ~10 minutes before confirmed restart window.
- Never force a Nitrado restart.
- Restart schedule cached in DB, refreshed each poll cycle.

---

## All Subsystems Designed

### 1. Admin-Controlled Sellability Toggle
- Per-product `sellable` flag on `AutoTraderProduct`.
- Admin flips from Flask dashboard (card-based UI).
- Unsellable items hidden from all player-facing flows.

### 2. Zombie Horde Product Type
- Config: wave count, difficulty, location class, price.
- Spawned via TraderOrder pipeline. FeatureToggle gated.

### 3. Custom Kit Product Type
- Admin-built item kit. Card-selector UI for kit building.
- Attachment/nesting rules validated at build time.
- Spawned via TraderOrder pipeline.

### 4. Airdrop Product Type
- Buyer chooses drop location via map picker (location is player-chosen, not random).
- Contents are randomized from a configured pool.
- At spawn_requested: public #airdrops @here announcement.
- Announcement includes: ~125m radius warning, dzmap POI-based region label.
- Anonymous buyer by default. FeatureToggle can reveal buyer name.

### 5. Map Tile Source Decision
- dzmap self-hosted tile source selected.
- xam.nu CDN explicitly rejected.
- Map picker embedded in Flask dashboard.
- Coordinate → POI region label used for Airdrop announcements.

### 6. TraderOrder State Machine (Restart-Aware)
States:
```
pending_payment → paid → queued_for_next_restart → spawn_requested → spawn_complete
                                                                    → spawn_failed
```
- spawn_failed triggers admin alert and wallet auto-refund.

### 7. Admin Support Ticket Bot
- SupportTicket model: user, category, description, state, assigned_admin, created_at.
- /ticket command opens private Discord thread.
- States: open → in_progress → resolved / closed.
- Admin Flask view for management.

### 8. FeatureToggle System
- FeatureToggle model: key, enabled, description.
- Every subsystem checks toggle before executing.
- Admin Flask UI to flip live without restart.
- Circuit breaker for every subsystem.

### 9. Casino Games
- Flask web view hosts game UI.
- Discord launcher embed with Play button.
- Discord summary embed after session.
- All RNG is deterministic server-side only.
- GameSession model: user, game_type, wager, outcome, payout, seed, created_at.
- WalletLedgerEntry for every wager and payout. FeatureToggle gated.

### 10. Daily Tasks & Achievements
- DailyTaskDefinition model: task_key, description, reward_credits, reset_type.
- AchievementDefinition model: key, description, reward_credits, one_time.
- UserDailyTask and UserAchievement track per-user progress.
- Daily reset at midnight UTC. Discord embed on completion. FeatureToggle gated.

---

## Deployment Sequencing Rule

1. Phase 0 → local Docker only.
2. Phase 1 → local Docker only.
3. Phase 2 → local Docker only.
4. Phase 3 → local Docker only until E6 sign-off.
5. Only after Phase 2 E6 AND Auto-Trader audit sign-off: begin Deployment Gate toward Cloudflare.
6. Cloudflare tunnels and public URLs disabled until that gate is passed.

> ⚠️ Auto-Trader pipeline has NOT been broken into its own Epic A–E checklist. Required open task.

---

## Progress-Tracker Rule (All Future Sessions)

Every response must begin with:
1. Labeled progress bar per phase/subsystem.
2. One Total Project Progress bar.
3. Uses 7-stage lifecycle.
4. Coded-but-untested never exceeds 40–50%.

---
*End of MASTER_HANDOFF.md*
