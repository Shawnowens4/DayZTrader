"""
tests/test_schema.py — Characterization tests for the existing DB schema.

Pins the current 13-table structure exactly so any future migration
that accidentally drops or renames something is caught immediately.

Requires a populated DB at DB_PATH or falls back to a fresh schema.sql DB.
Run before applying any migration.

Usage:
    pytest tests/test_schema.py -v
    DB_PATH=db/dayz_trader.db pytest tests/test_schema.py -v
"""
import sqlite3
import os
import pytest

DB_PATH = os.getenv("DB_PATH", "db/dayz_trader.db")

EXPECTED_TABLES = {
    "users", "transactions", "shop_items", "purchases",
    "delivery_queue", "market_listings", "market_disputes",
    "raffles", "raffle_entries", "casino_games", "casino_stats",
    "audit_log", "delivery_zones",
}  # 13 tables

EXPECTED_INDEXES = {
    "idx_transactions_user", "idx_purchases_user", "idx_purchases_status",
    "idx_delivery_status", "idx_market_status", "idx_market_seller",
    "idx_raffle_week", "idx_raffle_entries_user",
    "idx_casino_games_user", "idx_audit_type",
}  # 10 indexes

EXPECTED_COLUMNS = {
    "users": {
        "discord_id", "username", "balance", "total_earned", "total_spent",
        "joined_at", "last_seen", "last_daily", "is_banned",
    },
    "shop_items": {
        "item_id", "class_name", "display_name", "price", "category",
        "is_bundle", "bundle_data", "bundle_discount", "stock",
        "enabled", "admin_only", "image_url", "description",
        "created_by", "created_at", "updated_at",
    },
    "delivery_queue": {
        "id", "purchase_id", "job_type", "discord_id", "item_class",
        "item_display", "quantity", "delivery_zone", "is_vehicle",
        "fully_kitted", "attachments", "status", "attempt_count",
        "lifetime_sec", "queued_at", "processed_at", "revert_at",
    },
    "audit_log": {
        "id", "trade_type", "actor_id", "target_id",
        "item_ref", "amount", "notes", "timestamp",
    },
    "delivery_zones": {
        "zone_id", "name", "display", "coord_x", "coord_z",
        "map_lat", "map_lng", "vehicle_ok", "item_ok", "enabled",
    },
}

EXPECTED_ZONE_IDS = {
    "nwaf", "neaf", "balota", "berezino", "electro", "cherno", "vybor", "tisy"
}


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    """
    If live DB exists at DB_PATH, connect to it (read-only structural test).
    If not, initialise a fresh one from db/schema.sql for structural tests only.
    """
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        yield conn
        conn.close()
    else:
        schema_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
        if not os.path.exists(schema_path):
            pytest.skip("No DB and no schema.sql found — cannot run schema tests.")
        db_file = str(tmp_path_factory.mktemp("db") / "test.db")
        conn = sqlite3.connect(db_file)
        with open(schema_path) as f:
            conn.executescript(f.read())
        conn.commit()
        yield conn
        conn.close()


def _tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


def _indexes(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


def _columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


class TestTablePresence:
    def test_all_13_base_tables_exist(self, db):
        missing = EXPECTED_TABLES - _tables(db)
        assert not missing, f"Missing base tables: {missing}"

    def test_table_count_is_at_least_13(self, db):
        assert len(_tables(db)) >= 13


class TestIndexPresence:
    def test_all_10_base_indexes_exist(self, db):
        missing = EXPECTED_INDEXES - _indexes(db)
        assert not missing, f"Missing indexes: {missing}"


class TestColumnIntegrity:
    @pytest.mark.parametrize("table,expected_cols", EXPECTED_COLUMNS.items())
    def test_columns_present(self, db, table, expected_cols):
        actual = _columns(db, table)
        missing = expected_cols - actual
        assert not missing, f"Table '{table}' is missing columns: {missing}"


class TestDeliveryZoneSeed:
    def test_all_8_default_zones_seeded(self, db):
        rows = db.execute("SELECT zone_id FROM delivery_zones").fetchall()
        actual = {r[0] for r in rows}
        missing = EXPECTED_ZONE_IDS - actual
        assert not missing, f"Missing delivery zone seed rows: {missing}"
