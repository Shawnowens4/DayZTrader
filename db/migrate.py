"""
db/migrate.py — Manual migration runner.

Reads db/migrations/*.sql files in sorted numeric order (001_, 002_, ...).
Executes each against the configured DB using sqlite3 executescript().
Every migration file uses CREATE TABLE IF NOT EXISTS — safe on populated DBs.

SAFETY RULES:
  - Never called by main.py, web/app.py, or db/init_db.py.
  - Must be run explicitly by an admin: python db/migrate.py
  - Always test against a DB copy first before running on the live DB.
  - DB_PATH defaults to db/dayz_trader.db (matches db/init_db.py).

Usage:
    python db/migrate.py
    DB_PATH=db/mytest.db python db/migrate.py
"""
import sqlite3
import os
import glob

DB_PATH = os.getenv("DB_PATH", "db/dayz_trader.db")
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def run_migrations(db_path: str = DB_PATH) -> None:
    migration_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    if not migration_files:
        print("No migration files found in db/migrations/")
        return

    print(f"DB path:    {db_path}")
    print(f"Migrations: {len(migration_files)} file(s) found\n")

    conn = sqlite3.connect(db_path)
    try:
        for filepath in migration_files:
            filename = os.path.basename(filepath)
            print(f"  Running: {filename} ...", end=" ", flush=True)
            with open(filepath, "r") as f:
                sql = f.read()
            conn.executescript(sql)
            conn.commit()
            print("\u2713")
    except Exception as e:
        conn.rollback()
        print(f"\n  \u2717 FAILED: {e}")
        raise
    finally:
        conn.close()

    print("\nAll migrations complete.")


if __name__ == "__main__":
    run_migrations()
