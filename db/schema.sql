-- ============================================================
-- DayZ Trader Bot - Full Database Schema
-- ============================================================

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ------------------------------------------------------------
-- USERS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    discord_id    INTEGER PRIMARY KEY,
    username      TEXT NOT NULL,
    balance       INTEGER DEFAULT 1000,
    total_earned  INTEGER DEFAULT 0,
    total_spent   INTEGER DEFAULT 0,
    joined_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_daily    TIMESTAMP,
    is_banned     INTEGER DEFAULT 0
);

-- ------------------------------------------------------------
-- ECONOMY / TRANSACTIONS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id  INTEGER NOT NULL,
    amount      INTEGER NOT NULL,
    type        TEXT NOT NULL,
    reference   TEXT,
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES users(discord_id)
);

-- ------------------------------------------------------------
-- SHOP ITEMS & BUNDLES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shop_items (
    item_id          TEXT PRIMARY KEY,
    class_name       TEXT NOT NULL,
    display_name     TEXT NOT NULL,
    price            INTEGER NOT NULL,
    category         TEXT DEFAULT 'misc',
    is_bundle        INTEGER DEFAULT 0,
    bundle_data      TEXT,
    bundle_discount  INTEGER DEFAULT 0,
    stock            INTEGER DEFAULT -1,
    enabled          INTEGER DEFAULT 1,
    admin_only       INTEGER DEFAULT 0,
    image_url        TEXT,
    description      TEXT,
    created_by       INTEGER,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchases (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id    INTEGER NOT NULL,
    item_id       TEXT NOT NULL,
    quantity      INTEGER DEFAULT 1,
    total_cost    INTEGER NOT NULL,
    delivery_zone TEXT,
    status        TEXT DEFAULT 'queued',
    delivered_at  TIMESTAMP,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES users(discord_id),
    FOREIGN KEY (item_id) REFERENCES shop_items(item_id)
);

-- ------------------------------------------------------------
-- DELIVERY QUEUE
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delivery_queue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id   INTEGER,
    discord_id    INTEGER NOT NULL,
    item_class    TEXT NOT NULL,
    item_display  TEXT NOT NULL,
    quantity      INTEGER DEFAULT 1,
    delivery_zone TEXT NOT NULL,
    is_vehicle    INTEGER DEFAULT 0,
    fully_kitted  INTEGER DEFAULT 0,
    attachments   TEXT,
    status        TEXT DEFAULT 'pending',
    attempt_count INTEGER DEFAULT 0,
    lifetime_sec  INTEGER DEFAULT 7200,
    queued_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at  TIMESTAMP,
    revert_at     TIMESTAMP
);

-- ------------------------------------------------------------
-- PLAYER MARKETPLACE
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_listings (
    listing_id    TEXT PRIMARY KEY,
    seller_id     INTEGER NOT NULL,
    item_class    TEXT NOT NULL,
    item_display  TEXT NOT NULL,
    quantity      INTEGER DEFAULT 1,
    asking_price  INTEGER NOT NULL,
    status        TEXT DEFAULT 'pending',
    buyer_id      INTEGER,
    escrow_held   INTEGER DEFAULT 0,
    expires_at    TIMESTAMP,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (seller_id) REFERENCES users(discord_id)
);

CREATE TABLE IF NOT EXISTS market_disputes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id   TEXT NOT NULL,
    filed_by     INTEGER NOT NULL,
    reason       TEXT NOT NULL,
    resolved     INTEGER DEFAULT 0,
    resolved_by  INTEGER,
    resolution   TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (listing_id) REFERENCES market_listings(listing_id)
);

-- ------------------------------------------------------------
-- RAFFLE
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raffles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    week_number      INTEGER NOT NULL,
    vehicle          TEXT NOT NULL,
    vehicle_display  TEXT NOT NULL,
    entry_cost       INTEGER NOT NULL,
    max_entries      INTEGER DEFAULT 10,
    start_time       TIMESTAMP NOT NULL,
    end_time         TIMESTAMP NOT NULL,
    winner_id        INTEGER,
    winner_name      TEXT,
    status           TEXT NOT NULL DEFAULT 'open',
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raffle_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    raffle_id   INTEGER NOT NULL,
    discord_id  INTEGER NOT NULL,
    username    TEXT NOT NULL,
    num_entries INTEGER DEFAULT 1,
    entered_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raffle_id) REFERENCES raffles(id),
    FOREIGN KEY (discord_id) REFERENCES users(discord_id)
);

