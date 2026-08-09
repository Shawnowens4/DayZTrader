"""Pure delivery decision engine for Auto-Trader scheduler planning.

This module performs no I/O, no DB writes, and no network operations.
It only returns policy decisions for caller-orchestrated flows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable


ACTIONS = {
    "hold",
    "poll",
    "prepare",
    "eligible_to_write",
    "retry_later",
    "fail",
    "refund_eligible",
}


ELIGIBLE_ORDER_STATES = {
    "paid",
    "queued_for_delivery",
    "awaiting_restart_window",
    "delivery_written",
    "failed",
    "cancelled",
}


@dataclass(frozen=True)
class RestartWindow:
    id: str
    window_start_at: datetime
    window_end_at: datetime
    observed_at: datetime
    expires_at: datetime
    confidence: str
    is_conflicting: bool = False


@dataclass(frozen=True)
class DecisionPolicy:
    poll_interval_minutes: int = 5
    write_target_minutes_before_restart: int = 10
    write_guard_earliest_minutes_before_restart: int = 12
    write_guard_latest_minutes_before_restart: int = 5
    stale_after_minutes: int = 30
    max_attempts_per_window: int = 4


@dataclass(frozen=True)
class DeliveryDecision:
    action: str
    reason: str
    order_state: str
    selected_window_id: str | None = None
    retry_after_seconds: int | None = None
    should_alert: bool = False
    refund_eligible: bool = False


class DeliveryDecisionError(Exception):
    """Raised when invalid policy/action inputs are supplied."""


def _minutes_until(now: datetime, target: datetime) -> float:
    return (target - now).total_seconds() / 60.0


def _is_stale(window: RestartWindow, now: datetime, policy: DecisionPolicy) -> bool:
    if now > window.expires_at:
        return True
    max_age = timedelta(minutes=policy.stale_after_minutes)
    return (now - window.observed_at) > max_age


def _is_valid_window(window: RestartWindow, now: datetime, policy: DecisionPolicy) -> tuple[bool, str]:
    if window.is_conflicting:
        return False, "window_conflicting"
    if window.confidence not in {"high", "medium", "low"}:
        return False, "window_confidence_invalid"
    if window.window_end_at <= window.window_start_at:
        return False, "window_invalid_range"
    if _is_stale(window, now, policy):
        return False, "window_stale"
    if window.confidence == "low":
        return False, "window_low_confidence"
    return True, "window_valid"


def _select_window(
    windows: Iterable[RestartWindow],
    now: datetime,
    policy: DecisionPolicy,
) -> tuple[RestartWindow | None, str]:
    candidates: list[RestartWindow] = []
    saw_conflict = False
    saw_stale = False

    for window in windows:
        valid, reason = _is_valid_window(window, now, policy)
        if window.is_conflicting:
            saw_conflict = True
        if reason == "window_stale":
            saw_stale = True
        if not valid:
            continue
        if window.window_start_at <= now:
            continue
        candidates.append(window)

    if saw_conflict:
        return None, "window_conflicting"
    if not candidates and saw_stale:
        return None, "window_stale"
    if not candidates:
        return None, "window_unknown"

    candidates.sort(key=lambda w: w.window_start_at)
    return candidates[0], "window_selected"


def decide_delivery_action(
    *,
    order_state: str,
    windows: Iterable[RestartWindow],
    now: datetime,
    policy: DecisionPolicy | None = None,
    artifact_validation_passed: bool = True,
    previous_attempts_for_window: int = 0,
) -> DeliveryDecision:
    policy = policy or DecisionPolicy()

    if order_state not in ELIGIBLE_ORDER_STATES:
        return DeliveryDecision(
            action="fail",
            reason="order_state_not_scheduler_eligible",
            order_state=order_state,
            should_alert=True,
        )

    if order_state in {"failed", "cancelled"}:
        return DeliveryDecision(
            action="refund_eligible",
            reason="terminal_failure_or_cancel",
            order_state=order_state,
            refund_eligible=True,
        )

    if not artifact_validation_passed:
        return DeliveryDecision(
            action="fail",
            reason="artifact_validation_failed",
            order_state=order_state,
            should_alert=True,
        )

    if previous_attempts_for_window >= policy.max_attempts_per_window:
        return DeliveryDecision(
            action="fail",
            reason="max_attempts_exceeded_for_window",
            order_state=order_state,
            should_alert=True,
            refund_eligible=(order_state in {"delivery_written", "awaiting_restart_window"}),
        )

    selected, selection_reason = _select_window(windows, now, policy)
    if selected is None:
        if selection_reason == "window_conflicting":
            return DeliveryDecision(
                action="hold",
                reason="restart_window_conflicting",
                order_state=order_state,
                should_alert=True,
            )
        if selection_reason == "window_stale":
            return DeliveryDecision(
                action="poll",
                reason="restart_window_stale_refresh_required",
                order_state=order_state,
                retry_after_seconds=policy.poll_interval_minutes * 60,
                should_alert=True,
            )
        return DeliveryDecision(
            action="poll",
            reason="restart_window_unknown",
            order_state=order_state,
            retry_after_seconds=policy.poll_interval_minutes * 60,
        )

    minutes_until = _minutes_until(now, selected.window_start_at)
    earliest = policy.write_guard_earliest_minutes_before_restart
    latest = policy.write_guard_latest_minutes_before_restart

    if minutes_until > earliest:
        return DeliveryDecision(
            action="prepare",
            reason="window_confirmed_not_yet_in_write_guard",
            order_state=order_state,
            selected_window_id=selected.id,
            retry_after_seconds=policy.poll_interval_minutes * 60,
        )

    if latest <= minutes_until <= earliest:
        return DeliveryDecision(
            action="eligible_to_write",
            reason="within_write_guard_before_restart",
            order_state=order_state,
            selected_window_id=selected.id,
        )

    if minutes_until < latest:
        return DeliveryDecision(
            action="retry_later",
            reason="write_guard_missed_wait_next_window",
            order_state=order_state,
            selected_window_id=selected.id,
            retry_after_seconds=policy.poll_interval_minutes * 60,
            should_alert=True,
        )

    raise DeliveryDecisionError("unreachable decision branch")
