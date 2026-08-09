-- =============================================================
-- Slice A: Fake-Provider Delivery Scheduler Foundation (additive)
-- Local-only scheduler schema. No live provider/FTP/write actions.
-- Bound to Auto-Trader orders via trader_order FK only.
-- =============================================================

CREATE TABLE IF NOT EXISTS delivery_poll_run (
    id                          BIGSERIAL           PRIMARY KEY,
    run_kind                    TEXT                NOT NULL
                                    CHECK (run_kind IN ('status', 'schedule', 'file_inventory')),
    started_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    ended_at                    TIMESTAMPTZ,
    result                      TEXT                NOT NULL
                                    CHECK (result IN ('ok', 'partial', 'error')),
    error_code                  TEXT,
    summary_json                JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CHECK (ended_at IS NULL OR ended_at >= started_at)
);


CREATE TABLE IF NOT EXISTS restart_window_cache (
    id                          BIGSERIAL           PRIMARY KEY,
    source_ref                  TEXT                NOT NULL,
    window_start_at             TIMESTAMPTZ         NOT NULL,
    window_end_at               TIMESTAMPTZ         NOT NULL,
    confidence                  TEXT                NOT NULL
                                    CHECK (confidence IN ('high', 'medium', 'low')),
    observed_at                 TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    expires_at                  TIMESTAMPTZ         NOT NULL,
    is_conflicting              BOOLEAN             NOT NULL DEFAULT FALSE,
    stale_reason                TEXT,
    metadata                    JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CHECK (window_end_at > window_start_at),
    CHECK (expires_at >= observed_at)
);

CREATE INDEX IF NOT EXISTS idx_restart_window_cache_active
    ON restart_window_cache (is_conflicting, expires_at, window_start_at);

