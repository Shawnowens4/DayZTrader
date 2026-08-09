-- =============================================================
-- Slice 4: Player Listing + Escrow Foundation (P2P only)
-- Additive schema for marketplace and escrow, explicitly no server spawning.
-- =============================================================

CREATE TABLE IF NOT EXISTS player_listing (
    id                          BIGSERIAL           PRIMARY KEY,
    seller_discord_id           TEXT                NOT NULL
                                    REFERENCES player (discord_id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    buyer_discord_id            TEXT
                                    REFERENCES player (discord_id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    listing_type                TEXT                NOT NULL
                                    CHECK (listing_type IN ('ITEM', 'VEHICLE')),
    item_classname              TEXT
                                    REFERENCES item (classname)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    vehicle_label               TEXT,
    vehicle_running             BOOLEAN             NOT NULL DEFAULT TRUE,
    quantity                    INTEGER             NOT NULL DEFAULT 1
                                    CHECK (quantity > 0),
    price                       BIGINT              NOT NULL
                                    CHECK (price > 0),
    delivery_mode               TEXT                NOT NULL DEFAULT 'P2P_PHYSICAL'
                                    CHECK (delivery_mode = 'P2P_PHYSICAL'),
    status                      TEXT                NOT NULL DEFAULT 'ACTIVE'
                                    CHECK (status IN (
                                        'DRAFT',
                                        'ACTIVE',
                                        'RESERVED',
                                        'COMPLETED',
                                        'CANCELLED',
                                        'EXPIRED',
                                        'DISPUTED'
                                    )),
    created_by                  TEXT,
    updated_by                  TEXT,
    notes                       TEXT,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    closed_at                   TIMESTAMPTZ,

    CHECK (listing_type <> 'VEHICLE' OR vehicle_running = TRUE),
    CHECK (listing_type <> 'ITEM' OR item_classname IS NOT NULL),
    CHECK (seller_discord_id IS DISTINCT FROM buyer_discord_id)
);

CREATE INDEX IF NOT EXISTS idx_player_listing_seller_status
    ON player_listing (seller_discord_id, status);

CREATE INDEX IF NOT EXISTS idx_player_listing_buyer_status
    ON player_listing (buyer_discord_id, status);

DROP TRIGGER IF EXISTS trg_player_listing_updated_at ON player_listing;
CREATE TRIGGER trg_player_listing_updated_at
    BEFORE UPDATE ON player_listing
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS market_escrow (
    id                          BIGSERIAL           PRIMARY KEY,
    listing_id                  BIGINT              NOT NULL
                                    REFERENCES player_listing (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    seller_discord_id           TEXT                NOT NULL
                                    REFERENCES player (discord_id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    buyer_discord_id            TEXT                NOT NULL
                                    REFERENCES player (discord_id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    amount                      BIGINT              NOT NULL CHECK (amount > 0),
    hold_reference_id           TEXT                NOT NULL UNIQUE,
    release_reference_id        TEXT                UNIQUE,
    refund_reference_id         TEXT                UNIQUE,
    status                      TEXT                NOT NULL DEFAULT 'PENDING_HOLD'
                                    CHECK (status IN (
                                        'PENDING_HOLD',
                                        'HELD',
                                        'RELEASED',
                                        'CANCELLED',
                                        'REFUNDED',
                                        'DISPUTED',
                                        'EXPIRED'
                                    )),
    pickup_confirmed_by_buyer   BOOLEAN             NOT NULL DEFAULT FALSE,
    pickup_confirmed_at         TIMESTAMPTZ,
    dispute_reason              TEXT,
    created_by                  TEXT,
    updated_by                  TEXT,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CHECK (seller_discord_id <> buyer_discord_id),
    CHECK (status <> 'RELEASED' OR pickup_confirmed_by_buyer = TRUE)
);

CREATE INDEX IF NOT EXISTS idx_market_escrow_listing
    ON market_escrow (listing_id);

CREATE INDEX IF NOT EXISTS idx_market_escrow_status
    ON market_escrow (status);

CREATE INDEX IF NOT EXISTS idx_market_escrow_buyer_status
    ON market_escrow (buyer_discord_id, status);

DROP TRIGGER IF EXISTS trg_market_escrow_updated_at ON market_escrow;
CREATE TRIGGER trg_market_escrow_updated_at
    BEFORE UPDATE ON market_escrow
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


CREATE TABLE IF NOT EXISTS market_escrow_event (
    id                          BIGSERIAL           PRIMARY KEY,
    escrow_id                   BIGINT              NOT NULL
                                    REFERENCES market_escrow (id)
                                    ON DELETE RESTRICT
                                    ON UPDATE CASCADE,
    event_type                  TEXT                NOT NULL,
    actor_discord_id            TEXT,
    details                     JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_escrow_event_escrow_id
    ON market_escrow_event (escrow_id, created_at DESC);
