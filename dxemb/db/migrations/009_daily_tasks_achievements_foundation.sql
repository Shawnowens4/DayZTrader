-- =============================================================
-- Slice B: Daily Tasks + Achievements Foundation (additive)
-- Local-safe progression and one-time reward tracking.
-- =============================================================

CREATE TABLE IF NOT EXISTS task_definition (
    id                          BIGSERIAL           PRIMARY KEY,
    task_code                   TEXT                NOT NULL UNIQUE,
    display_name                TEXT                NOT NULL,
    description                 TEXT,
    target_count                INTEGER             NOT NULL CHECK (target_count > 0),
    reward_amount               BIGINT              NOT NULL DEFAULT 0 CHECK (reward_amount >= 0),
    reset_policy                TEXT                NOT NULL DEFAULT 'DAILY_UTC'
                                    CHECK (reset_policy IN ('DAILY_UTC')),
    is_enabled                  BOOLEAN             NOT NULL DEFAULT TRUE,
    created_by                  TEXT,
    updated_by                  TEXT,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_task_definition_updated_at ON task_definition;
CREATE TRIGGER trg_task_definition_updated_at
    BEFORE UPDATE ON task_definition
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS task_progress (
    id                          BIGSERIAL           PRIMARY KEY,
    discord_user_id             TEXT                NOT NULL
                                    REFERENCES player (discord_id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    task_id                     BIGINT              NOT NULL
                                    REFERENCES task_definition (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    cycle_date_utc              DATE                NOT NULL,
    progress_count              INTEGER             NOT NULL DEFAULT 0 CHECK (progress_count >= 0),
    completed_at                TIMESTAMPTZ,
    reward_granted              BOOLEAN             NOT NULL DEFAULT FALSE,
    reward_reference_id         TEXT,
    reward_ledger_id            BIGINT
                                    REFERENCES wallet_ledger (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    metadata                    JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_task_progress_cycle UNIQUE (discord_user_id, task_id, cycle_date_utc),
    CONSTRAINT uq_task_progress_reward_reference UNIQUE (reward_reference_id)
);

CREATE INDEX IF NOT EXISTS idx_task_progress_user_cycle
    ON task_progress (discord_user_id, cycle_date_utc DESC);

DROP TRIGGER IF EXISTS trg_task_progress_updated_at ON task_progress;
CREATE TRIGGER trg_task_progress_updated_at
    BEFORE UPDATE ON task_progress
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS achievement_definition (
    id                          BIGSERIAL           PRIMARY KEY,
    achievement_code            TEXT                NOT NULL UNIQUE,
    display_name                TEXT                NOT NULL,
    description                 TEXT,
    trigger_kind                TEXT                NOT NULL
                                    CHECK (trigger_kind IN ('MANUAL', 'TASK_COMPLETIONS', 'GAME_WINS')),
    target_value                INTEGER             NOT NULL DEFAULT 1 CHECK (target_value > 0),
    reward_amount               BIGINT              NOT NULL DEFAULT 0 CHECK (reward_amount >= 0),
    one_time                    BOOLEAN             NOT NULL DEFAULT TRUE,
    is_enabled                  BOOLEAN             NOT NULL DEFAULT TRUE,
    created_by                  TEXT,
    updated_by                  TEXT,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_achievement_definition_updated_at ON achievement_definition;
CREATE TRIGGER trg_achievement_definition_updated_at
    BEFORE UPDATE ON achievement_definition
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS achievement_unlock (
    id                          BIGSERIAL           PRIMARY KEY,
    discord_user_id             TEXT                NOT NULL
                                    REFERENCES player (discord_id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    achievement_id              BIGINT              NOT NULL
                                    REFERENCES achievement_definition (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    unlocked_at                 TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    reward_granted              BOOLEAN             NOT NULL DEFAULT FALSE,
    reward_reference_id         TEXT,
    reward_ledger_id            BIGINT
                                    REFERENCES wallet_ledger (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    metadata                    JSONB               NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT uq_achievement_unlock_once UNIQUE (discord_user_id, achievement_id),
    CONSTRAINT uq_achievement_unlock_reward_reference UNIQUE (reward_reference_id)
);

CREATE INDEX IF NOT EXISTS idx_achievement_unlock_user_time
    ON achievement_unlock (discord_user_id, unlocked_at DESC);
