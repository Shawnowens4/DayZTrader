from __future__ import annotations

import unittest

from tests.harness.postgres_isolated import (
    DEFAULT_ADMIN_URL,
    admin_database_url,
    database_url_for_name,
    disposable_database_name,
    init_sql_path,
)


class HarnessSmokeTests(unittest.TestCase):
    def test_disposable_database_name_prefix(self) -> None:
        name = disposable_database_name(prefix="dxemb_test")
        self.assertTrue(name.startswith("dxemb_test_"))
        self.assertGreater(len(name), len("dxemb_test_"))

    def test_database_url_target_switch(self) -> None:
        db_url = database_url_for_name(DEFAULT_ADMIN_URL, "dxemb_contract_test")
        self.assertTrue(db_url.endswith("/dxemb_contract_test"))

    def test_init_sql_path_exists(self) -> None:
        self.assertTrue(init_sql_path().exists())

    def test_admin_url_default(self) -> None:
        self.assertEqual(admin_database_url(), DEFAULT_ADMIN_URL)


if __name__ == "__main__":
    unittest.main()
