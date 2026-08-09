"""Utilities for disposable PostgreSQL test databases.

This harness is intentionally isolated from runtime code paths.
It is designed for schema/service contract tests in local CI/dev workflows.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse


DEFAULT_ADMIN_URL = "postgresql://dxemb:dxemb_dev_password@localhost:5432/postgres"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def init_sql_path() -> Path:
    return project_root() / "dxemb" / "db" / "init.sql"


def migration_sql_path(name: str) -> Path:
    return project_root() / "dxemb" / "db" / "migrations" / name


def admin_database_url() -> str:
    """Return admin URL used to create/drop disposable test databases."""
    return os.getenv("TEST_DATABASE_ADMIN_URL", DEFAULT_ADMIN_URL)


def disposable_database_name(prefix: str = "dxemb_slice") -> str:
    suffix = uuid.uuid4().hex[:10]
    return f"{prefix}_{suffix}"


def database_url_for_name(base_admin_url: str, database_name: str) -> str:
    parsed = urlparse(base_admin_url)
    replaced = parsed._replace(path=f"/{database_name}")
    return urlunparse(replaced)


def create_disposable_database(db_name: str) -> None:
    import psycopg2

    conn = psycopg2.connect(admin_database_url())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        conn.close()


def drop_disposable_database(db_name: str) -> None:
    import psycopg2

    conn = psycopg2.connect(admin_database_url())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # Terminate active sessions before drop for repeatable local runs.
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (db_name,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    finally:
        conn.close()


def apply_schema(db_url: str) -> None:
    apply_sql_file(db_url, init_sql_path())


def apply_sql_file(db_url: str, sql_path: Path) -> None:
    import psycopg2

    sql_text = sql_path.read_text(encoding="utf-8")
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)


def ensure_psycopg2_available() -> bool:
    try:
        import psycopg2  # noqa: F401
    except Exception:
        return False
    return True
