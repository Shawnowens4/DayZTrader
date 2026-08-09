-- =============================================================
-- Slice A: Auto-Trader Product + Trader Order Foundation (additive)
-- Admin/server-owned Auto-Trader domain; intentionally isolated from P2P.
-- =============================================================

CREATE TABLE IF NOT EXISTS auto_trader_product (
    id                          BIGSERIAL           PRIMARY KEY,
    product_code                TEXT                NOT NULL UNIQUE,
    product_type                TEXT                NOT NULL
                                    CHECK (product_type IN ('ITEM', 'KIT', 'VEHICLE')),
    item_classname              TEXT
                                    REFERENCES item (classname)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    kit_code                    TEXT,
    vehicle_code                TEXT,
    display_name                TEXT                NOT NULL,
    price                       BIGINT              NOT NULL CHECK (price > 0),
    is_enabled                  BOOLEAN             NOT NULL DEFAULT TRUE,
    is_sellable                 BOOLEAN             NOT NULL DEFAULT TRUE,
    stock_limit                 INTEGER             CHECK (stock_limit IS NULL OR stock_limit >= 0),
    stock_remaining             INTEGER             CHECK (stock_remaining IS NULL OR stock_remaining >= 0),
    console_safe                BOOLEAN             NOT NULL DEFAULT TRUE,
    console_metadata            JSONB               NOT NULL DEFAULT '{}'::jsonb,
    notes                       TEXT,
    created_by                  TEXT,
    updated_by                  TEXT,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CHECK (
        (product_type = 'ITEM' AND item_classname IS NOT NULL AND kit_code IS NULL AND vehicle_code IS NULL)
        OR (product_type = 'KIT' AND item_classname IS NULL AND kit_code IS NOT NULL AND vehicle_code IS NULL)
        OR (product_type = 'VEHICLE' AND item_classname IS NULL AND kit_code IS NULL AND vehicle_code IS NOT NULL)
    ),
    CHECK (
        stock_limit IS NULL
        OR stock_remaining IS NULL
        OR stock_remaining <= stock_limit
    )
);

CREATE INDEX IF NOT EXISTS idx_auto_trader_product_enabled
    ON auto_trader_product (is_enabled, is_sellable, product_type);

CREATE INDEX IF NOT EXISTS idx_auto_trader_product_item
    ON auto_trader_product (item_classname)
    WHERE item_classname IS NOT NULL;

DROP TRIGGER IF EXISTS trg_auto_trader_product_updated_at ON auto_trader_product;
CREATE TRIGGER trg_auto_trader_product_updated_at
    BEFORE UPDATE ON auto_trader_product
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS trader_order (
    id                          BIGSERIAL           PRIMARY KEY,
    order_reference             TEXT                NOT NULL UNIQUE,
    buyer_discord_id            TEXT                NOT NULL
                                    REFERENCES player (discord_id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    product_id                  BIGINT              NOT NULL
                                    REFERENCES auto_trader_product (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    quantity                    INTEGER             NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price                  BIGINT              NOT NULL CHECK (unit_price > 0),
    total_price                 BIGINT              NOT NULL CHECK (total_price > 0),
    state                       TEXT                NOT NULL
                                    CHECK (state IN (
                                        'draft',
                                        'pending_payment',
                                        'paid',
                                        'queued_for_delivery',
                                        'awaiting_restart_window',
                                        'delivery_written',
                                        'delivered',
                                        'failed',
                                        'refunded',
                                        'cancelled'
                                    )),
    payment_reference_id        TEXT,
    refund_reference_id         TEXT,
    failure_reason              TEXT,
    cancellation_reason         TEXT,
    delivery_metadata           JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_by                  TEXT,
    updated_by                  TEXT,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    closed_at                   TIMESTAMPTZ,

    CHECK (total_price = unit_price * quantity)
);

CREATE INDEX IF NOT EXISTS idx_trader_order_buyer_state
    ON trader_order (buyer_discord_id, state);

CREATE INDEX IF NOT EXISTS idx_trader_order_product_state
    ON trader_order (product_id, state);

DROP TRIGGER IF EXISTS trg_trader_order_updated_at ON trader_order;
CREATE TRIGGER trg_trader_order_updated_at
    BEFORE UPDATE ON trader_order
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS trader_order_event (
    id                          BIGSERIAL           PRIMARY KEY,
    trader_order_id             BIGINT              NOT NULL
                                    REFERENCES trader_order (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    event_type                  TEXT                NOT NULL,
    from_state                  TEXT,
    to_state                    TEXT,
    actor_discord_id            TEXT,
    reason_code                 TEXT,
    reason_text                 TEXT,
    reference_id                TEXT,
    details                     JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_trader_order_event_reference UNIQUE (trader_order_id, reference_id)
);

CREATE INDEX IF NOT EXISTS idx_trader_order_event_order_time
    ON trader_order_event (trader_order_id, created_at DESC);


CREATE OR REPLACE FUNCTION dxemb_trader_order_event_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'trader_order_event is immutable; updates/deletes are not allowed';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_trader_order_event_no_update ON trader_order_event;
CREATE TRIGGER trg_trader_order_event_no_update
    BEFORE UPDATE ON trader_order_event
    FOR EACH ROW EXECUTE FUNCTION dxemb_trader_order_event_immutable();

DROP TRIGGER IF EXISTS trg_trader_order_event_no_delete ON trader_order_event;
CREATE TRIGGER trg_trader_order_event_no_delete
    BEFORE DELETE ON trader_order_event
    FOR EACH ROW EXECUTE FUNCTION dxemb_trader_order_event_immutable();
