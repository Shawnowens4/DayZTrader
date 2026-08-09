-- =============================================================
-- Slice A: Moderation data contract + immutable action audit
-- Additive only. No legacy table changes.
-- =============================================================

CREATE TABLE IF NOT EXISTS moderation_action (
    id                  BIGSERIAL           PRIMARY KEY,
    action_type         TEXT                NOT NULL
                            CHECK (action_type IN (
                                'WARN',
                                'STATUS_QUERY',
                                'DRY_RUN_PREVIEW'
                            )),
    actor_discord_id    TEXT                NOT NULL,
    target_discord_id   TEXT                NOT NULL,
    reason              TEXT,
    metadata            JSONB               NOT NULL DEFAULT '{}'::jsonb,
    reference_id        TEXT                NOT NULL,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_moderation_action_reference
        UNIQUE (action_type, reference_id)
);

CREATE INDEX IF NOT EXISTS idx_moderation_action_target_created
    ON moderation_action (target_discord_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_moderation_action_actor_created
    ON moderation_action (actor_discord_id, created_at DESC);


CREATE OR REPLACE FUNCTION dxemb_moderation_action_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'moderation_action is immutable; updates/deletes are not allowed';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_moderation_action_no_update ON moderation_action;
CREATE TRIGGER trg_moderation_action_no_update
    BEFORE UPDATE ON moderation_action
    FOR EACH ROW EXECUTE FUNCTION dxemb_moderation_action_immutable();

DROP TRIGGER IF EXISTS trg_moderation_action_no_delete ON moderation_action;
CREATE TRIGGER trg_moderation_action_no_delete
    BEFORE DELETE ON moderation_action
    FOR EACH ROW EXECUTE FUNCTION dxemb_moderation_action_immutable();
