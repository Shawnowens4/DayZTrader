-- =============================================================
-- Slice C: Local-only ticket foundation (no guild writes)
-- Additive schema for ticket lifecycle + immutable audit events.
-- =============================================================

CREATE TABLE IF NOT EXISTS support_ticket (
    id                  BIGSERIAL           PRIMARY KEY,
    external_ref        TEXT                NOT NULL UNIQUE,
    requester_discord_id TEXT               NOT NULL,
    assignee_discord_id TEXT,
    subject             TEXT                NOT NULL,
    details             TEXT,
    status              TEXT                NOT NULL DEFAULT 'OPEN'
                            CHECK (status IN (
                                'OPEN',
                                'ASSIGNED',
                                'CLOSED'
                            )),
    opened_at           TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    closed_at           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_support_ticket_requester_status
    ON support_ticket (requester_discord_id, status);

CREATE INDEX IF NOT EXISTS idx_support_ticket_assignee_status
    ON support_ticket (assignee_discord_id, status);

DROP TRIGGER IF EXISTS trg_support_ticket_updated_at ON support_ticket;
CREATE TRIGGER trg_support_ticket_updated_at
    BEFORE UPDATE ON support_ticket
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS support_ticket_event (
    id                  BIGSERIAL           PRIMARY KEY,
    ticket_id           BIGINT              NOT NULL
                            REFERENCES support_ticket (id)
                            ON DELETE RESTRICT
                            ON UPDATE CASCADE,
    event_type          TEXT                NOT NULL
                            CHECK (event_type IN (
                                'OPENED',
                                'ASSIGNED',
                                'CLOSED',
                                'REOPENED'
                            )),
    actor_discord_id    TEXT                NOT NULL,
    note                TEXT,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_support_ticket_event_ticket_id
    ON support_ticket_event (ticket_id, created_at DESC);


CREATE OR REPLACE FUNCTION dxemb_support_ticket_event_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'support_ticket_event is immutable; updates/deletes are not allowed';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_support_ticket_event_no_update ON support_ticket_event;
CREATE TRIGGER trg_support_ticket_event_no_update
    BEFORE UPDATE ON support_ticket_event
    FOR EACH ROW EXECUTE FUNCTION dxemb_support_ticket_event_immutable();

DROP TRIGGER IF EXISTS trg_support_ticket_event_no_delete ON support_ticket_event;
CREATE TRIGGER trg_support_ticket_event_no_delete
    BEFORE DELETE ON support_ticket_event
    FOR EACH ROW EXECUTE FUNCTION dxemb_support_ticket_event_immutable();
