# Wallet/Ledger + Player Market/Escrow Recovery Design (Slice 1)

Date: 2026-08-08  
Scope: Design-only foundation for future additive implementation.  
Status: Draft validated for boundary and migration planning.

## 1. Domain Boundaries

### Auto-Trader (Out of Scope for this design implementation)
- Admin-owned server store.
- Uses dedicated TraderOrder/spawn queue delivery pipeline.
- May physically spawn only admin-approved products.
- Never reuses Player Market listing or escrow flows.

### Player Market + Escrow (In Scope)
- P2P listing and transaction lifecycle only.
- Listings are player-owned offers.
- Escrow holds/release/refund/dispute model tracks settlement.
- No seller-item spawning by this subsystem.
- Completion requires physical pickup confirmation signals.

## 2. Wallet + Ledger Core Principles

### Wallet balance source of truth
- Source of truth: per-player wallet balance in a dedicated wallet table.
- Wallet row is mutable, but only via guarded service methods.
- Every wallet mutation requires a matching immutable ledger row.

### Immutable ledger entry model
- Ledger entries are append-only.
- No updates/deletes for monetary event rows.
- Corrections are represented by compensating entries.
- Each entry stores: player identifier, signed amount delta, pre/post balance, reason code, actor context, created timestamp.

### Idempotency/reference rules
- Every external/request-driven mutation includes a unique idempotency reference.
- Reference uniqueness is enforced in ledger scope (global or per player per operation class).
- Duplicate references return previously committed outcome without re-applying funds.

### Admin adjustments and audit requirements
- Admin changes must include:
  - actor identifier
  - reason code
  - free-text rationale
  - reference token
- Adjustment operations require ledger event typing (credit/debit/correction).
- Audit queries are chronological by player and globally by actor/action type.

## 3. Player Listing + Escrow Lifecycle

### Listing lifecycle (planned states)
- DRAFT -> ACTIVE -> RESERVED -> COMPLETED
- Alternate terminal states: CANCELLED, EXPIRED
- Listing must always point to seller and listing metadata; never imply server-created inventory.

### Escrow lifecycle (planned states)
- PENDING_HOLD -> HELD -> RELEASED
- Alternate terminal states: CANCELLED, REFUNDED, DISPUTED, EXPIRED
- State transitions must be explicit and audited with actor, timestamp, and reason.

### Disputes, cancellation, refunds, payout/release
- Dispute flow freezes release path until decision.
- Cancellation before settlement triggers hold release/refund path.
- Refund creates inverse wallet movement through ledger-backed compensating entries.
- Release/payout requires successful hold state and policy checks.

### Physical pickup confirmation
- P2P completion requires confirmation artifacts and status fields.
- No runtime path may spawn seller-owned items or vehicles.
- Seller delivery is physical in-game handoff only.

## 4. Migration Strategy

### Migration order (planned)
1. Wallet table + ledger table + integrity constraints.
2. Listing table(s) and escrow extension table(s).
3. Transition/audit support indexes.
4. Read-model compatibility views (if needed).

### Rollback considerations
- Migrations are additive and forward-safe.
- Rollback for append-only ledger keeps audit records; disable feature flags rather than destructive table drops.
- Where reversible SQL is required, use migration framework down-scripts only for non-financial schema additions.

## 5. Service Contract Test Strategy

### Minimal harness introduced in Slice 1
- unittest-based harness with utilities for disposable test database creation.
- No runtime app behavior changed.

### Slice 2 and beyond
- Schema contract tests against isolated disposable DB only.
- Wallet service tests for atomic credit/debit, insufficient funds, idempotency, and immutable history.
- Market/escrow service tests for state transitions and boundary enforcement.

## 6. Explicit Non-Goals for Slice 1
- No bot command behavior changes.
- No web route behavior changes.
- No production schema changes.
- No external Discord/Nitrado operations.
