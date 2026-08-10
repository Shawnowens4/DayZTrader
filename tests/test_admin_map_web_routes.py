from __future__ import annotations

import importlib
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DXEMB_ROOT = ROOT / "dxemb"
if str(DXEMB_ROOT) not in sys.path:
    sys.path.insert(0, str(DXEMB_ROOT))


class AdminMapWebRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("DATABASE_URL", "postgresql://dxemb:dxemb@db:5432/dxemb")
        app_module = importlib.import_module("web.app")
        cls.app_module = importlib.reload(app_module)
        cls.client = cls.app_module.app.test_client()

    def test_workspace_requires_admin_role(self) -> None:
        response = self.client.get("/admin/map")
        self.assertEqual(response.status_code, 403)
        self.assertIn("admin role is required", response.get_data(as_text=True))

    def test_workspace_renders_for_admin_role(self) -> None:
        response = self.client.get("/admin/map?as_role=admin")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Map Admin Workspace", body)
        self.assertIn("No live game-map integration", body)
        self.assertIn("Local map preview slice", body)

    def test_workspace_normalizes_point_and_region_preview(self) -> None:
        response = self.client.get(
            "/admin/map"
            "?as_role=admin"
            "&tool=region"
            "&coord_mode=world"
            "&min_x=0&max_x=10000"
            "&min_z=0&max_z=10000"
            "&x=2500&z=5000"
            "&x2=7500&z2=9000"
        )
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Applied preview only", body)
        self.assertIn("north-west", body)
        self.assertIn("south-east", body)
        self.assertIn("25.0% / 50.0%", body)
        self.assertIn("Region width", body)
        self.assertIn("5000.0", body)

    def test_region_preview_requires_primary_point(self) -> None:
        response = self.client.get(
            "/admin/map"
            "?as_role=admin"
            "&tool=region"
            "&coord_mode=world"
            "&x2=7500&z2=9000"
        )
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Region preview requires Primary point values", body)
        self.assertNotIn("Internal Server Error", body)


if __name__ == "__main__":
    unittest.main()
