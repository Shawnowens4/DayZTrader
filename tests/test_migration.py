"""
tests/test_migration.py — Migration safety tests.

Verifies that:
  1. 001_base.sql applied to a fresh DB produces exactly 13 tables.
  2. 002_new_systems.sql applied after 001 produces exactly 26 tables.
  3. Both migrations are idempotent (safe to re-run: IF NOT EXISTS).
  4. No existing tables are dropped or renamed by 002.

All tests use isolated tmp DBs — the live DB is never touched.

Usage:
    pytest tests/test_migration.py -v
"""
import sqlite3
import os
import pytest

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "db", "migrations")
MIG_001 = os.path.join(MIGRATIONS_DIR, "001_base.sql")
MIG_002 = os.path.join(MIGRATIONS_DIR, "002_new_systems.sql")

BASE_TABLES = {
    "users", "transactions", "shop_items", "purchases",
    "delivery_queue", "market_listings", "market_disputes",
    "raffles", "raffle_entries", "casino_games", "casino_stats",
    "audit_log", "delivery_zones",
}

NEW_TABLES = {
    "idb_mappings", "vehicle_presets", "vehicle_parts", "vehicle_part_variants",
    "trunk_loadouts", "trunk_items", "attachment_compat", "onboarding_state",
    "counting_config", "counting_history", "monitor_log", "monitor_state",
    "admin_settings",
}


def _tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


def _run_sql_file(conn, path: str) -> None:
    with open(path) as f:
        conn.executescript(f.read())
    conn.commit()


@pytest.fixture
def fresh_db(tmp_path):
    db_file = str(tmp_path / "test_migrate.db")
    conn = sqlite3.connect(db_file)
    yield conn
    conn.close()


class TestMigration001:
    def test_produces_13_base_tables(self, fresh_db):
        _run_sql_file(fresh_db, MIG_001)
        assert _tables(fresh_db) == BASE_TABLES

    def test_idempotent(self, fresh_db):
        _run_sql_file(fresh_db, MIG_001)
        _run_sql_file(fresh_db, MIG_001)  # run twice
        assert _tables(fresh_db) == BASE_TABLES


class TestMigration002:
    def test_produces_26_total_tables(self, fresh_db):
        _run_sql_file(fresh_db, MIG_001)
        _run_sql_file(fresh_db, MIG_002)
        assert len(_tables(fresh_db)) == 26

    def test_all_new_tables_present(self, fresh_db):
        _run_sql_file(fresh_db, MIG_001)
        _run_sql_file(fresh_db, MIG_002)
        missing = NEW_TABLES - _tables(fresh_db)
        assert not missing, f"Missing new tables: {missing}"

    def test_all_base_tables_still_present(self, fresh_db):
        _run_sql_file(fresh_db, MIG_001)
        _run_sql_file(fresh_db, MIG_002)
        missing = BASE_TABLES - _tables(fresh_db)
        assert not missing, f"Base tables lost after 002: {missing}"

    def test_idempotent(self, fresh_db):
        _run_sql_file(fresh_db, MIG_001)
        _run_sql_file(fresh_db, MIG_002)
        _run_sql_file(fresh_db, MIG_002)  # run 002 twice
        assert len(_tables(fresh_db)) == 26

    def test_monitor_state_seed_row_exists(self, fresh_db):
        _run_sql_file(fresh_db, MIG_001)
        _run_sql_file(fresh_db, MIG_002)
        row = fresh_db.execute("SELECT id, current_state FROM monitor_state WHERE id=1").fetchone()
        assert row is not None
        assert row[1] == "IDLE"
