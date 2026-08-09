# Nitrado Delivery Scheduler Design (Design-Only)

Date: 2026-08-08
Scope: Design-only contract for a future controlled delivery boundary between Auto-Trader orders and DayZ server artifacts.
Status: Design approved for planning; runtime integration not implemented.

## 0. Non-Goals and Guardrails

- No runtime Nitrado API or FTP/SFTP integration is implemented in this sprint.
- No scheduler process is started.
- No DayZ XML/spawn files are written.
- No restart is requested, scheduled, or triggered.
- No credentials, hostnames, provider URLs, or secret values are documented.
- Player Market + Escrow is explicitly out of scope for this delivery path.

Reference candidates (read-only, no copy):
- C:/DXEMB/REPO CLONE/DayZTrader/dayz-console-trader-bot/dayz-console-trader-bot/bot/services/nitrado_client.py
- C:/DXEMB/REPO CLONE/DayZTrader/dayz-console-trader-bot/dayz-console-trader-bot/bot/services/ftp_client.py
- C:/DXEMB/REPO CLONE/DayZTrader/dayz-console-trader-bot/dayz-console-trader-bot/bot/services/xml_generator.py
- dayz-console-trader-bot.zip: dayz-console-trader-bot/bot/services/nitrado_client.py
- dayz-console-trader-bot.zip: dayz-console-trader-bot/bot/services/ftp_client.py
- dayz-console-trader-bot.zip: dayz-console-trader-bot/bot/services/xml_generator.py

## 1. Order-to-Delivery Boundary

### 1.1 Auto-Trader states eligible for scheduling

Only Auto-Trader `trader_order` rows may enter scheduling, and only after successful payment path.

Entry states:
- paid
- queued_for_delivery

Scheduling progression states:
- queued_for_delivery -> awaiting_restart_window -> delivery_written -> delivered

Failure/terminal handling:
- queued_for_delivery/awaiting_restart_window/delivery_written -> failed
- failed/cancelled -> refunded (through wallet-bridge refund contract)

### 1.2 Explicitly prohibited sources

The scheduler must reject anything that is not an Auto-Trader order.

Prohibited from scheduler intake:
- Any `player_listing` state (`DRAFT`, `ACTIVE`, `RESERVED`, `COMPLETED`, `CANCELLED`, `EXPIRED`, `DISPUTED`)
- Any `market_escrow` state (`PENDING_HOLD`, `HELD`, `RELEASED`, `CANCELLED`, `REFUNDED`, `DISPUTED`, `EXPIRED`)

Rule:
- No read/write side effects to P2P lifecycle tables from scheduler logic.

### 1.3 Correlation and idempotency IDs

A single correlation chain is required end-to-end:
- order_reference (existing)
- delivery_request_id (new logical request key)
- spawn_artifact_id (new immutable artifact key)
- write_attempt_id (new per-attempt key)
- refund_reference_id (existing wallet ledger reference)

Idempotency keys:
- delivery_request_key = ORDER:{order_id}:DELIVERY
- artifact_key = ORDER:{order_id}:ARTIFACT:{artifact_hash}
- write_key = ORDER:{order_id}:WINDOW:{restart_window_id}:ATTEMPT:{n}
- refund_key = AUTO_TRADER_REFUND:{order_id}

Each key must be unique in its own table scope and replay-safe.

## 2. Future Data Model Proposal (No SQL in this sprint)

### 2.1 Proposed additive tables

1. server_connection_profile_ref
- Purpose: reference to secret-managed connection/profile identifiers (no secrets stored).
- Fields: id, profile_name, provider_kind, secret_ref, is_enabled, created_at, updated_at.

2. scheduler_poll_run
- Purpose: immutable record of each poll cycle.
- Fields: id, started_at, ended_at, run_kind (status|schedule|file_inventory), result, error_code, summary_json.

3. restart_window_cache
- Purpose: cached restart windows from provider observations.
- Fields: id, source_ref, window_start_at, window_end_at, confidence, observed_at, expires_at, is_conflicting.

4. trader_delivery_request
- Purpose: one scheduling request per eligible trader order.
- Fields: id, order_id, delivery_request_key, state, enqueue_at, blocked_reason, correlation_id, created_at, updated_at.

