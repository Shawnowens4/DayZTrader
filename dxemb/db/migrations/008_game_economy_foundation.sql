-- =============================================================
-- Slice A: Games Economy Foundation (additive)
-- Local-safe deterministic game audit and wallet-ledger linked records.
-- =============================================================

CREATE TABLE IF NOT EXISTS game_feature_flag (
    id                          BIGSERIAL           PRIMARY KEY,
    game_code                   TEXT                NOT NULL UNIQUE,
    is_enabled                  BOOLEAN             NOT NULL DEFAULT TRUE,
    allow_live_payout           BOOLEAN             NOT NULL DEFAULT FALSE,
    min_wager                   BIGINT              NOT NULL DEFAULT 1 CHECK (min_wager > 0),
    max_wager                   BIGINT              NOT NULL DEFAULT 5000 CHECK (max_wager >= min_wager),
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_game_feature_flag_updated_at ON game_feature_flag;
CREATE TRIGGER trg_game_feature_flag_updated_at
    BEFORE UPDATE ON game_feature_flag
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();

INSERT INTO game_feature_flag (game_code, is_enabled, allow_live_payout, min_wager, max_wager)
VALUES ('COIN_FLIP', TRUE, FALSE, 1, 5000)
ON CONFLICT (game_code) DO NOTHING;


CREATE TABLE IF NOT EXISTS game_session (
    id                          BIGSERIAL           PRIMARY KEY,
    session_reference           TEXT                NOT NULL UNIQUE,
    discord_user_id             TEXT                NOT NULL
                                    REFERENCES player (discord_id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    game_code                   TEXT                NOT NULL,
    feature_flag_id             BIGINT              NOT NULL
                                    REFERENCES game_feature_flag (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    idempotency_key             TEXT                NOT NULL,
    wager_amount                BIGINT              NOT NULL CHECK (wager_amount > 0),
    pick_value                  TEXT                NOT NULL,
    outcome_value               TEXT                NOT NULL,
    is_win                      BOOLEAN             NOT NULL,
    payout_multiplier           NUMERIC(10, 4)      NOT NULL CHECK (payout_multiplier >= 0),
    payout_amount               BIGINT              NOT NULL CHECK (payout_amount >= 0),
    server_seed                 TEXT                NOT NULL,
    server_seed_hash            TEXT                NOT NULL,
    rng_algorithm               TEXT                NOT NULL DEFAULT 'sha256_mod2',
    rng_value                   INTEGER             NOT NULL CHECK (rng_value IN (0, 1)),
    debit_reference_id          TEXT,
    payout_reference_id         TEXT,
    debit_ledger_id             BIGINT
                                    REFERENCES wallet_ledger (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    payout_ledger_id            BIGINT
                                    REFERENCES wallet_ledger (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    mode                        TEXT                NOT NULL
                                    CHECK (mode IN ('dry-run', 'wallet-settle')),
    metadata                    JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_game_session_user_idempotency UNIQUE (discord_user_id, game_code, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_game_session_user_created_at
    ON game_session (discord_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_game_session_game_created_at
    ON game_session (game_code, created_at DESC);


CREATE OR REPLACE FUNCTION dxemb_game_session_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'game_session is immutable; updates/deletes are not allowed';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_game_session_no_update ON game_session;
CREATE TRIGGER trg_game_session_no_update
    BEFORE UPDATE ON game_session
    FOR EACH ROW EXECUTE FUNCTION dxemb_game_session_immutable();

DROP TRIGGER IF EXISTS trg_game_session_no_delete ON game_session;
CREATE TRIGGER trg_game_session_no_delete
    BEFORE DELETE ON game_session
    FOR EACH ROW EXECUTE FUNCTION dxemb_game_session_immutable();
