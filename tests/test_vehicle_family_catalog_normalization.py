from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DXEMB_ROOT = ROOT / "dxemb"
if str(DXEMB_ROOT) not in sys.path:
    sys.path.insert(0, str(DXEMB_ROOT))

from shared.catalog.vehicle_family_catalog import resolve_vehicle_family_identity
from shared.catalog.vehicle_thumbnail_resolver_service import normalize_family


class VehicleFamilyCatalogNormalizationTests(unittest.TestCase):
    def test_sedan_02_prefix_resolves_to_sarka_120(self) -> None:
        identity = resolve_vehicle_family_identity("Sedan_02_Door_1_1")
        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity["canonical_key"], "sedan_02")
        self.assertEqual(identity["display_name"], "Sarka 120")

    def test_hatchback_02_prefix_resolves_to_gunter_2(self) -> None:
        identity = resolve_vehicle_family_identity("Hatchback_02_Door_1_1")
        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity["canonical_key"], "hatchback_02")
        self.assertEqual(identity["display_name"], "Gunter 2")

    def test_hatchback_and_sedan_do_not_cross_resolve(self) -> None:
        sedan = resolve_vehicle_family_identity("Sedan_02_Door_1_1")
        hatchback = resolve_vehicle_family_identity("Hatchback_02_Door_1_1")
        self.assertNotEqual(sedan["canonical_key"], hatchback["canonical_key"])  # type: ignore[index]
        self.assertEqual(normalize_family("Sarka 120"), "sedan_02")
        self.assertEqual(normalize_family("Gunter 2"), "hatchback_02")
        self.assertNotEqual(normalize_family("Sarka 120"), "hatchback_02")
        self.assertNotEqual(normalize_family("offroad_02"), "hatchback_02")


if __name__ == "__main__":
    unittest.main()