5. trader_spawn_artifact
- Purpose: immutable generated payload metadata before any upload/write.
- Fields: id, order_id, artifact_key, artifact_type, artifact_hash, schema_version, validation_result, created_at.

6. trader_delivery_write_attempt
- Purpose: each attempted write cycle and decision.
- Fields: id, order_id, write_key, restart_window_id, decision, decision_reason, attempted_at, duration_ms, provider_result, checksum_before, checksum_after.

7. trader_delivery_outcome
- Purpose: authoritative terminal delivery outcome.
- Fields: id, order_id, final_state, outcome_reason, terminal_at, delivered_at, refund_eligible_at.

8. trader_delivery_alert
- Purpose: operator-facing alerts/escalations.
- Fields: id, order_id, severity, alert_code, message_redacted, created_at, acknowledged_at, acknowledged_by.

9. trader_delivery_refund_link
- Purpose: one-way immutable mapping to wallet ledger refund reference.
- Fields: id, order_id, refund_reference_id, ledger_entry_id, linked_at.

### 2.2 Retention and audit rules

- Immutable tables: scheduler_poll_run, trader_spawn_artifact, trader_delivery_write_attempt, trader_delivery_alert, trader_delivery_refund_link.
- Mutable state tables: trader_delivery_request, restart_window_cache, trader_delivery_outcome.
- Minimum retention:
  - poll runs: 30 days
  - write attempts/outcomes/alerts/refunds: 180 days
  - artifact metadata and hash chain: 365 days
- Purge strategy:
  - logical archival first, hard purge only by explicit admin policy.
- Audit rule:
  - every state transition emits an immutable event row with actor/system and reason.

## 3. Scheduler Behavior

### 3.1 Poll cadence

- Status polling target: every 5 minutes.
- File inventory/pull backup target: every 30 minutes when enabled for the environment profile.

### 3.2 Restart cache behavior

- Every poll attempts to refresh restart windows into restart_window_cache.
- Cache expiry rule:
  - window expires at `expires_at` or immediately if conflict detected from newer observations.
- Confidence model:
  - high: two consecutive matching observations
  - medium: single source observation
  - low: stale or conflicting observations

### 3.3 Never-restart rule

- Scheduler must never call any restart endpoint or command.
- If restart is required but no trusted window exists, order remains blocked in `awaiting_restart_window`.

### 3.4 Write timing contract

- Only consider write-eligible when order is `queued_for_delivery` or `awaiting_restart_window`.
- Write target is approximately 10 minutes before a confirmed restart window start.
- Guard band:
  - earliest: 12 minutes before
  - latest: 5 minutes before
- Outside guard band: no write, keep waiting.

### 3.5 Unknown/stale/conflicting schedule handling

- Unknown schedule: hold order in `awaiting_restart_window`, create warning alert after threshold.
- Stale schedule: block writes and request refreshed poll cycle.
- Conflicting windows: mark conflict, raise alert, require admin hold/approve decision before writing.

## 4. Failure and Refund Rules

### 4.1 Hard write-prevention conditions

Do not write if any of the following is true:
- order not in write-eligible state
- product not console-safe
- artifact validation failed
- restart window missing/stale/conflicting
- profile disabled
- previous terminal outcome exists

### 4.2 Retry policy and backoff

- Retry only transient failures (timeout, temporary provider unavailable, checksum read mismatch before write lock).
- Backoff:
  - attempt 1 -> immediate
  - attempt 2 -> +2 min
  - attempt 3 -> +5 min
  - attempt 4 -> +10 min
- Max attempts per window: 4.
- After max attempts: mark failed for current window and wait next valid window unless policy escalates.

### 4.3 Alert thresholds

- warning: first blocked window due to stale/unknown schedule.
- high: two consecutive failed attempts in one window.
- critical: exhausted retries across two consecutive windows.

### 4.4 Refund eligibility transition

Auto-Trader refund eligibility starts when:
- order has terminal failure/cancel signal, and
- delivery outcome marks non-deliverable under policy, and
- no successful delivery_written->delivered completion exists.

Then:
- order transitions to failed (or remains cancelled), then bridge handles idempotent `refunded` transition.
- refund linkage is persisted in trader_delivery_refund_link.

### 4.5 P2P isolation rule

- Refund logic in this path may only affect Auto-Trader order debit references.
- Scheduler must never create/update P2P escrow refunds or listing states.

