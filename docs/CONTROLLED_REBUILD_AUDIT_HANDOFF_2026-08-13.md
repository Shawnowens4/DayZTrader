# Controlled Rebuild Audit Handoff — 2026-08-13

## Purpose

This handoff preserves the completed read-only audit and decisions before implementation. It is not authorization to change code, databases, Nitrado, server files, or credentials.

## Authoritative Rules

- `oldbase.html` is the only active UI/UX source. Use it as the visual/product blueprint; do not create another base shell or paste it wholesale over the app.
- Xbox/PlayStation console only. All server-facing data/export behavior is pinned to the matching current official Bohemia Central Economy source revision for the active map/mission.
- PC-only, mods, scripts, PBOs, Arma assumptions, generic compatibility, and guessed source facts are blocked.
- Preserve every recovery branch, file, database, local asset, Docker resource, and partial feature. Quarantine incompatible work; never delete/reset it during rebuild.
- No Copilot agents until credits return and the owner explicitly approves a narrow task.

## UI and Branch State

- Active branch: `feature/local-finish-ui-recovery`.
- Canonical oldbase checkpoint: `1f90a668` (`oldbase.html as canonical template starting point`).
- Quarantined UI conflict: `424322bb` changed `dashboard.html`; retain but do not build from it.
- Existing templates/pages are recovery evidence only. The oldbase visual flow is the UI source.

## Workspaces and Roles

### Workspaces

1. Server Editor: Owner/Admin — server source files, CE editors, Server Vehicle Builder, Event Pack Builder, map/log, review/export, later Nitrado.
2. Trader Control: Owner/Admin/Trader — products, sale/sellback settings, pricing, bundles, completed weapons, vehicle products, orders, shifts, tickets.
3. Discord Operations: Admin/Mod/Trader — bot-only role-appropriate functions.
4. Player Systems: later — Auto Trader purchase, P2P market/escrow, games, onboarding, tasks, notifications.

### Roles

- Owner: all access; credentials, billing boundary, delegation.
- Backup Superuser: lead-admin emergency/recovery capability, Owner-approved operational scopes, no billing by default.
- Admin: full Server Editor; Owner-granted Nitrado operational scopes.
- Trader: Mod capabilities plus Trader Control only.
- Mod: moderation/tickets/Change Explorer only.
- Player: player systems only.

## Server Editor Inventory

### Existing oldbase strengths

- CE XML browser intake for `types.xml`, `cfgspawnabletypes.xml`, `cfgeventspawns.xml`.
- Vehicle cards, variants, cargo picker, attachment/nesting/workbench patterns.
- DayZIDB mapping/fallback logic.
- Browser-side review/validation prototype.

### Existing oldbase limitations

- Hard-coded vehicle/parts/stats/compatibility and demo actions.
- No structured editor, source snapshot/version/diff, real XML generation, or Nitrado integration.
- Current export is browser preview/copy behavior, not server XML output.
- Current settings page is export-policy demo, not Nitrado/server settings.

### Required server tools

- Server File Workspace: original snapshot, draft, diff, source provenance, map/mission profile.
- Types Editor, Spawnable Types Editor, Events Editor, Event Spawns Editor.
- Map Workspace and Log Viewer.
- Server Vehicle Builder and Item/Cargo Builder.
- Event Pack Builder using official custom CE override/append behavior where supported.
- Review, validated console XML export, and later Nitrado preflight/staging.
- Change Explorer for Mod/Trader read-only staff explanations.

## Vehicle Rules

- Closed console vehicle catalog: six verified drivable land families plus one verified boat family.
- Exclude wrecks, static assets, helicopters, PC/mod content, and unverified family variants.
- Every family requires a verified profile: classname, variant/color, required running parts, optional installed parts, standard cargo, special cargo/external slots, image coverage, static/wreck exclusions, official revision, and Owner/lead-admin confirmation.
- M3S-like special external slots for logs/planks/metal sheets/barrels/crates remain separate from running parts and normal trunk cargo.

## Image Rules

1. Local curated `dxemb/web/static/items` assets.
2. DayZIDB mapped asset fallback.
3. Explicit record/admin image override.
4. Neutral missing image/classname card.

Track vehicle body, each valid color, each required/optional/special part, and status: Local / DayZIDB fallback / Override / Missing / Mismatch blocked.

Map design: official Bohemia image is pinned overview/fallback; a controlled calibrated XYZ tile source is preferred for interactive pan/zoom. A Map Profile stores the source revision, bounds, transform, orientation, and calibration. No marker is claimed accurate without verified source and calibration.

## Trader and Economy Rules

- Auto Trader is outbound only: approved server-owned items, bundles, completed weapons, and vehicle products.
- Product directions are separate: `auto trader sale enabled` and `manual sellback accepted`.
- Sellback uses ticket → physical in-game intake/destruction → Trader/Admin verification → one-time payout → close/audit. Never automatic item removal and never a refund.
- Shop state and staff coverage are separate. Use schedules/manual override plus Trader/Admin shifts; Discord presence alone means available, not confirmed handling.
- Economy support is advisory: configured CE supply plus actual trader ticket/order history. Do not claim live world quantity without reliable server evidence. Suggestions never auto-change price/limits.

## Recovery Candidates

- Types importer: safe local source intake; DTD/entity and malformed XML rejection; dry-run/apply; SHA/evidence provenance; curation preservation. Not a server XML editor.
- Catalog curation: local-only image validation, source/manual separation, review/enable states, bounded bulk confirmation. Old UI is quarantined.
- Auto Trader order service: isolated outbound order state/event/idempotency foundation. Missing real console validation, stock reservation, safe defaults, bundles/weapons/vehicle definitions, sellback.
- Wallet bridge: atomic debit/outbound paid order and idempotent refund foundation. Never use for sellback payout.
- Nitrado scheduler: fake-only/dry-run decision/audit boundary with no network/FTP/write/restart/spawn commands. Keep blocked until validated export and Owner-approved real provider design.
- Local auth: test helper only; browser role hints are not security. Replace with verified Discord identity and explicit scope system.
- Map math: reusable coordinate helpers only; no real map/source linkage yet.

## Resume Order

1. Continue audit of Operations Evidence and remaining ticket/moderation recovery work.
2. Produce final matrix: proven, reuse candidate, demo-only, quarantined, missing, deferred.
3. When supplied, inventory local `static/items` assets and CDN/tile configuration; create verified map profile.
4. Close audit with exact first implementation slice: Server File Workspace snapshot/import/review, using oldbase visuals only.
5. Do not touch Nitrado/live delivery/Neon/migrations until later explicit approval.
