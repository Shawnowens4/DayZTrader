-- =============================================================
-- Slice C: Mission/Bounty Foundation (additive)
-- Local-only, feature-flagged mission progress and claim ledger links.
-- =============================================================

CREATE TABLE IF NOT EXISTS mission_feature_flag (
    id                          BIGSERIAL           PRIMARY KEY,
    feature_code                TEXT                NOT NULL UNIQUE,
    is_enabled                  BOOLEAN             NOT NULL DEFAULT FALSE,
    allow_reward_settlement     BOOLEAN             NOT NULL DEFAULT FALSE,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_mission_feature_flag_updated_at ON mission_feature_flag;
CREATE TRIGGER trg_mission_feature_flag_updated_at
    BEFORE UPDATE ON mission_feature_flag
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();

INSERT INTO mission_feature_flag (feature_code, is_enabled, allow_reward_settlement)
VALUES ('MISSION_BOUNTY', FALSE, FALSE)
ON CONFLICT (feature_code) DO NOTHING;


CREATE TABLE IF NOT EXISTS mission_bounty (
    id                          BIGSERIAL           PRIMARY KEY,
    mission_code                TEXT                NOT NULL UNIQUE,
    title                       TEXT                NOT NULL,
    description                 TEXT,
    target_count                INTEGER             NOT NULL CHECK (target_count > 0),
    reward_amount               BIGINT              NOT NULL CHECK (reward_amount >= 0),
    starts_at                   TIMESTAMPTZ,
    expires_at                  TIMESTAMPTZ,
    state                       TEXT                NOT NULL
                                    CHECK (state IN ('DRAFT', 'ACTIVE', 'CANCELLED', 'EXPIRED', 'CLOSED')),
    moderation_state            TEXT                NOT NULL DEFAULT 'PENDING'
                                    CHECK (moderation_state IN ('PENDING', 'APPROVED', 'REJECTED')),
    created_by                  TEXT                NOT NULL,
    updated_by                  TEXT                NOT NULL,
    cancel_reason               TEXT,
    metadata                    JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CHECK (expires_at IS NULL OR starts_at IS NULL OR expires_at > starts_at)
);

DROP TRIGGER IF EXISTS trg_mission_bounty_updated_at ON mission_bounty;
CREATE TRIGGER trg_mission_bounty_updated_at
    BEFORE UPDATE ON mission_bounty
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();

CREATE INDEX IF NOT EXISTS idx_mission_bounty_state
    ON mission_bounty (state, created_at DESC);


CREATE TABLE IF NOT EXISTS mission_bounty_progress (
    id                          BIGSERIAL           PRIMARY KEY,
    mission_id                  BIGINT              NOT NULL
                                    REFERENCES mission_bounty (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    discord_user_id             TEXT                NOT NULL
                                    REFERENCES player (discord_id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    progress_count              INTEGER             NOT NULL DEFAULT 0 CHECK (progress_count >= 0),
    status                      TEXT                NOT NULL
                                    CHECK (status IN ('ENROLLED', 'ELIGIBLE', 'CLAIMED', 'CANCELLED', 'EXPIRED')),
    eligible_at                 TIMESTAMPTZ,
    claimed_at                  TIMESTAMPTZ,
    claim_reference_id          TEXT,
    reward_granted              BOOLEAN             NOT NULL DEFAULT FALSE,
    reward_ledger_id            BIGINT
                                    REFERENCES wallet_ledger (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    metadata                    JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_mission_user UNIQUE (mission_id, discord_user_id),
    CONSTRAINT uq_mission_claim_reference UNIQUE (claim_reference_id)
);

DROP TRIGGER IF EXISTS trg_mission_bounty_progress_updated_at ON mission_bounty_progress;
CREATE TRIGGER trg_mission_bounty_progress_updated_at
    BEFORE UPDATE ON mission_bounty_progress
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();

CREATE INDEX IF NOT EXISTS idx_mission_bounty_progress_user_status
    ON mission_bounty_progress (discord_user_id, status, updated_at DESC);
