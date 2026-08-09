# Moderation + Community Recovery Plan (Slice 5, Design-Only)

Date: 2026-08-08  
Scope: Design-only inventory and safe integration plan.  
Implementation status: No moderation/community runtime restoration performed.

## 1. Recovery Objectives

- Recover moderation and community systems in controlled slices.
- Preserve architecture boundaries already established in PERM.
- Avoid direct archive copy and avoid Discord server-side configuration changes.

## 2. Read-Only Evidence Inventory

### Archive source: C:\DXEMB

Moderation/community candidate modules:
- `C:\DXEMB\discord_bot\src\cogs\moderation.py`
- `C:\DXEMB\discord_bot\src\cogs\user.py`
- `C:\DXEMB\core\services\moderation_service.py`
- `C:\DXEMB\core\services\user_service.py`
- `C:\DXEMB\core\services\audit_service.py`

Related cogs that may contain shared command/dependency patterns:
- `C:\DXEMB\discord_bot\src\cogs\admin.py`
- `C:\DXEMB\discord_bot\src\cogs\help.py`

### Duplicate generation evidence

`C:\DXEMB\discord_bot\src\cogs\moderation.py` includes multiple generated sections in one file:
- legacy prefix-command `Moderation` cog with `mod_warn`, `mod_kick`, `mod_ban`
- newer slash-command `ModerationCog` with marketplace/dispute moderation commands
- both `def setup(bot)` and `async def setup(bot)` patterns in the same module

This confirms the file must be split/adapted deliberately and cannot be copied directly.

### Archive tests present

Archive test files discovered:
- `C:\DXEMB\tests\test_discord_bot.py`
- `C:\DXEMB\tests\test_user_cog.py`
- `C:\DXEMB\tests\test_user_service.py`
- `C:\DXEMB\tests\test_admin_service_integration.py`
- `C:\DXEMB\tests\test_admin_views.py`
- plus marketplace/escrow/economy tests already used in earlier slices

Gap signal:
- No dedicated archive tests explicitly named for ticket workflows, onboarding flows, channel provisioning, or role automation.

### Archive dependency manifests

Observed dependency manifests:
- `C:\DXEMB\requirements.txt`
- `C:\DXEMB\discord_bot\requirements.txt`

Notable packages from archive context:
- `discord.py`, `flask`, `flask_sqlalchemy`, `flask_migrate`, `flask_login`
- `sqlalchemy`, `psycopg2-binary`, `redis`, `python-dotenv`, `pytest`

### ZIP source (dayz-console-trader-bot.zip)

Keyword-filtered zip inventory produced no direct moderation/onboarding/ticket module matches.
ZIP appears focused on trader/economy/admin tooling and is not the primary moderation/community source.

## 3. Safe Integration Plan (Design-Only)

### Phase A: Module decomposition (no behavior release)

- Create a new PERM moderation package with separated concerns:
  - command adapters (prefix/slash wrappers)
  - domain services
  - audit/event emitter interfaces
- Split archive `moderation.py` into coherent submodules before any command enablement.
- Keep all restored commands disabled behind feature flags by default.

### Phase B: Data/audit contracts

- Define moderation action audit table(s) and reason taxonomy.
- Add immutable action history entries for warn/kick/ban/suspend/remove/resolve.
- Add actor/target/context fields and correlation IDs for dispute links.

### Phase C: Community features sequencing

1. Staff logs and moderation action tracking (read-only publish).
2. Role/channel guardrails and dry-run checks (no live writes by default).
3. Onboarding/profile workflow restore with idempotent user-state transitions.
4. Ticket lifecycle model and internal tests before any guild integration.

### Phase D: Test-first enablement

Required tests before enabling each subsystem:
- unit tests for command permission gates and role checks
- service tests for moderation action transitions
- integration tests for audit persistence and rollback behavior
- negative tests proving no unintended guild mutation occurs in dry-run mode

## 4. Risk Register

- Duplicate-generation moderation code may hide contradictory behavior.
- Archive dependency drift (SQLAlchemy/Flask stack) may conflict with current PERM lightweight runtime.
- Missing explicit ticket/onboarding tests increase regression risk.

Mitigations:
- recover by slice with isolated tests and feature flags
- preserve current PERM runtime boundaries
- add test scaffolding before wiring live Discord interactions

## 5. Explicit Non-Goals in Slice 5

- No Discord guild/channel/role changes.
- No token, secret, or deployment setting changes.
- No runtime moderation feature release.
- No archive extraction or bulk-copy restoration.

## 6. Slice A-D Implementation Reconciliation (2026-08-08)

### Implemented in PERM (local-only)

- Moderation immutable audit contract:
  - `dxemb/db/migrations/003_moderation_audit_foundation.sql`
  - `dxemb/shared/moderation_audit_service.py`
  - tests: `tests/test_moderation_audit_service.py`
- Moderation command adapters (strict scope):
  - `dxemb/bot/cogs/moderation_local.py`
  - warn, local status query, dry-run preview only
  - tests: `tests/test_moderation_command_adapter.py`
- Ticket foundation:
  - `dxemb/db/migrations/004_ticket_foundation.sql`
  - `dxemb/shared/ticket_service.py`
  - tests: `tests/test_ticket_service.py`
- Profile/onboarding persistence + dry-run evaluator:
  - `dxemb/db/migrations/005_profile_onboarding_foundation.sql`
  - `dxemb/shared/profile_onboarding_service.py`
  - tests: `tests/test_profile_onboarding_service.py`

### Explicitly not implemented

- Kick/ban/timeout moderation actions
- Role/channel/permission/webhook/message mutations
- Marketplace moderation actions (`suspend listing`, `resolve dispute`)
- Live Discord guild operations
- Neon/Nitrado/external service writes

### Remaining moderation/community gaps

- Bot-level runtime integration for ticket commands/workflows
- Web/admin visibility for moderation and ticket audit data
- Feature-flag strategy for staged moderation rollout
- End-to-end bot command integration tests beyond adapter/service scope
