from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


def _load_progress_module():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "dxemb" / "shared" / "catalog" / "tools" / "render_project_progress.py"
    spec = importlib.util.spec_from_file_location("render_project_progress", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["render_project_progress"] = module
    spec.loader.exec_module(module)
    return module


class ProjectProgressSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.data_path = self.repo_root / "dxemb" / "shared" / "catalog" / "data" / "project_progress.json"
        self.module = _load_progress_module()
        self.payload = json.loads(self.data_path.read_text(encoding="utf-8"))

    def test_active_local_weights_total_100_and_deferred_excluded(self) -> None:
        stats = self.module.calculate_and_validate(self.payload)
        self.assertEqual(stats["active_weight_total"], 100)
        self.assertGreaterEqual(len(stats["deferred"]), 1)
        for item in stats["deferred"]:
            self.assertEqual(int(item["weight"]), 0)

    def test_overall_percentage_calculation(self) -> None:
        stats = self.module.calculate_and_validate(self.payload)
        self.assertEqual(stats["overall"], 41)

    def test_invalid_status_percentage_combination_fails(self) -> None:
        invalid_payload = copy.deepcopy(self.payload)
        invalid_payload["items"][0]["status"] = "discovery"
        invalid_payload["items"][0]["percent_complete"] = 80

        with self.assertRaises(ValueError):
            self.module.calculate_and_validate(invalid_payload)

    def test_complete_requires_verification_fields(self) -> None:
        invalid_payload = copy.deepcopy(self.payload)
        target = next(item for item in invalid_payload["items"] if item["id"] == "18")
        target["status"] = "complete"
        target["percent_complete"] = 100
        target["test_status"] = "not_applicable"

        with self.assertRaises(ValueError):
            self.module.calculate_and_validate(invalid_payload)

    def test_owner_review_required_cannot_be_complete(self) -> None:
        invalid_payload = copy.deepcopy(self.payload)
        target = next(item for item in invalid_payload["items"] if item["id"] == "7")
        target["status"] = "owner_review_required"
        target["percent_complete"] = 100

        with self.assertRaises(ValueError):
            self.module.calculate_and_validate(invalid_payload)

    def test_vehicle_compatibility_and_builder_stay_blocked_until_queue_resolved(self) -> None:
        invalid_payload = copy.deepcopy(self.payload)
        invalid_payload["owner_review_queue_resolved"] = False

        item7 = next(item for item in invalid_payload["items"] if item["id"] == "7")
        item8 = next(item for item in invalid_payload["items"] if item["id"] == "8")

        item7["status"] = "locally_tested"
        item7["percent_complete"] = 80
        item8["status"] = "owner_review_required"
        item8["percent_complete"] = 85

        with self.assertRaises(ValueError):
            self.module.calculate_and_validate(invalid_payload)


if __name__ == "__main__":
    unittest.main()
