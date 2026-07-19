-- ============================================================
-- Migration 002 — New Systems
-- Phase 1 scaffold. 13 new tables.
-- ALL statements use CREATE TABLE IF NOT EXISTS.
-- Safe to run against a populated DB: adds tables only,
-- touches no existing tables or rows.
--
-- Run manually: python db/migrate.py
-- Do NOT run in production until Phase 2 dev testing passes.
--
-- Base tables before:  13
-- New tables added:    13
-- Total after:         26
-- ============================================================

PRAGMA foreign_keys=ON;

-- 1. IDB image resolution
CREATE TABLE IF NOT EXISTS idb_mappings (
    class_name    TEXT PRIMARY KEY,
    idb_key       TEXT,
    image_url     TEXT,
    thumb_url     TEXT,
    verified      INTEGER DEFAULT 0,
    override      INTEGER DEFAULT 0,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Vehicle presets
CREATE TABLE IF NOT EXISTS vehicle_presets (
    preset_id     TEXT PRIMARY KEY,
    class_name    TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    category      TEXT DEFAULT 'vehicles',
    base_price    INTEGER NOT NULL,
    thumbnail_url TEXT,
    enabled       INTEGER DEFAULT 1,
    created_by    INTEGER,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Vehicle parts per preset
CREATE TABLE IF NOT EXISTS vehicle_parts (
    part_id       TEXT PRIMARY KEY,
    preset_id     TEXT NOT NULL REFERENCES vehicle_presets(preset_id),
    slot_type     TEXT NOT NULL,
    class_name    TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    is_required   INTEGER DEFAULT 1,
    enabled       INTEGER DEFAULT 1,
    sort_order    INTEGER DEFAULT 0,
    thumbnail_url TEXT
);

-- 4. Color/variant alternatives per vehicle part
CREATE TABLE IF NOT EXISTS vehicle_part_variants (
    variant_id    TEXT PRIMARY KEY,
    part_id       TEXT NOT NULL REFERENCES vehicle_parts(part_id),
    class_name    TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    color_label   TEXT,
    thumbnail_url TEXT
);

-- 5. Trunk/cargo loadout presets
CREATE TABLE IF NOT EXISTS trunk_loadouts (
    loadout_id    TEXT PRIMARY KEY,
    preset_id     TEXT NOT NULL REFERENCES vehicle_presets(preset_id),
    display_name  TEXT NOT NULL,
    created_by    INTEGER,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Items within a trunk loadout
CREATE TABLE IF NOT EXISTS trunk_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    loadout_id    TEXT NOT NULL REFERENCES trunk_loadouts(loadout_id),
    class_name    TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    quantity      INTEGER DEFAULT 1,
    slot_type     TEXT DEFAULT 'cargo',
    parent_class  TEXT,
    nesting_depth INTEGER DEFAULT 0
);

-- 7. Attachment/nesting compatibility rules
CREATE TABLE IF NOT EXISTS attachment_compat (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    host_class    TEXT NOT NULL,
    attach_class  TEXT NOT NULL,
    slot_name     TEXT NOT NULL,
    valid         INTEGER DEFAULT 1,
    source        TEXT DEFAULT 'manual'
);

-- 8. Onboarding/welcome state per member per guild
CREATE TABLE IF NOT EXISTS onboarding_state (
    discord_id     INTEGER NOT NULL,
    guild_id       INTEGER NOT NULL,
    stage          TEXT DEFAULT 'JOINED',
    rules_accepted INTEGER DEFAULT 0,
    welcome_sent   INTEGER DEFAULT 0,
    completed_at   TIMESTAMP,
    PRIMARY KEY (discord_id, guild_id)
);

-- 9. Counting game config per guild
CREATE TABLE IF NOT EXISTS counting_config (
    guild_id       INTEGER PRIMARY KEY,
    channel_id     INTEGER,
    current_count  INTEGER DEFAULT 0,
    current_holder INTEGER,
    high_score     INTEGER DEFAULT 0,
    penalty_role   TEXT,
    milestone_role TEXT,
    active         INTEGER DEFAULT 1
);

-- 10. Counting game history
CREATE TABLE IF NOT EXISTS counting_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    INTEGER NOT NULL,
    discord_id  INTEGER NOT NULL,
    count_value INTEGER NOT NULL,
    correct     INTEGER NOT NULL,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 11. Nitrado monitor event log
CREATE TABLE IF NOT EXISTS monitor_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type    TEXT NOT NULL,
    server_status TEXT,
    failure_count INTEGER DEFAULT 0,
    monitor_state TEXT NOT NULL,
    message       TEXT,
    triggered_by  TEXT DEFAULT 'auto',
    timestamp     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 12. Nitrado monitor singleton state row
CREATE TABLE IF NOT EXISTS monitor_state (
    id                   INTEGER PRIMARY KEY CHECK (id = 1),
    current_state        TEXT NOT NULL DEFAULT 'IDLE',
    failure_count        INTEGER DEFAULT 0,
    last_check           TIMESTAMP,
    last_restart_attempt TIMESTAMP,
    last_recovery        TIMESTAMP,
    restart_in_progress  INTEGER DEFAULT 0,
    override_active      INTEGER DEFAULT 0,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO monitor_state (id, current_state) VALUES (1, 'IDLE');

-- 13. Admin key-value settings per guild
CREATE TABLE IF NOT EXISTS admin_settings (
    guild_id      INTEGER NOT NULL,
    setting_key   TEXT NOT NULL,
    setting_value TEXT,
    updated_by    INTEGER,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (guild_id, setting_key)
);

-- New indexes for new tables
CREATE INDEX IF NOT EXISTS idx_idb_class        ON idb_mappings(class_name);
CREATE INDEX IF NOT EXISTS idx_monitor_log_type ON monitor_log(event_type);
CREATE INDEX IF NOT EXISTS idx_monitor_log_time ON monitor_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_counting_guild   ON counting_history(guild_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_guild ON onboarding_state(guild_id);
