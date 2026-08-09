from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


def _load_run_audit() -> callable:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "dxemb" / "shared" / "catalog" / "tools" / "audit_console_vehicle_assets.py"
    spec = importlib.util.spec_from_file_location("audit_console_vehicle_assets", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["audit_console_vehicle_assets"] = module
    spec.loader.exec_module(module)
    return module.run_audit


class ConsoleVehicleAuditArtifactsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.docs_dir = self.repo_root / "docs"
        self.data_dir = self.repo_root / "dxemb" / "shared" / "catalog" / "data"
        self.run_audit = _load_run_audit()

    def test_audit_generates_required_outputs(self) -> None:
        summary = self.run_audit()

        expected_files = [
            self.docs_dir / "DAYZ_IMAGE_AND_VEHICLE_VARIANT_AUDIT.md",
            self.docs_dir / "CONSOLE_VEHICLE_COMPATIBILITY_MATRIX.md",
            self.docs_dir / "CONSOLE_VEHICLE_OWNER_REVIEW_QUEUE.md",
            self.data_dir / "console_vehicle_compatibility.review.json",
        ]

        for path in expected_files:
            self.assertTrue(path.exists(), msg=f"missing expected audit file: {path}")
            self.assertGreater(path.stat().st_size, 50, msg=f"audit file unexpectedly small: {path}")

        self.assertIn("coverage_totals", summary)
        self.assertIn("coverage_states", summary)
        self.assertIn("compatibility_summary", summary)
        self.assertGreaterEqual(summary["owner_review_queue_count"], 1)
        self.assertGreaterEqual(summary["owner_review_grouped_count"], 1)

    def test_fail_closed_compatibility_json_shape(self) -> None:
        self.run_audit()
        compat_path = self.data_dir / "console_vehicle_compatibility.review.json"
        payload = json.loads(compat_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["scope"], "xbox_playstation_console_only")
        self.assertIn("fail_closed_message", payload)
        self.assertIn("Not available until console compatibility is verified", payload["fail_closed_message"])
        self.assertIn("evidence_record_template", payload)

        vehicles = payload.get("vehicles", [])
        self.assertGreaterEqual(len(vehicles), 5)

        allowed_status = {"approved", "owner_review_required", "excluded"}
        for vehicle in vehicles:
            self.assertIn(vehicle.get("approved_status"), allowed_status)
            self.assertIn(vehicle.get("selection_state"), {"allowed", "blocked"})

            for variant in vehicle.get("variants", []):
                self.assertIn(variant.get("approved_status"), allowed_status)
                self.assertIn(variant.get("selection_state"), {"allowed", "blocked"})
                self.assertIn(
                    variant.get("body_image_coverage"),
                    {"exact_local_image", "family_fallback_only", "generic_fallback_only", "missing", "part_only", "excluded"},
                )
                self.assertTrue(isinstance(variant.get("evidence_records", []), list))

        owner_review = payload.get("owner_review", {})
        queue = owner_review.get("raw", [])
        grouped = owner_review.get("grouped", [])
        self.assertGreaterEqual(len(queue), 1)
        self.assertGreaterEqual(len(grouped), 1)
        self.assertLessEqual(len(grouped), len(queue))

        for row in queue:
            self.assertTrue(row.get("vehicle"))
            self.assertTrue(row.get("relationship"))
            self.assertTrue(row.get("observed_classname"))
            self.assertTrue(isinstance(row.get("evidence_records", []), list))


if __name__ == "__main__":
    unittest.main()
