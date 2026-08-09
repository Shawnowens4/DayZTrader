-- =============================================================
-- Slice 3: Wallet + Ledger Foundation (additive)
-- Adds wallet_account and wallet_ledger without modifying legacy tables.
-- =============================================================

CREATE TABLE IF NOT EXISTS wallet_account (
    id                  BIGSERIAL           PRIMARY KEY,
    discord_user_id     TEXT                NOT NULL UNIQUE
                            REFERENCES player (discord_id)
                            ON DELETE RESTRICT
                            ON UPDATE CASCADE,
    balance             BIGINT              NOT NULL DEFAULT 0
                            CHECK (balance >= 0),
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wallet_account_discord_user_id
    ON wallet_account (discord_user_id);

DROP TRIGGER IF EXISTS trg_wallet_account_updated_at ON wallet_account;
CREATE TRIGGER trg_wallet_account_updated_at
    BEFORE UPDATE ON wallet_account
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS wallet_ledger (
    id                  BIGSERIAL           PRIMARY KEY,
    discord_user_id     TEXT                NOT NULL
                            REFERENCES player (discord_id)
                            ON DELETE RESTRICT
                            ON UPDATE CASCADE,
    entry_type          TEXT                NOT NULL
                            CHECK (entry_type IN (
                                'CREDIT',
                                'DEBIT',
                                'ADJUSTMENT',
                                'REFUND',
                                'HOLD',
                                'RELEASE'
                            )),
    amount              BIGINT              NOT NULL CHECK (amount > 0),
    signed_amount       BIGINT              NOT NULL CHECK (signed_amount <> 0),
    balance_before      BIGINT              NOT NULL CHECK (balance_before >= 0),
    balance_after       BIGINT              NOT NULL CHECK (balance_after >= 0),
    reference_type      TEXT                NOT NULL,
    reference_id        TEXT                NOT NULL,
    reason_code         TEXT,
    reason_text         TEXT,
    actor_discord_id    TEXT,
    metadata            JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_wallet_ledger_reference
        UNIQUE (discord_user_id, reference_type, reference_id)
);

CREATE INDEX IF NOT EXISTS idx_wallet_ledger_user_created_at
    ON wallet_ledger (discord_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wallet_ledger_reference
    ON wallet_ledger (reference_type, reference_id);


CREATE OR REPLACE FUNCTION dxemb_wallet_ledger_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'wallet_ledger is immutable; updates/deletes are not allowed';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_wallet_ledger_no_update ON wallet_ledger;
CREATE TRIGGER trg_wallet_ledger_no_update
    BEFORE UPDATE ON wallet_ledger
    FOR EACH ROW EXECUTE FUNCTION dxemb_wallet_ledger_immutable();

DROP TRIGGER IF EXISTS trg_wallet_ledger_no_delete ON wallet_ledger;
CREATE TRIGGER trg_wallet_ledger_no_delete
    BEFORE DELETE ON wallet_ledger
    FOR EACH ROW EXECUTE FUNCTION dxemb_wallet_ledger_immutable();
