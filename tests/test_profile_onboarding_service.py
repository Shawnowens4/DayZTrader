from __future__ import annotations

import sys
import unittest
from pathlib import Path

from tests.harness.postgres_isolated import (
    admin_database_url,
    apply_schema,
    apply_sql_file,
    create_disposable_database,
    database_url_for_name,
    disposable_database_name,
    drop_disposable_database,
    ensure_psycopg2_available,
    migration_sql_path,
)

ROOT = Path(__file__).resolve().parents[1]
DXEMB_ROOT = ROOT / "dxemb"
if str(DXEMB_ROOT) not in sys.path:
    sys.path.insert(0, str(DXEMB_ROOT))

from shared.profile_onboarding_service import OnboardingStateError
from shared.profile_onboarding_service import ProfileOnboardingService


class ProfileOnboardingServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not ensure_psycopg2_available():
            raise unittest.SkipTest("psycopg2 is not available in the current interpreter")

        cls.db_name = disposable_database_name(prefix="dxemb_profile")
        cls.db_url = database_url_for_name(admin_database_url(), cls.db_name)
        create_disposable_database(cls.db_name)
        try:
            apply_schema(cls.db_url)
            apply_sql_file(cls.db_url, migration_sql_path("005_profile_onboarding_foundation.sql"))
        except Exception:
            drop_disposable_database(cls.db_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        drop_disposable_database(cls.db_name)

    def setUp(self) -> None:
        self.service = ProfileOnboardingService(database_url=self.db_url)
        self.user_id = f"profile-{self._testMethodName}"

    def test_profile_upsert_idempotency(self) -> None:
        first = self.service.upsert_profile(
            discord_user_id=self.user_id,
            display_name="Alpha",
            timezone="UTC",
            preferred_platform="XBOX",
            metadata={"step": 1},
        )
        second = self.service.upsert_profile(
            discord_user_id=self.user_id,
            display_name=None,
            timezone="UTC+1",
            preferred_platform=None,
            metadata={"step": 2},
        )

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["display_name"], "Alpha")
        self.assertEqual(second["timezone"], "UTC+1")
        self.assertEqual(second["preferred_platform"], "XBOX")

    def test_onboarding_state_transitions(self) -> None:
        states = [
            "STARTED",
            "PROFILE_CAPTURED",
            "READY_FOR_REVIEW",
            "COMPLETED",
        ]
        for state in states:
            result = self.service.transition_onboarding_state(
                discord_user_id=self.user_id,
                to_state=state,
                actor_discord_id="staff-1",
                note=f"to {state}",
            )
            self.assertTrue(result["applied"])

        self.assertEqual(self.service.get_onboarding_state(self.user_id), "COMPLETED")

    def test_invalid_transition_rejected(self) -> None:
        with self.assertRaises(OnboardingStateError):
            self.service.transition_onboarding_state(
                discord_user_id=self.user_id,
                to_state="READY_FOR_REVIEW",
                actor_discord_id="staff-2",
            )

    def test_dry_run_evaluator_outputs_only(self) -> None:
        result = self.service.evaluate_onboarding_dry_run(
            discord_user_id=self.user_id,
            state="PROFILE_CAPTURED",
        )
        self.assertTrue(result["dry_run"])
        self.assertIn("queue_manual_review", result["actions"])
        self.assertEqual(self.service.get_onboarding_state(self.user_id), None)


if __name__ == "__main__":
    unittest.main()
