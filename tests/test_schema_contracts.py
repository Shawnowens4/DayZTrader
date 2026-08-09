from __future__ import annotations

import unittest

from tests.harness.postgres_isolated import (
    admin_database_url,
    apply_schema,
    create_disposable_database,
    database_url_for_name,
    disposable_database_name,
    drop_disposable_database,
    ensure_psycopg2_available,
)


class SchemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        import psycopg2

        cls._psycopg2 = psycopg2
        cls.db_name = disposable_database_name(prefix="dxemb_contract")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)

        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def _connect(self):
        return self._psycopg2.connect(self.db_url, connect_timeout=5)

    def test_core_tables_exist(self) -> None:
        expected = {"player", "item", "escrow_transaction"}
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                    """
                )
                actual = {row[0] for row in cur.fetchall()}

        self.assertTrue(expected.issubset(actual))

    def test_player_contract_columns_and_uniqueness(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'player'
                    """
                )
                cols = {row[0] for row in cur.fetchall()}

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.constraint_column_usage ccu
                      ON tc.constraint_name = ccu.constraint_name
                     AND tc.table_schema = ccu.table_schema
                    WHERE tc.table_schema = 'public'
                      AND tc.table_name = 'player'
                      AND tc.constraint_type = 'UNIQUE'
                      AND ccu.column_name = 'discord_id'
                    """
                )
                unique_count = cur.fetchone()[0]

        self.assertIn("discord_id", cols)
        self.assertIn("created_at", cols)
        self.assertIn("updated_at", cols)
        self.assertGreaterEqual(unique_count, 1)

    def test_item_contract_for_catalog_queries(self) -> None:
        required = {
            "classname",
            "display_name",
            "category",
            "subcategory",
            "buy_price",
            "sell_price",
            "is_enabled",
            "thumbnail_url",
            "notes",
        }
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'item'
                    """
                )
                cols = {row[0] for row in cur.fetchall()}

        self.assertTrue(required.issubset(cols))

    def test_escrow_constraints_exist(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pg_get_constraintdef(c.oid)
                    FROM pg_constraint c
                    JOIN pg_class t ON c.conrelid = t.oid
                    JOIN pg_namespace n ON t.relnamespace = n.oid
                    WHERE n.nspname = 'public'
                      AND t.relname = 'escrow_transaction'
                      AND c.contype = 'c'
                    """
                )
                checks = [row[0] for row in cur.fetchall()]

        self.assertTrue(any("quantity > 0" in check for check in checks))
        self.assertTrue(any("state" in check and "PENDING" in check for check in checks))

    def test_catalog_query_compatibility(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO item (
                        classname,
                        display_name,
                        category,
                        subcategory,
                        is_enabled,
                        notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (classname) DO NOTHING
                    """,
                    (
                        "M4A1",
                        "M4A1 Assault Rifle",
                        "Weapons",
                        "Rifles",
                        True,
                        "{}",
                    ),
                )

                cur.execute(
                    """
                    SELECT
                        classname,
                        display_name,
                        category,
                        subcategory,
                        buy_price,
                        sell_price,
                        is_enabled,
                        thumbnail_url,
                        notes
                    FROM item
                    WHERE is_enabled = TRUE
                      AND (classname ILIKE %s OR COALESCE(display_name, '') ILIKE %s)
                    ORDER BY classname ASC
                    LIMIT %s OFFSET %s
                    """,
                    ("%M4%", "%M4%", 25, 0),
                )
                rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT DISTINCT category
                    FROM item
                    WHERE category IS NOT NULL
                    ORDER BY category ASC
                    """
                )
                categories = [row[0] for row in cur.fetchall()]

        self.assertGreaterEqual(len(rows), 1)
        self.assertIn("Weapons", categories)


if __name__ == "__main__":
    unittest.main()