## 5. DayZ Console Artifact Rules

### 5.1 Console-safe domain

- Products limited to approved console-safe items, kits, vehicles.
- No PC/mod/Arma mechanics.
- No claim-code or virtual-delivery constructs.

### 5.2 Cargo semantics

- Cargo fields limited to:
  - quantity
  - chance
  - damage
- No liquid-value semantics.

### 5.3 Validation and staging

Before any future write-capable slice:
- generate artifact in staging buffer
- validate XML well-formedness and schema constraints
- verify product references against allow-list
- compute SHA256 checksum
- record artifact metadata only (this sprint)

### 5.4 Atomic write strategy (future)

Planned strategy:
- pull current target file metadata/checksum
- upload candidate as temporary artifact
- verify remote checksum
- atomically replace target via rename/swap operation where supported
- keep rollback pointer to previous checksum/version

### 5.5 Overwrite avoidance

- Never overwrite unknown/newer server content without checksum precondition match.
- If checksum precondition fails, abort write and raise alert.

## 6. Security and Operations

- Store only credential references (secret_ref), never secret values.
- Require periodic secret rotation policy with audit events.
- Enforce provider timeout and rate-limit budgets with circuit-breaker behavior.
- Logs must redact identifiers that can expose access data.
- Provide manual controls:
  - hold
  - approve single-window write
  - cancel delivery request
- Dry-run/sandbox mode is mandatory before enabling any real writes.

## 7. Test Plan (Future Implementation Validation)

### 7.1 Unit/service test areas

- order-state gate checks for scheduler intake
- polling decision logic for 5m/30m run kinds
- restart-window selection and conflict handling
- write-decision guard band (10-minute rule)
- retry/backoff and terminal escalation
- refund eligibility gating and idempotent refund link creation
- strict P2P non-interference assertions

### 7.2 Test doubles strategy

- fake clock for deterministic window math
- fake provider adapter for status/schedule responses
- fake FTP adapter for upload/checksum/rename outcomes
- in-memory alert sink for escalation assertions

### 7.3 Integration boundary tests (no real Nitrado)

- disposable DB integration tests validating event chain and state progression
- adapter contract tests for provider/FTP interfaces with deterministic fixtures
- checksum mismatch and stale-window chaos tests

### 7.4 Acceptance checklist before test-server enablement

- all scheduler unit tests passing
- all integration boundary tests passing
- dry-run mode runbook executed with zero side effects
- manual hold/approve/cancel controls validated
- alert thresholds validated in simulated failure scenarios
- explicit owner approval captured for write-capable activation

## 8. Implementation Sequence (Future Additive Slices)

### Slice 1 (requires explicit owner approval)
- Add additive scheduler schema migrations for proposed delivery tables.
- Add domain models/services for delivery request lifecycle only.
- Add tests for state gates and idempotency.
- No provider/FTP integration yet.

### Slice 2
- Add provider abstraction interfaces and fake adapters.
- Implement poll-run coordinator with cached restart-window decisions.
- Add decision-engine tests for unknown/stale/conflicting windows.

### Slice 3
- Add artifact staging/validation/hash pipeline and immutable artifact records.
- Add checksum precondition logic and write-attempt record model.
- Keep dry-run mode only.

### Slice 4 (requires explicit owner approval)
- Add controlled write-capable adapter integration for a test server profile.
- Enable guarded upload/atomic-replace path behind manual approve controls.
- Add full alerting and refund-link orchestration under strict policy gates.

### Slice 5
- Add operations dashboards and audit review tooling for delivery outcomes.
- Add retention jobs and archival workflow.

## 9. Future File Areas (Planned)

Potential additions/changes in future implementation slices:
- dxemb/db/migrations/00x_nitrado_delivery_scheduler_foundation.sql
- dxemb/shared/nitrado_delivery_scheduler_service.py
- dxemb/shared/nitrado_provider_adapter.py
- dxemb/shared/dayz_artifact_staging_service.py
- dxemb/shared/delivery_alert_service.py
- tests/test_nitrado_delivery_scheduler_service.py
- tests/test_dayz_artifact_staging_service.py
- tests/test_nitrado_provider_adapter_contract.py

No code changes were made in those areas in this sprint.
