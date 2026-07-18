"""
Database initialization - creates all tables from schema.sql
"""
import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "db/dayz_trader.db")

async def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r") as f:
        schema = f.read()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(schema)
        await db.commit()
    print(f"Database initialized at {DB_PATH}")

async def get_db():
    return aiosqlite.connect(DB_PATH)