-- ------------------------------------------------------------
-- CASINO
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS casino_games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id  INTEGER NOT NULL,
    game_type   TEXT NOT NULL,
    bet_amount  INTEGER NOT NULL,
    winnings    INTEGER NOT NULL,
    result      TEXT NOT NULL,
    played_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES users(discord_id)
);

CREATE TABLE IF NOT EXISTS casino_stats (
    discord_id       INTEGER PRIMARY KEY,
    total_bets       INTEGER DEFAULT 0,
    total_wagered    INTEGER DEFAULT 0,
    total_winnings   INTEGER DEFAULT 0,
    games_played     INTEGER DEFAULT 0,
    favorite_game    TEXT,
    biggest_win      INTEGER DEFAULT 0,
    last_played      TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES users(discord_id)
);

-- ------------------------------------------------------------
-- AUDIT LOG
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_type  TEXT NOT NULL,
    actor_id    INTEGER,
    target_id   INTEGER,
    item_ref    TEXT,
    amount      INTEGER,
    notes       TEXT,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- DELIVERY ZONES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delivery_zones (
    zone_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    display     TEXT NOT NULL,
    coord_x     REAL NOT NULL,
    coord_z     REAL NOT NULL,
    map_lat     REAL,
    map_lng     REAL,
    vehicle_ok  INTEGER DEFAULT 1,
    item_ok     INTEGER DEFAULT 1,
    enabled     INTEGER DEFAULT 1
);

INSERT OR IGNORE INTO delivery_zones VALUES
    ('nwaf',       'NWAF',      'Northwest Airfield',  4500.0,  11000.0, 65.2, 35.1, 1, 1, 1),
    ('neaf',       'NEAF',      'Northeast Airfield',  11500.0, 12500.0, 67.8, 74.2, 1, 1, 1),
    ('balota',     'Balota',    'Balota Airfield',     2600.0,  2400.0,  24.1, 26.3, 1, 1, 1),
    ('berezino',   'Berezino',  'Berezino',            12900.0, 7600.0,  52.4, 80.1, 0, 1, 1),
    ('electro',    'Electro',   'Elektrozavodsk',      11000.0, 2400.0,  24.5, 70.3, 0, 1, 1),
    ('cherno',     'Cherno',    'Chernogorsk',         7200.0,  2200.0,  23.0, 48.2, 0, 1, 1),
    ('vybor',      'Vybor',     'Vybor',               3700.0,  9200.0,  58.0, 31.5, 1, 1, 1),
    ('tisy',       'Tisy',      'Tisy Military Base',  1100.0,  13800.0, 72.1, 18.4, 1, 1, 1);

-- ------------------------------------------------------------
-- INDEXES
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_transactions_user     ON transactions(discord_id);
CREATE INDEX IF NOT EXISTS idx_purchases_user        ON purchases(discord_id);
CREATE INDEX IF NOT EXISTS idx_purchases_status      ON purchases(status);
CREATE INDEX IF NOT EXISTS idx_delivery_status       ON delivery_queue(status);
CREATE INDEX IF NOT EXISTS idx_market_status         ON market_listings(status);
CREATE INDEX IF NOT EXISTS idx_market_seller         ON market_listings(seller_id);
CREATE INDEX IF NOT EXISTS idx_raffle_week           ON raffles(week_number);
CREATE INDEX IF NOT EXISTS idx_raffle_entries_user   ON raffle_entries(discord_id);
CREATE INDEX IF NOT EXISTS idx_casino_games_user     ON casino_games(discord_id);
CREATE INDEX IF NOT EXISTS idx_audit_type            ON audit_log(trade_type);
