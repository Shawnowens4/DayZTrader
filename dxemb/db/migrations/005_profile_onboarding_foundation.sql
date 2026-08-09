-- =============================================================
-- Slice D: Profile/Onboarding persistence + dry-run evaluator
-- Additive schema only, no Discord side-effect behavior.
-- =============================================================

CREATE TABLE IF NOT EXISTS player_profile (
    id                  BIGSERIAL           PRIMARY KEY,
    discord_user_id     TEXT                NOT NULL UNIQUE,
    display_name        TEXT,
    timezone            TEXT,
    preferred_platform  TEXT                CHECK (preferred_platform IN ('XBOX', 'PLAYSTATION')),
    reputation_score    INTEGER             NOT NULL DEFAULT 0,
    metadata            JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_player_profile_updated_at ON player_profile;
CREATE TRIGGER trg_player_profile_updated_at
    BEFORE UPDATE ON player_profile
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS onboarding_session (
    id                  BIGSERIAL           PRIMARY KEY,
    discord_user_id     TEXT                NOT NULL UNIQUE,
    state               TEXT                NOT NULL DEFAULT 'PENDING'
                            CHECK (state IN (
                                'PENDING',
                                'STARTED',
                                'PROFILE_CAPTURED',
                                'READY_FOR_REVIEW',
                                'COMPLETED'
                            )),
    note                TEXT,
    updated_by          TEXT,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_onboarding_session_updated_at ON onboarding_session;
CREATE TRIGGER trg_onboarding_session_updated_at
    BEFORE UPDATE ON onboarding_session
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS onboarding_event (
    id                  BIGSERIAL           PRIMARY KEY,
    onboarding_id       BIGINT              NOT NULL
                            REFERENCES onboarding_session (id)
                            ON DELETE RESTRICT
                            ON UPDATE CASCADE,
    from_state          TEXT,
    to_state            TEXT                NOT NULL,
    actor_discord_id    TEXT                NOT NULL,
    note                TEXT,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_onboarding_event_onboarding_id
    ON onboarding_event (onboarding_id, created_at DESC);
