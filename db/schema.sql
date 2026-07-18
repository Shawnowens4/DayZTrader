-- =============================================
-- DayZ Trader Bot - Full Database Schema
-- =============================================

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Users
CREATE TABLE IF NOT EXISTS users (
    discord_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    balance INTEGER DEFAULT 1000,
    total_earned INTEGER DEFAULT 0,
    total_spent INTEGER DEFAULT 0,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Shop Items
CREATE TABLE IF NOT EXISTS shop_items (
    item_id TEXT PRIMARY KEY,
    class_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    price INTEGER NOT NULL,
    category TEXT DEFAULT 'misc',
    is_bundle BOOLEAN DEFAULT 0,
    bundle_data TEXT,
    bundle_discount_pct INTEGER DEFAULT 0,
    stock INTEGER DEFAULT -1,
    enabled BOOLEAN DEFAULT 1,
    admin_only BOOLEAN DEFAULT 0,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Shop Purchases
CREATE TABLE IF NOT EXISTS shop_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    quantity INTEGER DEFAULT 1,
    total_cost INTEGER NOT NULL,
    delivered BOOLEAN DEFAULT 0,
    delivered_by INTEGER,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES users(discord_id),
    FOREIGN KEY (item_id) REFERENCES shop_items(item_id)
);

-- Player Market Listings
CREATE TABLE IF NOT EXISTS market_listings (
    listing_id TEXT PRIMARY KEY,
    seller_id INTEGER NOT NULL,
    item_class TEXT NOT NULL,
    item_display TEXT NOT NULL,
    quantity INTEGER DEFAULT 1,
    asking_price INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    buyer_id INTEGER,
    escrow_held INTEGER DEFAULT 0,
    dispute_reason TEXT,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (seller_id) REFERENCES users(discord_id)
);

-- Trade Audit Log
CREATE TABLE IF NOT EXISTS trade_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_type TEXT NOT NULL,
    actor_id INTEGER,
    target_id INTEGER,
    item_ref TEXT,
    amount INTEGER,
    notes TEXT,
    admin_id INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Raffles
CREATE TABLE IF NOT EXISTS raffles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_number INTEGER NOT NULL,
    vehicle TEXT NOT NULL,
    vehicle_display TEXT NOT NULL,
    entry_cost INTEGER NOT NULL,
    max_entries_per_player INTEGER DEFAULT 10,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    winner_id INTEGER,
    winner_name TEXT,
    status TEXT DEFAULT 'inactive',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raffle_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raffle_id INTEGER NOT NULL,
    discord_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    num_entries INTEGER DEFAULT 1,
    entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raffle_id) REFERENCES raffles(id),
    FOREIGN KEY (discord_id) REFERENCES users(discord_id)
);

-- Casino Games
CREATE TABLE IF NOT EXISTS casino_games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id INTEGER NOT NULL,
    game_type TEXT NOT NULL,
    bet_amount INTEGER NOT NULL,
    winnings INTEGER NOT NULL,
    result TEXT NOT NULL,
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES users(discord_id)
);

CREATE TABLE IF NOT EXISTS casino_stats (
    discord_id INTEGER PRIMARY KEY,
    total_bets INTEGER DEFAULT 0,
    total_wagered INTEGER DEFAULT 0,
    total_winnings INTEGER DEFAULT 0,
    games_played INTEGER DEFAULT 0,
    favorite_game TEXT,
    last_played TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES users(discord_id)
);

-- Economy Transactions
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (discord_id) REFERENCES users(discord_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_shop_items_category ON shop_items(category);
CREATE INDEX IF NOT EXISTS idx_shop_items_enabled ON shop_items(enabled);
CREATE INDEX IF NOT EXISTS idx_market_listings_status ON market_listings(status);
CREATE INDEX IF NOT EXISTS idx_market_listings_seller ON market_listings(seller_id);
CREATE INDEX IF NOT EXISTS idx_raffle_entries_user ON raffle_entries(discord_id);
CREATE INDEX IF NOT EXISTS idx_casino_games_user ON casino_games(discord_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(discord_id);
