# DayZTrader / DXEMB — Controlled Rebuild Continuity

> Authoritative resume record. Read this before planning, editing, testing, or proposing work.
> Last updated: 2026-08-13.
> Current mode: read-only reconciliation and architecture audit. No server, database, Nitrado, or implementation changes are approved by this record.

## Active UI Rule

- `dxemb/web/templates/oldbase.html` is the only active visual/UI source.
- Do not create, restore, extend, or use `base.html`, dashboard templates, or another HTML shell as the rebuild source.
- Do not paste oldbase over the application. Port/replace its demo behavior in controlled slices only after audit closeout.
- Git commit `1f90a668` is the oldbase canonical-source checkpoint.
- Git commit `424322bb` changed `dashboard.html`; retain it as quarantined recovery evidence. Do not use it as active UI direction and do not delete/reset it.

## Locked Product Boundaries

One web app has four workspaces:

1. Server Editor — Owner/Admin full control: server files, CE XML tools, Server Vehicle Builder, Event Pack Builder, map/log tools, validated exports, and later Nitrado controls.
2. Trader Control — Owner/Admin plus Trader role: Auto Trader catalog, product availability, pricing, bundles, completed weapons, vehicle products, orders, staff shifts, and manual sellback operations.
3. Discord Operations — Admin/Mod/Trader role-specific bot functions, moderation, tickets, announcements, and support.
4. Player Systems — later player-facing bot features: Auto Trader purchase flow, P2P market/escrow, games, onboarding, tasks, and notifications.

Server Vehicle Builder and Trader Vehicle Product Builder are separate outputs. They may reuse verified data/cards but never share the same preset/export record.

## Roles

- Owner: all controls; exclusive credential setup/rotation/revocation, billing/payment-account boundary, and permission delegation.
- Backup Superuser: the lead admin account with owner-approved emergency bot/server recovery scopes; no billing/payment access by default.
- Admin: full Server Editor access and only Owner-granted Nitrado action scopes.
- Trader: Mod capabilities plus Trader Control operations; no Server Editor/XML/map/Nitrado access.
- Mod: Discord moderation, ticket support, and Change Explorer read-only access; no Trader product/payout control.
- Player: player-facing bot features only.

The existing `local_auth.py` browser role hint is local-demo/test-only and is not production security.

## Console-Only Rule

All server-touching behavior must use the latest applicable official Bohemia Interactive Central Economy source/schema for the selected Xbox/PlayStation map and mission. Never use PC-only mechanics, mods, scripts, PBOs, Arma assumptions, or guessed compatibility. Unknown console compatibility fails closed.

Before a server-facing import/export/upload: record the official source revision, selected map/mission, server-original source snapshot, validation result, and no-PC/mod/script result.

Verified official ChernarusPlus baseline candidate during this audit: Bohemia commit `083cd041b88e196b6e1c312dfc272ae8120d9752` dated 2026-07-15, `Changed: updated dayzOffline.chernarusplus mission files`. Re-check the matching current server update before real implementation/export.

## Current Audit Findings

- `oldbase.html` has a useful browser-side CE intake, vehicle/cargo/attachment/workbench prototype, DayZIDB mapping, and review-preview UX. Its vehicle data, compatibility, export, settings, and many actions are demo/hard-coded and not server truth.
- The real Server Editor needs Server File Workspace, Types/Spawnable Types/Events/Event Spawns editors, map/log workspace, Event Pack Builder, validated console XML export, change history, and Nitrado settings.
- The Safe Types XML Importer is a strong recovery candidate: malformed/DTD/entity rejection, dry run/apply, SHA-256 provenance, evidence locators, idempotent import, and curation preservation. It is catalog intake only, not a server XML editor.
- Catalog curation is a recovery candidate: preserves imported source facts separately from manual price/enable/image/note choices, validates local-only images, and uses bounded bulk confirmation. Its old templates are not active UI.
- Auto Trader order and wallet bridge have useful isolated order/audit/idempotency foundations. They are not live-safe yet: new products default enabled, console safety is only a boolean, stock is not reserved, and sellback is missing.
- Nitrado scheduler is fake-provider/dry-run only. It has no network, FTP, XML write, upload, spawn, or force-restart capability. Keep it blocked until Server File Workspace, validated console exports, real provider preflight, and Owner-approved scopes exist.
- Map workspace is coordinate normalization/region math only. It has arbitrary default bounds, no real map profile, no source parsing, and no real map render. Reuse math only.
- Image rule: local `dxemb/web/static/items` is primary; DayZIDB is second fallback; record override is third; neutral classname/missing card is final fallback. Current oldbase uses DayZIDB first and must be corrected later.
- Vehicle rule: only six verified drivable land-vehicle families plus one verified drivable boat family. Wrecks, static objects, helicopters, PC/mod content, generic part lists, and generic cargo assumptions are blocked. Verify every family, required running part, optional part, special slot, variant, and image with Owner/lead-admin review before use.

## Trader Rules

- Auto Trader sells approved server-owned products only.
- Manual sellback appears on the same Trader product card but is separate: accept/disable toggle, payout, quantity limits, staff ticket, physical intake/destruction, verified one-time payout, and audit history.
- Sellback is never an automatic item removal and is never an Auto Trader purchase/refund.
- Shop open/closed is separate from manual-sellback staff coverage. Staff presence may show available; on-duty status requires explicit shift or opt-in auto-shift and ends offline/timeout/role loss.

## Nitrado Rules

- Never force restart.
- Owner-only: API/FTP credential setup, credential rotation/revocation, billing/payment boundary, and permission delegation.
- Nitrado commands are policy-wrapped actions, never raw command/API/FTP access.
- Owner/Admin scopes may include status, schedule, logs, file compare, export validation, preflight, stage approved output, delivery retry, and action-history read. Exact scopes are Owner-granted.
- No secret/payment value appears in Discord, logs, Change Explorer, or normal admin UI.

## Next Exact Work

Continue read-only audit:
1. Audit Operations Evidence workspace and remaining ticket/moderation recovery components for Change Explorer and manual sellback reuse.
2. Produce one final feature matrix: proven, recovery candidate, demo-only, quarantined, missing, deferred.
3. Inventory local image/CDN inputs once supplied; establish Map Profile with official fallback image plus calibrated tile source.
4. Only after audit closeout, define the first narrow implementation slice: Server File Workspace source snapshot/import/review using oldbase visual patterns only.

## Do Not Do Yet

- Do not delete/reset branches, local files, Docker resources, Neon projects, tables, data, or old UI variants.
- Do not apply migrations or wire Neon.
- Do not connect to Nitrado, FTP, API, billing, or upload paths.
- Do not invoke Copilot agents.
- Do not rename DXEMB to Zed420.
- Do not implement player market, games, live delivery, or real auth before the Server Editor foundation is proven.
