from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DXEMB_ROOT = ROOT / "dxemb"
if str(DXEMB_ROOT) not in sys.path:
    sys.path.insert(0, str(DXEMB_ROOT))

from shared.nitrado_delivery_decision_engine import DecisionPolicy
from shared.nitrado_delivery_decision_engine import RestartWindow
from shared.nitrado_delivery_decision_engine import decide_delivery_action


@dataclass
class FakeClock:
    now_value: datetime

    def now(self) -> datetime:
        return self.now_value


class NitradoDeliveryDecisionEngineTests(unittest.TestCase):
    def _window(
        self,
        *,
        now: datetime,
        start_in_minutes: int,
        end_in_minutes: int,
        confidence: str = "high",
        conflict: bool = False,
        observed_offset_minutes: int = -2,
        expires_offset_minutes: int = 20,
        wid: str = "w1",
    ) -> RestartWindow:
        return RestartWindow(
            id=wid,
            window_start_at=now + timedelta(minutes=start_in_minutes),
            window_end_at=now + timedelta(minutes=end_in_minutes),
            observed_at=now + timedelta(minutes=observed_offset_minutes),
            expires_at=now + timedelta(minutes=expires_offset_minutes),
            confidence=confidence,
            is_conflicting=conflict,
        )

    def test_unknown_window_returns_poll(self) -> None:
        clock = FakeClock(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc))
        decision = decide_delivery_action(
            order_state="queued_for_delivery",
            windows=[],
            now=clock.now(),
        )
        self.assertEqual(decision.action, "poll")
        self.assertEqual(decision.reason, "restart_window_unknown")

    def test_conflicting_window_returns_hold_and_alert(self) -> None:
        clock = FakeClock(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc))
        decision = decide_delivery_action(
            order_state="awaiting_restart_window",
            windows=[self._window(now=clock.now(), start_in_minutes=10, end_in_minutes=20, conflict=True)],
            now=clock.now(),
        )
        self.assertEqual(decision.action, "hold")
        self.assertTrue(decision.should_alert)

    def test_stale_window_returns_poll(self) -> None:
        clock = FakeClock(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc))
        stale = self._window(
            now=clock.now(),
            start_in_minutes=11,
            end_in_minutes=20,
            observed_offset_minutes=-90,
            expires_offset_minutes=-1,
        )
        decision = decide_delivery_action(
            order_state="queued_for_delivery",
            windows=[stale],
            now=clock.now(),
            policy=DecisionPolicy(stale_after_minutes=30),
        )
        self.assertEqual(decision.action, "poll")
        self.assertEqual(decision.reason, "restart_window_stale_refresh_required")

    def test_far_window_returns_prepare(self) -> None:
        clock = FakeClock(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc))
        window = self._window(now=clock.now(), start_in_minutes=30, end_in_minutes=40)
        decision = decide_delivery_action(
            order_state="queued_for_delivery",
            windows=[window],
            now=clock.now(),
        )
        self.assertEqual(decision.action, "prepare")
        self.assertEqual(decision.selected_window_id, "w1")

    def test_write_guard_returns_eligible_to_write(self) -> None:
        clock = FakeClock(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc))
        window = self._window(now=clock.now(), start_in_minutes=10, end_in_minutes=20)
        decision = decide_delivery_action(
            order_state="awaiting_restart_window",
            windows=[window],
            now=clock.now(),
        )
        self.assertEqual(decision.action, "eligible_to_write")
        self.assertEqual(decision.reason, "within_write_guard_before_restart")

    def test_too_late_for_window_returns_retry_later(self) -> None:
        clock = FakeClock(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc))
        window = self._window(now=clock.now(), start_in_minutes=4, end_in_minutes=20)
        decision = decide_delivery_action(
            order_state="awaiting_restart_window",
            windows=[window],
            now=clock.now(),
        )
        self.assertEqual(decision.action, "retry_later")
        self.assertTrue(decision.should_alert)

    def test_terminal_failed_state_is_refund_eligible(self) -> None:
        clock = FakeClock(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc))
        decision = decide_delivery_action(
            order_state="failed",
            windows=[],
            now=clock.now(),
        )
        self.assertEqual(decision.action, "refund_eligible")
        self.assertTrue(decision.refund_eligible)

    def test_invalid_order_state_fails(self) -> None:
        clock = FakeClock(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc))
        decision = decide_delivery_action(
            order_state="draft",
            windows=[],
            now=clock.now(),
        )
        self.assertEqual(decision.action, "fail")
        self.assertTrue(decision.should_alert)

    def test_artifact_validation_failure_fails(self) -> None:
        clock = FakeClock(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc))
        decision = decide_delivery_action(
            order_state="queued_for_delivery",
            windows=[self._window(now=clock.now(), start_in_minutes=10, end_in_minutes=20)],
            now=clock.now(),
            artifact_validation_passed=False,
        )
        self.assertEqual(decision.action, "fail")
        self.assertEqual(decision.reason, "artifact_validation_failed")

    def test_max_attempts_exceeded_fails(self) -> None:
        clock = FakeClock(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc))
        decision = decide_delivery_action(
            order_state="awaiting_restart_window",
            windows=[self._window(now=clock.now(), start_in_minutes=10, end_in_minutes=20)],
            now=clock.now(),
            previous_attempts_for_window=4,
            policy=DecisionPolicy(max_attempts_per_window=4),
        )
        self.assertEqual(decision.action, "fail")
        self.assertTrue(decision.should_alert)

    def test_engine_never_returns_restart_action(self) -> None:
        clock = FakeClock(datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc))
        decisions = [
            decide_delivery_action(order_state="queued_for_delivery", windows=[], now=clock.now()),
            decide_delivery_action(
                order_state="queued_for_delivery",
                windows=[self._window(now=clock.now(), start_in_minutes=10, end_in_minutes=20)],
                now=clock.now(),
            ),
            decide_delivery_action(
                order_state="awaiting_restart_window",
                windows=[self._window(now=clock.now(), start_in_minutes=4, end_in_minutes=20)],
                now=clock.now(),
            ),
        ]
        for decision in decisions:
            self.assertNotIn("restart", decision.action)
            self.assertIn(
                decision.action,
                {"hold", "poll", "prepare", "eligible_to_write", "retry_later", "fail", "refund_eligible"},
            )


if __name__ == "__main__":
    unittest.main()