DROP TRIGGER IF EXISTS trg_restart_window_cache_updated_at ON restart_window_cache;
CREATE TRIGGER trg_restart_window_cache_updated_at
    BEFORE UPDATE ON restart_window_cache
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS trader_delivery_request (
    id                          BIGSERIAL           PRIMARY KEY,
    order_id                    BIGINT              NOT NULL UNIQUE
                                    REFERENCES trader_order (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    delivery_request_key        TEXT                NOT NULL UNIQUE,
    state                       TEXT                NOT NULL
                                    CHECK (state IN (
                                        'queued_for_delivery',
                                        'awaiting_restart_window',
                                        'prepare_pending',
                                        'eligible_to_write',
                                        'retry_later',
                                        'failed',
                                        'refund_eligible',
                                        'delivered',
                                        'cancelled'
                                    )),
    enqueue_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    blocked_reason              TEXT,
    correlation_id              TEXT,
    policy_snapshot             JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_by                  TEXT,
    updated_by                  TEXT,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trader_delivery_request_state
    ON trader_delivery_request (state, enqueue_at);

DROP TRIGGER IF EXISTS trg_trader_delivery_request_updated_at ON trader_delivery_request;
CREATE TRIGGER trg_trader_delivery_request_updated_at
    BEFORE UPDATE ON trader_delivery_request
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS trader_scheduler_event (
    id                          BIGSERIAL           PRIMARY KEY,
    trader_delivery_request_id  BIGINT              NOT NULL
                                    REFERENCES trader_delivery_request (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    order_id                    BIGINT              NOT NULL
                                    REFERENCES trader_order (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    event_type                  TEXT                NOT NULL,
    from_state                  TEXT,
    to_state                    TEXT,
    decision                    TEXT,
    reason_code                 TEXT,
    reason_text                 TEXT,
    actor_id                    TEXT,
    reference_id                TEXT,
    details                     JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_trader_scheduler_event_reference UNIQUE (trader_delivery_request_id, reference_id)
);

CREATE INDEX IF NOT EXISTS idx_trader_scheduler_event_order_time
    ON trader_scheduler_event (order_id, created_at DESC);


CREATE TABLE IF NOT EXISTS trader_spawn_artifact (
    id                          BIGSERIAL           PRIMARY KEY,
    order_id                    BIGINT              NOT NULL
                                    REFERENCES trader_order (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    artifact_key                TEXT                NOT NULL UNIQUE,
    artifact_type               TEXT                NOT NULL
                                    CHECK (artifact_type IN ('xml_staging_metadata', 'cargo_manifest_metadata', 'vehicle_manifest_metadata')),
    artifact_hash               TEXT                NOT NULL,
    schema_version              TEXT                NOT NULL,
    validation_result           TEXT                NOT NULL
                                    CHECK (validation_result IN ('passed', 'failed')),
    validation_summary          JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_trader_spawn_artifact_hash UNIQUE (order_id, artifact_hash)
);

CREATE INDEX IF NOT EXISTS idx_trader_spawn_artifact_order
    ON trader_spawn_artifact (order_id, created_at DESC);


CREATE TABLE IF NOT EXISTS trader_delivery_attempt (
    id                          BIGSERIAL           PRIMARY KEY,
    order_id                    BIGINT              NOT NULL
                                    REFERENCES trader_order (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    trader_delivery_request_id  BIGINT              NOT NULL
                                    REFERENCES trader_delivery_request (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    poll_run_id                 BIGINT
                                    REFERENCES delivery_poll_run (id)
                                    ON DELETE SET NULL
                                    ON UPDATE CASCADE,
    restart_window_cache_id     BIGINT
                                    REFERENCES restart_window_cache (id)
                                    ON DELETE SET NULL
                                    ON UPDATE CASCADE,
    write_key                   TEXT                NOT NULL UNIQUE,
    attempt_no                  INTEGER             NOT NULL CHECK (attempt_no > 0),
    decision                    TEXT                NOT NULL
                                    CHECK (decision IN ('hold', 'poll', 'prepare', 'eligible_to_write', 'retry_later', 'fail', 'refund_eligible')),
    decision_reason             TEXT,
    attempted_at                TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    duration_ms                 INTEGER             CHECK (duration_ms IS NULL OR duration_ms >= 0),
    provider_result             JSONB               NOT NULL DEFAULT '{}'::jsonb,
    checksum_before             TEXT,
    checksum_after              TEXT,

    CONSTRAINT uq_trader_delivery_attempt_seq UNIQUE (trader_delivery_request_id, attempt_no)
);

CREATE INDEX IF NOT EXISTS idx_trader_delivery_attempt_order
    ON trader_delivery_attempt (order_id, attempted_at DESC);


CREATE TABLE IF NOT EXISTS trader_delivery_alert (
    id                          BIGSERIAL           PRIMARY KEY,
    order_id                    BIGINT              NOT NULL
                                    REFERENCES trader_order (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    trader_delivery_request_id  BIGINT
                                    REFERENCES trader_delivery_request (id)
                                    ON DELETE SET NULL
                                    ON UPDATE CASCADE,
    severity                    TEXT                NOT NULL
                                    CHECK (severity IN ('warning', 'high', 'critical')),
    alert_code                  TEXT                NOT NULL,
    message_redacted            TEXT                NOT NULL,
    dedupe_key                  TEXT,
    metadata                    JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    acknowledged_at             TIMESTAMPTZ,
    acknowledged_by             TEXT,

    CONSTRAINT uq_trader_delivery_alert_dedupe UNIQUE (order_id, dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_trader_delivery_alert_open
    ON trader_delivery_alert (severity, acknowledged_at, created_at DESC);


CREATE TABLE IF NOT EXISTS trader_delivery_refund_link (
    id                          BIGSERIAL           PRIMARY KEY,
    order_id                    BIGINT              NOT NULL UNIQUE
                                    REFERENCES trader_order (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    refund_reference_id         TEXT                NOT NULL UNIQUE,
    wallet_ledger_id            BIGINT              NOT NULL
                                    REFERENCES wallet_ledger (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    linked_at                   TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    details                     JSONB               NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_trader_delivery_refund_link_time
    ON trader_delivery_refund_link (linked_at DESC);


CREATE OR REPLACE FUNCTION dxemb_scheduler_event_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'scheduler audit tables are immutable; updates/deletes are not allowed';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_delivery_poll_run_no_update ON delivery_poll_run;
CREATE TRIGGER trg_delivery_poll_run_no_update
    BEFORE UPDATE ON delivery_poll_run
    FOR EACH ROW EXECUTE FUNCTION dxemb_scheduler_event_immutable();

DROP TRIGGER IF EXISTS trg_delivery_poll_run_no_delete ON delivery_poll_run;
CREATE TRIGGER trg_delivery_poll_run_no_delete
    BEFORE DELETE ON delivery_poll_run
    FOR EACH ROW EXECUTE FUNCTION dxemb_scheduler_event_immutable();

DROP TRIGGER IF EXISTS trg_trader_scheduler_event_no_update ON trader_scheduler_event;
CREATE TRIGGER trg_trader_scheduler_event_no_update
    BEFORE UPDATE ON trader_scheduler_event
    FOR EACH ROW EXECUTE FUNCTION dxemb_scheduler_event_immutable();

DROP TRIGGER IF EXISTS trg_trader_scheduler_event_no_delete ON trader_scheduler_event;
CREATE TRIGGER trg_trader_scheduler_event_no_delete
    BEFORE DELETE ON trader_scheduler_event
    FOR EACH ROW EXECUTE FUNCTION dxemb_scheduler_event_immutable();

DROP TRIGGER IF EXISTS trg_trader_spawn_artifact_no_update ON trader_spawn_artifact;
CREATE TRIGGER trg_trader_spawn_artifact_no_update
    BEFORE UPDATE ON trader_spawn_artifact
    FOR EACH ROW EXECUTE FUNCTION dxemb_scheduler_event_immutable();

DROP TRIGGER IF EXISTS trg_trader_spawn_artifact_no_delete ON trader_spawn_artifact;
CREATE TRIGGER trg_trader_spawn_artifact_no_delete
    BEFORE DELETE ON trader_spawn_artifact
    FOR EACH ROW EXECUTE FUNCTION dxemb_scheduler_event_immutable();

DROP TRIGGER IF EXISTS trg_trader_delivery_attempt_no_update ON trader_delivery_attempt;
CREATE TRIGGER trg_trader_delivery_attempt_no_update
    BEFORE UPDATE ON trader_delivery_attempt
    FOR EACH ROW EXECUTE FUNCTION dxemb_scheduler_event_immutable();

DROP TRIGGER IF EXISTS trg_trader_delivery_attempt_no_delete ON trader_delivery_attempt;
CREATE TRIGGER trg_trader_delivery_attempt_no_delete
    BEFORE DELETE ON trader_delivery_attempt
    FOR EACH ROW EXECUTE FUNCTION dxemb_scheduler_event_immutable();

DROP TRIGGER IF EXISTS trg_trader_delivery_refund_link_no_update ON trader_delivery_refund_link;
CREATE TRIGGER trg_trader_delivery_refund_link_no_update
    BEFORE UPDATE ON trader_delivery_refund_link
    FOR EACH ROW EXECUTE FUNCTION dxemb_scheduler_event_immutable();

DROP TRIGGER IF EXISTS trg_trader_delivery_refund_link_no_delete ON trader_delivery_refund_link;
CREATE TRIGGER trg_trader_delivery_refund_link_no_delete
    BEFORE DELETE ON trader_delivery_refund_link
    FOR EACH ROW EXECUTE FUNCTION dxemb_scheduler_event_immutable();
