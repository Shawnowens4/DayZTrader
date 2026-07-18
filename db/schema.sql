-- DayZ Console Trader Bot - Full Database Schema
-- SQLite via aiosqlite

PRAGMA foreign_keys = ON;

-- ==================== USERS ====================
CREATE TABLE IF NOT EXISTS users (
    discord_id   INTEGER PRIMARY KEY,
    username     TEXT NOT NULL,
    balance      INTEGER DEFAULT 1000,
    total_earned INTEGER DEFAULT 0,
    total_spent  INTEGER DEFAULT 0,
    joined_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== ECONOMY ====================
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id  INTEGER NOT NULL,
    amount      INTEGER NOT NULL,
    type        TEXT NOT NULL, -- purchase, sale, reward, casino, raffle, admin_adjust
    reference   TEXT,          -- item_id, listing_id, etc.
    notes       TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES users(discord_id)
);

-- ==================== SHOP ====================
CREATE TABLE IF NOT EXISTS shop_items (
    item_id          TEXT PRIMARY KEY,
    class_name       TEXT NOT NULL,
    display_name     TEXT NOT NULL,
    description      TEXT,
    price            INTEGER NOT NULL,
    category         TEXT NOT NULL,
    is_bundle        BOOLEAN DEFAULT 0,
    bundle_data      TEXT,    -- JSON: [{"class":"AKM","qty":1,"attachments":[]}]
    is_container     BOOLEAN DEFAULT 0,
    container_data   TEXT,    -- JSON: [{"class":"Rag","qty":5}] items inside
    stock            INTEGER DEFAULT -1,  -- -1 = unlimited
    enabled          BOOLEAN DEFAULT 1,
    admin_only       BOOLEAN DEFAULT 0,
    image_url        TEXT,
    created_by       INTEGER,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_shop_category ON shop_items(category);
CREATE INDEX idx_shop_enabled  ON shop_items(enabled);

-- ==================== PURCHASES ====================
CREATE TABLE IF NOT EXISTS purchases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id   INTEGER NOT NULL,
    item_id      TEXT NOT NULL,
    quantity     INTEGER DEFAULT 1,
    total_price  INTEGER NOT NULL,
    delivery_zone TEXT,
    status       TEXT DEFAULT 'queued',  -- queued, delivering, delivered, failed
    delivered_at TIMESTAMP,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES users(discord_id),
    FOREIGN KEY (item_id) REFERENCES shop_items(item_id)
);

-- ==================== DELIVERY QUEUE ====================
CREATE TABLE IF NOT EXISTS delivery_queue (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id   INTEGER NOT NULL,
    item_class    TEXT NOT NULL,
    delivery_zone TEXT NOT NULL,
    fully_kitted  BOOLEAN DEFAULT 1,
    status        TEXT DEFAULT 'pending',  -- pending, writing, written, spawned, reverted, failed
    original_nominal INTEGER,
    original_min     INTEGER,
    revert_at     TIMESTAMP,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (purchase_id) REFERENCES purchases(id)
);

-- ==================== PLAYER MARKET ====================
CREATE TABLE IF NOT EXISTS market_listings (
    listing_id   TEXT PRIMARY KEY,
    seller_id    INTEGER NOT NULL,
    item_class   TEXT NOT NULL,
    item_display TEXT NOT NULL,
    quantity     INTEGER DEFAULT 1,
    asking_price INTEGER NOT NULL,
    status       TEXT DEFAULT 'pending',  -- pending, escrowed, delivered, cancelled, disputed
    buyer_id     INTEGER,
    escrow_held  INTEGER DEFAULT 0,
    delivery_zone TEXT,
    expires_at   TIMESTAMP,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (seller_id) REFERENCES users(discord_id)
);

CREATE INDEX idx_market_status ON market_listings(status);
CREATE INDEX idx_market_seller ON market_listings(seller_id);

-- ==================== TRADE AUDIT LOG ====================
CREATE TABLE IF NOT EXISTS trade_audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_type  TEXT NOT NULL,  -- purchase, listing, escrow, refund, dispute, admin_adjust, delivery
    actor_id    INTEGER,
    target_id   INTEGER,
    item_ref    TEXT,
    amount      INTEGER,
    notes       TEXT,
    admin_id    INTEGER,  -- set if an admin performed or approved this action
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== CASINO ====================
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
    discord_id     INTEGER PRIMARY KEY,
    total_wagered  INTEGER DEFAULT 0,
    total_winnings INTEGER DEFAULT 0,
    games_played   INTEGER DEFAULT 0,
    biggest_win    INTEGER DEFAULT 0,
    favorite_game  TEXT,
    last_played    TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES users(discord_id)
);

-- ==================== RAFFLE ====================
CREATE TABLE IF NOT EXISTS raffles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    week_number     INTEGER NOT NULL,
    vehicle         TEXT NOT NULL,
    vehicle_display TEXT NOT NULL,
    entry_cost      INTEGER NOT NULL,
    start_time      TIMESTAMP NOT NULL,
    end_time        TIMESTAMP NOT NULL,
    winner_id       INTEGER,
    winner_name     TEXT,
    status          TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

CREATE INDEX idx_raffle_week         ON raffles(week_number);
CREATE INDEX idx_raffle_entries_user ON raffle_entries(discord_id);
