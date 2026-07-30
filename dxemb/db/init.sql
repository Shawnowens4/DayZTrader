-- =============================================================
-- DXEMB Schema — Epic A1 + A2
-- Tables: player, item, escrow_transaction
-- Creation order: function → player → item → escrow_transaction
-- All FKs are now real constraints (tables exist in same file).
-- Idempotent: safe to run multiple times.
-- Postgres-compatible. No custom ENUM types.
-- =============================================================


-- =============================================================
-- Shared trigger function — MUST be defined before any trigger
-- that references it. CREATE OR REPLACE is idempotent.
-- =============================================================
CREATE OR REPLACE FUNCTION dxemb_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =============================================================
-- A2: player
-- One row per Discord user who has interacted with the trader.
-- discord_id is the authoritative Discord snowflake (string).
-- =============================================================
CREATE TABLE IF NOT EXISTS player (
    id                  BIGSERIAL           PRIMARY KEY,
    discord_id          TEXT                NOT NULL UNIQUE,
    username            TEXT,                          -- Discord display name, updated on activity
    is_banned           BOOLEAN             NOT NULL DEFAULT FALSE,
    ban_reason          TEXT,
    notes               TEXT,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_player_discord_id
    ON player (discord_id);

DROP TRIGGER IF EXISTS trg_player_updated_at ON player;
CREATE TRIGGER trg_player_updated_at
    BEFORE UPDATE ON player
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


-- =============================================================
-- A2: item
-- One row per DayZ classname that the trader knows about.
-- classname matches types.xml / DayZIDB exactly (case-sensitive).
-- =============================================================
CREATE TABLE IF NOT EXISTS item (
    id                  BIGSERIAL           PRIMARY KEY,
    classname           TEXT                NOT NULL UNIQUE,   -- e.g. AKM, M4A1_Black
    display_name        TEXT,                                  -- human label, e.g. "AKM Assault Rifle"
    category            TEXT,                                  -- e.g. Weapons, Clothing, Vehicles
    subcategory         TEXT,                                  -- e.g. Rifles, Jackets
    buy_price           INTEGER,                               -- currency units, NULL = not for sale
    sell_price          INTEGER,                               -- currency units, NULL = no sell
    is_enabled          BOOLEAN             NOT NULL DEFAULT TRUE,
    thumbnail_url       TEXT,                                  -- DayZIDB WebP path or CDN URL
    notes               TEXT,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_item_classname
    ON item (classname);

CREATE INDEX IF NOT EXISTS idx_item_category
    ON item (category);

CREATE INDEX IF NOT EXISTS idx_item_enabled
    ON item (is_enabled);

DROP TRIGGER IF EXISTS trg_item_updated_at ON item;
CREATE TRIGGER trg_item_updated_at
    BEFORE UPDATE ON item
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();


-- =============================================================
-- A1 (updated): escrow_transaction
-- FK stubs promoted to real FKs now that player and item exist.
-- =============================================================
CREATE TABLE IF NOT EXISTS escrow_transaction (
    id                  BIGSERIAL           PRIMARY KEY,

    -- Real FK to player.discord_id (TEXT match)
    discord_user_id     TEXT                NOT NULL
                            REFERENCES player (discord_id)
                            ON DELETE RESTRICT
                            ON UPDATE CASCADE,

    -- Real FK to item.classname (TEXT match)
    item_classname      TEXT                NOT NULL
                            REFERENCES item (classname)
                            ON DELETE RESTRICT
                            ON UPDATE CASCADE,

    quantity            INTEGER             NOT NULL DEFAULT 1
                            CHECK (quantity > 0),

    state               TEXT                NOT NULL DEFAULT 'PENDING'
                            CHECK (state IN (
                                'PENDING',
                                'FUNDED',
                                'SPAWNED',
                                'COLLECTED',
                                'CANCELLED',
                                'REFUNDED',
                                'EXPIRED',
                                'DISPUTED'
                            )),

    handled_by          TEXT,              -- Discord ID of admin who last acted
    notes               TEXT,

    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_escrow_discord_user_id
    ON escrow_transaction (discord_user_id);

CREATE INDEX IF NOT EXISTS idx_escrow_state
    ON escrow_transaction (state);

CREATE INDEX IF NOT EXISTS idx_escrow_user_state
    ON escrow_transaction (discord_user_id, state);

DROP TRIGGER IF EXISTS trg_escrow_updated_at ON escrow_transaction;
CREATE TRIGGER trg_escrow_updated_at
    BEFORE UPDATE ON escrow_transaction
    FOR EACH ROW EXECUTE FUNCTION dxemb_set_updated_at();
