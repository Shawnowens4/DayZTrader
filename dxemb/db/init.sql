-- =============================================================
-- DXEMB Schema — Epic A1
-- EscrowTransaction table with state CHECK constraint,
-- auto-updated timestamps, and indexes.
-- Idempotent: safe to run multiple times.
-- Postgres-compatible. No custom ENUM types.
-- =============================================================

-- -----------------------------------------------------------------
-- EscrowTransaction
-- Tracks every player order through the Xbox DayZ trader lifecycle.
-- discord_user_id and item_classname are FK stubs — hard FKs added
-- in a later epic once the referenced tables exist.
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS escrow_transaction (
    id                  BIGSERIAL           PRIMARY KEY,

    -- FK stub: references players table (not yet created)
    discord_user_id     TEXT                NOT NULL,

    -- FK stub: references items table (not yet created)
    item_classname      TEXT                NOT NULL,

    quantity            INTEGER             NOT NULL DEFAULT 1
                            CHECK (quantity > 0),

    -- Trader lifecycle state
    state               TEXT                NOT NULL DEFAULT 'PENDING'
                            CHECK (state IN (
                                'PENDING',
                                'FUNDED',
                                'SPAWNED',
                                'COLLECTED',
                                'CANCELLED',
                                'REFUNDED',
                                'EXPIRED',
                                'DISPUTED'
                            )),

    -- Optional: admin who last touched this order
    handled_by          TEXT,

    -- Optional: free-text notes (admin remarks, cancellation reason, etc.)
    notes               TEXT,

    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------
-- Auto-update trigger: keeps updated_at current on every row change
-- -----------------------------------------------------------------
CREATE OR REPLACE FUNCTION dxemb_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_escrow_updated_at ON escrow_transaction;

CREATE TRIGGER trg_escrow_updated_at
    BEFORE UPDATE ON escrow_transaction
    FOR EACH ROW
    EXECUTE FUNCTION dxemb_set_updated_at();

-- -----------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_escrow_discord_user_id
    ON escrow_transaction (discord_user_id);

CREATE INDEX IF NOT EXISTS idx_escrow_state
    ON escrow_transaction (state);

CREATE INDEX IF NOT EXISTS idx_escrow_user_state
    ON escrow_transaction (discord_user_id, state);
