"""Local scheduler service scaffolding for fake-provider delivery flows.

This service is DB-backed for local tests, but does not perform real network
or filesystem actions. It records decisions, attempts, and alerts only.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any

from psycopg2.extras import Json

from shared.nitrado_delivery_decision_engine import DecisionPolicy
from shared.nitrado_delivery_decision_engine import RestartWindow
from shared.nitrado_delivery_decision_engine import decide_delivery_action
from shared.nitrado_delivery_interfaces import DeliveryFileTransport
from shared.nitrado_delivery_interfaces import RestartWindowProvider


DEFAULT_DATABASE_URL = "postgresql://dxemb:dxemb@db:5432/dxemb"


class SchedulerBoundaryError(Exception):
    """Raised when non-Auto-Trader domains attempt scheduler access."""


class SchedulerStateError(Exception):
    """Raised when scheduler state operations are invalid."""


@dataclass(frozen=True)
class DeliveryRequestResult:
    delivery_request_id: int
    order_id: int
    state: str
    delivery_request_key: str
    applied: bool
    idempotent: bool


class NitradoDeliverySchedulerService:
    ALLOWED_ORDER_STATES = {
        "paid",
        "queued_for_delivery",
        "awaiting_restart_window",
        "delivery_written",
        "failed",
        "cancelled",
    }

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    def enqueue_delivery_request(
        self,
        *,
        order_id: int,
        actor_id: str,
        source_domain: str = "AUTOTRADER",
    ) -> DeliveryRequestResult:
        if source_domain.strip().upper() != "AUTOTRADER":
            raise SchedulerBoundaryError("scheduler accepts only AUTOTRADER order domain")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, state
                    FROM trader_order
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise SchedulerStateError("trader_order not found")

                order_state = row[1]
                if order_state not in self.ALLOWED_ORDER_STATES:
                    raise SchedulerStateError(f"order state not scheduler-eligible: {order_state}")

                key = f"ORDER:{order_id}:DELIVERY"
                cur.execute(
                    """
                    SELECT id, state
                    FROM trader_delivery_request
                    WHERE delivery_request_key = %s
                    """,
                    (key,),
                )
                existing = cur.fetchone()
                if existing:
                    return DeliveryRequestResult(
                        delivery_request_id=int(existing[0]),
                        order_id=order_id,
                        state=existing[1],
                        delivery_request_key=key,
                        applied=False,
                        idempotent=True,
                    )

                initial_state = "queued_for_delivery" if order_state == "paid" else order_state
                cur.execute(
                    """
                    INSERT INTO trader_delivery_request (
                        order_id,
                        delivery_request_key,
                        state,
                        enqueue_at,
                        created_by,
                        updated_by
                    )
                    VALUES (%s, %s, %s, NOW(), %s, %s)
                    RETURNING id
                    """,
                    (order_id, key, initial_state, actor_id, actor_id),
                )
                request_id = int(cur.fetchone()[0])

                self._insert_scheduler_event(
                    cur,
                    request_id=request_id,
                    order_id=order_id,
                    event_type="DELIVERY_REQUEST_ENQUEUED",
                    from_state=None,
                    to_state=initial_state,
                    decision="prepare",
                    reason_code="REQUEST_ENQUEUED",
                    reason_text="Auto-Trader order entered scheduler queue",
                    actor_id=actor_id,
                    reference_id=f"ENQUEUE:{order_id}",
                    details={"source_domain": source_domain.upper()},
                )

                return DeliveryRequestResult(
                    delivery_request_id=request_id,
                    order_id=order_id,
                    state=initial_state,
                    delivery_request_key=key,
                    applied=True,
                    idempotent=False,
                )

    def poll_and_cache_windows(
        self,
        *,
        provider: RestartWindowProvider,
        now: datetime,
        actor_id: str,
    ) -> dict[str, Any]:
        windows = provider.fetch_restart_windows(now)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO delivery_poll_run (
                        run_kind,
                        started_at,
                        ended_at,
                        result,
                        summary_json
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        "schedule",
                        now,
                        now,
                        "ok",
                        Json({"window_count": len(windows), "actor_id": actor_id}),
                    ),
                )
                poll_run_id = int(cur.fetchone()[0])

                cached = 0
                for idx, window in enumerate(windows, start=1):
                    cur.execute(
                        """
                        INSERT INTO restart_window_cache (
                            source_ref,
                            window_start_at,
                            window_end_at,
                            confidence,
                            observed_at,
                            expires_at,
                            is_conflicting,
                            metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            window.source_ref,
                            window.window_start_at,
                            window.window_end_at,
                            window.confidence,
                            window.observed_at,
                            window.expires_at,
                            bool(window.is_conflicting),
                            Json({"poll_run_id": poll_run_id, "position": idx}),
                        ),
                    )
                    cached += 1

        return {
            "poll_run_id": poll_run_id,
            "cached_windows": cached,
            "mode": "dry-run",
        }

    def prepare_artifact_metadata_dry_run(
        self,
        *,
        order_id: int,
        artifact_type: str,
        payload: dict[str, Any],
        transport: DeliveryFileTransport,
    ) -> dict[str, Any]:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        artifact_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        artifact_key = f"ORDER:{order_id}:ARTIFACT:{artifact_hash}"

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trader_spawn_artifact (
                        order_id,
                        artifact_key,
                        artifact_type,
                        artifact_hash,
                        schema_version,
                        validation_result,
                        validation_summary
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (artifact_key) DO NOTHING
                    RETURNING id
                    """,
                    (
                        order_id,
                        artifact_key,
                        artifact_type,
                        artifact_hash,
                        "v1",
                        "passed",
                        Json({"mode": "dry-run", "payload_keys": sorted(payload.keys())}),
                    ),
                )
                row = cur.fetchone()
                artifact_id = int(row[0]) if row else None

        transport_result = transport.stage_artifact_metadata(
            order_id=order_id,
            artifact_hash=artifact_hash,
            metadata={"artifact_type": artifact_type, "mode": "dry-run"},
        )

        return {
            "artifact_id": artifact_id,
            "artifact_key": artifact_key,
            "artifact_hash": artifact_hash,
            "transport_result": transport_result,
            "mode": "dry-run",
        }

    def evaluate_request(
        self,
        *,
        order_id: int,
        now: datetime,
        policy: DecisionPolicy | None = None,
    ) -> dict[str, Any]:
        policy = policy or DecisionPolicy()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.id, r.state, o.state
                    FROM trader_delivery_request r
                    JOIN trader_order o ON o.id = r.order_id
                    WHERE r.order_id = %s
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                request_row = cur.fetchone()
                if not request_row:
                    raise SchedulerStateError("delivery request not found")

                request_id = int(request_row[0])
                request_state = request_row[1]
                order_state = request_row[2]

                cur.execute(
                    """
                    SELECT id, window_start_at, window_end_at, observed_at, expires_at, confidence, is_conflicting
                    FROM restart_window_cache
                    WHERE expires_at >= %s
                    ORDER BY window_start_at ASC
                    LIMIT 20
                    """,
                    (now,),
                )
                window_rows = cur.fetchall()

                windows = [
                    RestartWindow(
                        id=str(row[0]),
                        window_start_at=row[1],
                        window_end_at=row[2],
                        observed_at=row[3],
                        expires_at=row[4],
                        confidence=row[5],
                        is_conflicting=bool(row[6]),
                    )
                    for row in window_rows
                ]

                selected_window_int: int | None = None
                attempt_count = 0
                if windows:
                    try:
                        selected_window_int = int(windows[0].id)
                    except ValueError:
                        selected_window_int = None

                if selected_window_int is not None:
                    cur.execute(
                        """
                        SELECT COUNT(*)
                        FROM trader_delivery_attempt
                        WHERE trader_delivery_request_id = %s
                          AND restart_window_cache_id = %s
                        """,
                        (request_id, selected_window_int),
                    )
                    attempt_count = int(cur.fetchone()[0])

                decision = decide_delivery_action(
                    order_state=order_state,
                    windows=windows,
                    now=now,
                    policy=policy,
                    previous_attempts_for_window=attempt_count,
                )

                next_attempt_no = attempt_count + 1
                write_key = (
                    f"ORDER:{order_id}:WINDOW:{selected_window_int}:ATTEMPT:{next_attempt_no}"
                    if selected_window_int is not None
                    else f"ORDER:{order_id}:WINDOW:UNKNOWN:ATTEMPT:{next_attempt_no}"
                )

                cur.execute(
                    """
                    INSERT INTO trader_delivery_attempt (
                        order_id,
                        trader_delivery_request_id,
                        restart_window_cache_id,
                        write_key,
                        attempt_no,
                        decision,
                        decision_reason,
                        attempted_at,
                        duration_ms,
                        provider_result
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        order_id,
                        request_id,
                        selected_window_int,
                        write_key,
                        next_attempt_no,
                        decision.action,
                        decision.reason,
                        now,
                        0,
                        Json({"mode": "dry-run", "request_state": request_state}),
                    ),
                )
                attempt_id = int(cur.fetchone()[0])

                self._insert_scheduler_event(
                    cur,
                    request_id=request_id,
                    order_id=order_id,
                    event_type="DELIVERY_DECISION_RECORDED",
                    from_state=request_state,
                    to_state=request_state,
                    decision=decision.action,
                    reason_code=decision.reason,
                    reason_text="Decision evaluated by local scheduler engine",
                    actor_id="scheduler",
                    reference_id=f"ATTEMPT:{attempt_id}",
                    details={"retry_after_seconds": decision.retry_after_seconds},
                )

                if decision.should_alert:
                    cur.execute(
                        """
                        INSERT INTO trader_delivery_alert (
                            order_id,
                            trader_delivery_request_id,
                            severity,
                            alert_code,
                            message_redacted,
                            dedupe_key,
                            metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (order_id, dedupe_key) DO NOTHING
                        """,
                        (
                            order_id,
                            request_id,
                            "warning" if decision.action in {"hold", "poll", "retry_later"} else "high",
                            decision.reason.upper(),
                            "scheduler decision requires operator review",
                            f"ORDER:{order_id}:ALERT:{decision.reason}",
                            Json({"mode": "dry-run", "decision": decision.action}),
                        ),
                    )

                if decision.refund_eligible:
                    cur.execute(
                        """
                        UPDATE trader_delivery_request
                        SET state = 'refund_eligible',
                            updated_by = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        ("scheduler", request_id),
                    )

        return {
            "order_id": order_id,
            "action": decision.action,
            "reason": decision.reason,
            "selected_window_id": decision.selected_window_id,
            "retry_after_seconds": decision.retry_after_seconds,
            "should_alert": decision.should_alert,
            "refund_eligible": decision.refund_eligible,
            "mode": "dry-run",
        }

    def link_refund_eligibility(
        self,
        *,
        order_id: int,
        refund_reference_id: str,
        wallet_ledger_id: int,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trader_delivery_refund_link (
                        order_id,
                        refund_reference_id,
                        wallet_ledger_id,
                        linked_at,
                        details
                    )
                    VALUES (%s, %s, %s, NOW(), %s)
                    ON CONFLICT (order_id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        order_id,
                        refund_reference_id,
                        wallet_ledger_id,
                        Json({"mode": "dry-run"}),
                    ),
                )
                row = cur.fetchone()
                if row:
                    return {"linked": True, "refund_link_id": int(row[0]), "idempotent": False}

                return {"linked": False, "refund_link_id": None, "idempotent": True}

    def list_requests(self, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 200))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, order_id, delivery_request_key, state, enqueue_at, blocked_reason, created_at, updated_at
                    FROM trader_delivery_request
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (safe_limit,),
                )
                rows = cur.fetchall()

        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": int(row[0]),
                    "order_id": int(row[1]),
                    "delivery_request_key": row[2],
                    "state": row[3],
                    "enqueue_at": row[4],
                    "blocked_reason": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                }
            )
        return out

    def list_events(self, order_id: int, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, trader_delivery_request_id, event_type, from_state, to_state,
                           decision, reason_code, reason_text, actor_id, reference_id, details, created_at
                    FROM trader_scheduler_event
                    WHERE order_id = %s
                    ORDER BY created_at ASC, id ASC
                    LIMIT %s
                    """,
                    (order_id, safe_limit),
                )
                rows = cur.fetchall()

        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": int(row[0]),
                    "trader_delivery_request_id": int(row[1]),
                    "event_type": row[2],
                    "from_state": row[3],
                    "to_state": row[4],
                    "decision": row[5],
                    "reason_code": row[6],
                    "reason_text": row[7],
                    "actor_id": row[8],
                    "reference_id": row[9],
                    "details": row[10],
                    "created_at": row[11],
                }
            )
        return out

    def _insert_scheduler_event(
        self,
        cur,
        *,
        request_id: int,
        order_id: int,
        event_type: str,
        from_state: str | None,
        to_state: str | None,
        decision: str | None,
        reason_code: str | None,
        reason_text: str | None,
        actor_id: str | None,
        reference_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        cur.execute(
            """
            INSERT INTO trader_scheduler_event (
                trader_delivery_request_id,
                order_id,
                event_type,
                from_state,
                to_state,
                decision,
                reason_code,
                reason_text,
                actor_id,
                reference_id,
                details,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request_id,
                order_id,
                event_type,
                from_state,
                to_state,
                decision,
                reason_code,
                reason_text,
                actor_id,
                reference_id,
                Json(details or {}),
                datetime.now(timezone.utc),
            ),
        )
