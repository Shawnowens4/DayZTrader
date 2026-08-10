# =============================================================
# DXEMB Web — app.py  (Epic A4 / A9)
# Flask admin panel entry point.
# Routes:
#   GET /         — HTML status dashboard (admin-facing)
#   GET /health   — JSON health check (bot + monitoring use)
# =============================================================
import sys
import os
import json
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, jsonify, render_template, request

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(ROOT_DIR))

from shared.db import get_sync_health
from shared.auto_trader_order_service import AutoTraderOrderService
from shared.game_economy_service import DeterministicCoinFlipEngine
from shared.game_economy_service import GameEconomyService
from shared.market_escrow_service import MarketEscrowService
from shared.mission_bounty_service import MissionBountyService
from shared.delivery_scheduler_service import NitradoDeliverySchedulerService
from shared.task_achievement_service import TaskAchievementService
from shared.wallet_ledger_service import InvalidAmountError
from shared.wallet_ledger_service import WalletLedgerService

try:
    from web.catalog_admin import catalog_bp
except ModuleNotFoundError:
    from catalog_admin import catalog_bp

try:
    from web.wallet_admin import wallet_admin_bp
except ModuleNotFoundError:
    from wallet_admin import wallet_admin_bp

try:
    from web.vehicle_admin import vehicle_bp
except ModuleNotFoundError:
    from vehicle_admin import vehicle_bp

try:
    from web.local_auth import admin_or_higher
    from web.local_auth import authenticated_player
    from web.local_auth import get_request_role_hint
    from web.local_auth import get_resolved_identity
    from web.local_auth import has_role
    from web.local_auth import moderator_or_higher
except ModuleNotFoundError:
    from local_auth import admin_or_higher
    from local_auth import authenticated_player
    from local_auth import get_request_role_hint
    from local_auth import get_resolved_identity
    from local_auth import has_role
    from local_auth import moderator_or_higher

try:
    from web.ui import register_ui_helpers
except ModuleNotFoundError:
    from ui import register_ui_helpers

app = Flask(__name__)
register_ui_helpers(app)
app.register_blueprint(catalog_bp)
app.register_blueprint(wallet_admin_bp)
app.register_blueprint(vehicle_bp)

TABLES = ["player", "item", "escrow_transaction"]
OPS_PAGE_SIZE = 20
OPS_MAX_PAGE_SIZE = 50
OPS_ALLOWED_MODERATION_ACTIONS = {"", "WARN", "STATUS_QUERY", "DRY_RUN_PREVIEW"}
OPS_ALLOWED_TICKET_STATUS = {"", "OPEN", "ASSIGNED", "CLOSED"}
OPS_ALLOWED_DELIVERY_STATES = {
    "",
    "queued_for_delivery",
    "awaiting_restart_window",
    "prepare_pending",
    "eligible_to_write",
    "retry_later",
    "failed",
    "refund_eligible",
    "delivered",
    "cancelled",
}
MAP_ALLOWED_TOOLS = {"point", "region"}
MAP_ALLOWED_COORD_MODES = {"world", "normalized"}
MAP_PREVIEW_DEFAULT_MIN = 0.0
MAP_PREVIEW_DEFAULT_MAX = 10000.0


def _request_role_hint() -> str:
    return get_request_role_hint()


def _is_admin_actor() -> bool:
    return has_role(get_resolved_identity(), "admin")


def _ops_database_url() -> str:
    return os.getenv("DATABASE_URL", "postgresql://dxemb:dxemb@db:5432/dxemb")


def _wallet_service() -> WalletLedgerService:
  return WalletLedgerService(database_url=os.getenv("DATABASE_URL"))


def _market_service() -> MarketEscrowService:
  return MarketEscrowService(database_url=os.getenv("DATABASE_URL"))


def _autotrader_service() -> AutoTraderOrderService:
    return AutoTraderOrderService(database_url=os.getenv("DATABASE_URL"))


def _scheduler_service() -> NitradoDeliverySchedulerService:
    return NitradoDeliverySchedulerService(database_url=os.getenv("DATABASE_URL"))


def _game_service() -> GameEconomyService:
    return GameEconomyService(database_url=os.getenv("DATABASE_URL"))


def _task_service() -> TaskAchievementService:
    return TaskAchievementService(database_url=os.getenv("DATABASE_URL"))


def _mission_service() -> MissionBountyService:
    return MissionBountyService(database_url=os.getenv("DATABASE_URL"))


def _resolve_local_player_identity() -> tuple[str | None, str | None, int]:
    identity = get_resolved_identity()
    if not identity.player_id:
        return None, "player identity is required via X-DXEMB-PLAYER-ID or discord_user_id", 401
    return identity.player_id, None, 200


def _parse_bounded_int(raw_value: str | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int((raw_value or "").strip() or str(default))
    except ValueError:
        return default
    return max(minimum, min(parsed, maximum))


def _parse_bounded_float(raw_value: str | None, *, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float((raw_value or "").strip() or str(default))
    except ValueError:
        return default
    return max(minimum, min(parsed, maximum))


def _normalize_choice(raw_value: str | None, *, allowed: set[str], default: str) -> str:
    candidate = (raw_value or "").strip()
    return candidate if candidate in allowed else default


def _map_workspace_progress_hint() -> dict[str, str]:
    out = {
        "id": "9",
        "title": "Local map preview slice",
        "status": "unknown",
        "blocker": "no local map progress data found",
        "next_step": "add map slice progress source entry",
    }
    source_path = ROOT_DIR / "shared" / "catalog" / "data" / "project_progress.json"
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        for item in payload.get("items", []):
            if str(item.get("id")) == "9":
                out["title"] = str(item.get("title") or out["title"])
                out["status"] = str(item.get("status") or out["status"])
                out["blocker"] = str(item.get("blocker") or "")
                out["next_step"] = str(item.get("next_step") or "")
                return out
    except Exception as exc:
        out["blocker"] = f"map progress data could not be read: {exc}"
    return out


def _map_normalize(value: float, *, minimum: float, maximum: float) -> float:
    span = maximum - minimum
    if span <= 0:
        return 0.0
    raw = (value - minimum) / span
    return max(0.0, min(raw, 1.0))


def _map_quadrant(*, normalized_x: float, normalized_z: float) -> str:
    top = "north" if normalized_z <= 0.5 else "south"
    side = "west" if normalized_x <= 0.5 else "east"
    return f"{top}-{side}"


def _map_parse_optional_pair(raw_x: str, raw_z: str, *, label: str, errors: list[str]) -> tuple[float, float] | None:
    x_value = raw_x.strip()
    z_value = raw_z.strip()
    if not x_value and not z_value:
        return None
    if not x_value or not z_value:
        errors.append(f"{label} requires both X and Z values")
        return None
    try:
        return float(x_value), float(z_value)
    except ValueError:
        errors.append(f"{label} values must be numeric")
        return None


def _wallet_auth_error_response(message: str, status_code: int):
    return (
        render_template(
            "wallet_player.html",
            auth_error=message,
            owner=None,
            history=[],
            page=1,
            limit=25,
            has_next=False,
            direction="all",
            status="all",
            entry_type="",
            reference_query="",
            created_after="",
            created_before="",
        ),
        status_code,
    )


def _ops_env_presence_rows() -> list[dict[str, object]]:
    env_items = [
        ("DATABASE_URL", "Database connection"),
        ("DISCORD_TOKEN", "Discord bot runtime"),
        ("GUILD_IDS", "Slash command scoping"),
        ("SLASH_SYNC", "Slash sync mode"),
        ("NITRADO_API_TOKEN", "Nitrado provider token"),
        ("NITRADO_SERVER_ID", "Nitrado target server"),
    ]
    rows: list[dict[str, object]] = []
    for key, label in env_items:
        value = (os.getenv(key) or "").strip()
        rows.append(
            {
                "key": key,
                "label": label,
                "present": bool(value),
                "hint": "set" if value else "missing",
            }
        )
    return rows


def _ops_feature_flags() -> dict[str, object]:
    out: dict[str, object] = {"game": [], "mission": [], "errors": []}
    try:
        import psycopg2

        with psycopg2.connect(_ops_database_url(), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT game_code, is_enabled, allow_live_payout, min_wager, max_wager, updated_at
                    FROM game_feature_flag
                    ORDER BY game_code ASC
                    """
                )
                for row in cur.fetchall():
                    out["game"].append(
                        {
                            "feature_code": row[0],
                            "is_enabled": bool(row[1]),
                            "mode_hint": "live" if bool(row[2]) else "dry-run",
                            "min_value": int(row[3]),
                            "max_value": int(row[4]),
                            "updated_at": row[5],
                        }
                    )

                cur.execute(
                    """
                    SELECT feature_code, is_enabled, allow_reward_settlement, updated_at
                    FROM mission_feature_flag
                    ORDER BY feature_code ASC
                    """
                )
                for row in cur.fetchall():
                    out["mission"].append(
                        {
                            "feature_code": row[0],
                            "is_enabled": bool(row[1]),
                            "mode_hint": "live" if bool(row[2]) else "dry-run",
                            "updated_at": row[3],
                        }
                    )
    except Exception as exc:
        out["errors"].append(str(exc))
    return out


def _ops_fetch_summary_counts() -> dict[str, object]:
    summary = {
        "moderation_action_count": 0,
        "open_ticket_count": 0,
        "assigned_ticket_count": 0,
        "scheduler_request_count": 0,
        "scheduler_open_alert_count": 0,
        "errors": [],
    }
    try:
        import psycopg2

        with psycopg2.connect(_ops_database_url(), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM moderation_action")
                summary["moderation_action_count"] = int(cur.fetchone()[0])

                cur.execute("SELECT COUNT(*) FROM support_ticket WHERE status = 'OPEN'")
                summary["open_ticket_count"] = int(cur.fetchone()[0])

                cur.execute("SELECT COUNT(*) FROM support_ticket WHERE status = 'ASSIGNED'")
                summary["assigned_ticket_count"] = int(cur.fetchone()[0])

                cur.execute("SELECT COUNT(*) FROM trader_delivery_request")
                summary["scheduler_request_count"] = int(cur.fetchone()[0])

                cur.execute("SELECT COUNT(*) FROM trader_delivery_alert WHERE acknowledged_at IS NULL")
                summary["scheduler_open_alert_count"] = int(cur.fetchone()[0])
    except Exception as exc:
        summary["errors"].append(str(exc))
    return summary


def _ops_fetch_moderation_rows(
    *,
    target_discord_id: str,
    moderation_action: str,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, object]], bool, str | None]:
    where_clauses = []
    params: list[object] = []
    if target_discord_id:
        where_clauses.append("target_discord_id = %s")
        params.append(target_discord_id)
    if moderation_action:
        where_clauses.append("action_type = %s")
        params.append(moderation_action)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    query = f"""
        SELECT
            m.id,
            m.action_type,
            m.actor_discord_id,
            m.target_discord_id,
            m.reason,
            m.reference_id,
            m.created_at,
            COALESCE(target_stats.total_actions, 0) AS target_total_actions,
            COALESCE(target_stats.warn_actions, 0) AS target_warn_actions
        FROM moderation_action m
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) AS total_actions,
                COUNT(*) FILTER (WHERE action_type = 'WARN') AS warn_actions
            FROM moderation_action mx
            WHERE mx.target_discord_id = m.target_discord_id
        ) target_stats ON TRUE
        {where_sql}
        ORDER BY m.created_at DESC, m.id DESC
        LIMIT %s OFFSET %s
    """

    rows: list[dict[str, object]] = []
    try:
        import psycopg2

        with psycopg2.connect(_ops_database_url(), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple([*params, limit + 1, offset]))
                for row in cur.fetchall():
                    target_id = row[3]
                    rows.append(
                        {
                            "id": int(row[0]),
                            "action_type": row[1],
                            "actor_discord_id": row[2],
                            "target_discord_id": target_id,
                            "reason": row[4],
                            "reference_id": row[5],
                            "created_at": row[6],
                            "target_total_actions": int(row[7]),
                            "target_warn_actions": int(row[8]),
                            "target_wallet_link": f"/wallet/admin/{target_id}?as_role=admin" if target_id else "",
                            "detail_marker": "Foundation exists; moderation detail workspace pending",
                        }
                    )
    except Exception as exc:
        return [], False, str(exc)

    has_next = len(rows) > limit
    return rows[:limit], has_next, None


def _ops_fetch_ticket_rows(
    *,
    ticket_status: str,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, object]], bool, str | None]:
    where_sql = "WHERE t.status = %s" if ticket_status else ""
    query = f"""
        SELECT
            t.id,
            t.external_ref,
            t.requester_discord_id,
            t.assignee_discord_id,
            t.subject,
            t.details,
            t.status,
            t.opened_at,
            t.closed_at,
            t.updated_at,
            ev.event_type,
            ev.actor_discord_id,
            ev.note,
            ev.created_at,
            COALESCE(ev_count.event_count, 0) AS event_count
        FROM support_ticket t
        LEFT JOIN LATERAL (
            SELECT event_type, actor_discord_id, note, created_at
            FROM support_ticket_event
            WHERE ticket_id = t.id
            ORDER BY id DESC
            LIMIT 1
        ) ev ON TRUE
        LEFT JOIN LATERAL (
            SELECT COUNT(*) AS event_count
            FROM support_ticket_event te
            WHERE te.ticket_id = t.id
        ) ev_count ON TRUE
        {where_sql}
        ORDER BY t.updated_at DESC, t.id DESC
        LIMIT %s OFFSET %s
    """

    params: list[object] = []
    if ticket_status:
        params.append(ticket_status)
    rows: list[dict[str, object]] = []

    try:
        import psycopg2

        with psycopg2.connect(_ops_database_url(), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple([*params, limit + 1, offset]))
                for row in cur.fetchall():
                    rows.append(
                        {
                            "id": int(row[0]),
                            "external_ref": row[1],
                            "requester_discord_id": row[2],
                            "assignee_discord_id": row[3],
                            "subject": row[4],
                            "details": row[5],
                            "status": row[6],
                            "opened_at": row[7],
                            "closed_at": row[8],
                            "updated_at": row[9],
                            "last_event_type": row[10],
                            "last_event_actor": row[11],
                            "last_event_note": row[12],
                            "last_event_at": row[13],
                            "event_count": int(row[14]),
                            "requester_wallet_link": f"/wallet/admin/{row[2]}?as_role=admin" if row[2] else "",
                            "assignee_wallet_link": f"/wallet/admin/{row[3]}?as_role=admin" if row[3] else "",
                            "detail_marker": "Foundation exists; ticket detail workspace pending",
                        }
                    )
    except Exception as exc:
        return [], False, str(exc)

    has_next = len(rows) > limit
    return rows[:limit], has_next, None


def _ops_fetch_scheduler_rows(
    *,
    delivery_state: str,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, object]], bool, str | None]:
    where_sql = "WHERE r.state = %s" if delivery_state else ""
    query = f"""
        SELECT
            r.id,
            r.order_id,
            r.state,
            r.enqueue_at,
            r.blocked_reason,
            COALESCE(a.attempt_count, 0) AS attempt_count,
            a.last_attempt_at,
            COALESCE(al.open_alert_count, 0) AS open_alert_count,
            la.decision AS latest_decision,
            la.decision_reason AS latest_decision_reason
        FROM trader_delivery_request r
        LEFT JOIN (
            SELECT trader_delivery_request_id, COUNT(*) AS attempt_count, MAX(attempted_at) AS last_attempt_at
            FROM trader_delivery_attempt
            GROUP BY trader_delivery_request_id
        ) a ON a.trader_delivery_request_id = r.id
        LEFT JOIN (
            SELECT trader_delivery_request_id, COUNT(*) AS open_alert_count
            FROM trader_delivery_alert
            WHERE acknowledged_at IS NULL
            GROUP BY trader_delivery_request_id
        ) al ON al.trader_delivery_request_id = r.id
        LEFT JOIN LATERAL (
            SELECT decision, decision_reason, attempted_at
            FROM trader_delivery_attempt da
            WHERE da.trader_delivery_request_id = r.id
            ORDER BY da.attempted_at DESC, da.id DESC
            LIMIT 1
        ) la ON TRUE
        {where_sql}
        ORDER BY r.enqueue_at DESC, r.id DESC
        LIMIT %s OFFSET %s
    """

    params: list[object] = []
    if delivery_state:
        params.append(delivery_state)
    rows: list[dict[str, object]] = []

    try:
        import psycopg2

        with psycopg2.connect(_ops_database_url(), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple([*params, limit + 1, offset]))
                for row in cur.fetchall():
                    rows.append(
                        {
                            "id": int(row[0]),
                            "order_id": int(row[1]),
                            "state": row[2],
                            "enqueue_at": row[3],
                            "blocked_reason": row[4],
                            "attempt_count": int(row[5]),
                            "last_attempt_at": row[6],
                            "open_alert_count": int(row[7]),
                            "latest_decision": row[8],
                            "latest_decision_reason": row[9],
                            "request_status_link": f"/autotrader/scheduler/orders/{int(row[1])}/status?as_role=moderator",
                            "order_detail_link": f"/autotrader/orders/{int(row[1])}",
                            "order_history_link": f"/autotrader/orders/{int(row[1])}/history",
                        }
                    )
    except Exception as exc:
        return [], False, str(exc)

    has_next = len(rows) > limit
    return rows[:limit], has_next, None


def _ops_build_url(base: dict[str, object], **overrides: object) -> str:
    merged: dict[str, object] = dict(base)
    merged.update(overrides)
    filtered = {
        key: value
        for key, value in merged.items()
        if value is not None and value != ""
    }
    return f"/admin/operations?{urlencode(filtered)}"


def _ops_section_summary(*, shown: int, page: int, limit: int, has_prev: bool, has_next: bool, error: str | None, row_label: str) -> dict[str, object]:
    start_row = 0 if shown == 0 else ((page - 1) * limit) + 1
    end_row = ((page - 1) * limit) + shown
    return {
        "shown": shown,
        "page": page,
        "limit": limit,
        "has_prev": has_prev,
        "has_next": has_next,
        "error": error,
        "window_label": f"{row_label}: {start_row}-{end_row}" if shown > 0 else f"{row_label}: none",
    }


# ------------------------------------------------------------------
# DB helper — synchronous psycopg2 (Flask is sync; asyncpg is bot-only)
# ------------------------------------------------------------------
def _db_check() -> dict:
  """Run DB health check via the shared database layer."""
  db = get_sync_health(TABLES)
  return {
    "ok": db["connected"],
    "latency_ms": db["latency_ms"],
    "tables": db["tables"],
    "error": db["error"],
  }


# ------------------------------------------------------------------
# GET /health  — JSON, used by bot, Docker healthcheck, monitoring
# ------------------------------------------------------------------
@app.route("/health")
def health():
    db = _db_check()
    payload = {
        "status": "ok" if db["ok"] else "degraded",
        "db": {
            "connected": db["ok"],
            "latency_ms": db["latency_ms"],
            "tables": db["tables"],
            "error": db["error"],
        },
    }
    status_code = 200 if db["ok"] else 503
    return jsonify(payload), status_code


@app.get("/wallet/<discord_user_id>")
def wallet_balance(discord_user_id: str):
    service = _wallet_service()
    return jsonify(
        {
            "discord_user_id": discord_user_id,
            "balance": service.get_balance(discord_user_id),
            "mode": "read-only",
        }
    )


@app.get("/wallet/<discord_user_id>/ledger")
def wallet_ledger(discord_user_id: str):
    limit = _parse_bounded_int(request.args.get("limit"), default=25, minimum=1, maximum=200)
    service = _wallet_service()
    rows = service.list_ledger_entries(discord_user_id=discord_user_id, limit=limit)
    return jsonify(
        {
            "discord_user_id": discord_user_id,
            "count": len(rows),
            "rows": rows,
            "mode": "read-only",
        }
    )


@app.post("/wallet/<discord_user_id>/preview")
def wallet_preview(discord_user_id: str):
    payload = request.get_json(silent=True) or {}
    operation = (payload.get("operation") or "").strip().lower()
    try:
        amount = int(payload.get("amount") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be an integer"}), 400
    service = _wallet_service()

    if amount <= 0:
        return jsonify({"error": "amount must be > 0"}), 400

    current = service.get_balance(discord_user_id)
    if operation == "credit":
        projected = current + amount
        allowed = True
        error = None
    elif operation == "debit":
        projected = current - amount
        allowed = projected >= 0
        error = None if allowed else "insufficient funds"
    else:
        return jsonify({"error": "operation must be credit or debit"}), 400

    return jsonify(
        {
            "discord_user_id": discord_user_id,
            "operation": operation,
            "amount": amount,
            "current_balance": current,
            "projected_balance": projected,
            "allowed": allowed,
            "error": error,
            "applied": False,
            "mode": "dry-run",
        }
    )


@app.post("/wallet/<discord_user_id>/adjust")
def wallet_adjust_disabled(discord_user_id: str):
    return (
        jsonify(
            {
                "error": "wallet mutation endpoint is disabled in local-safe mode",
                "discord_user_id": discord_user_id,
                "applied": False,
                "mode": "disabled",
            }
        ),
        403,
    )


@app.get("/wallet/me")
@authenticated_player(on_fail=_wallet_auth_error_response)
def wallet_me():
    owner_id = get_resolved_identity().player_id or ""

    service = _wallet_service()
    owner = service.get_wallet_summary(owner_id)
    if owner is None:
        service.ensure_wallet_owner(owner_id=owner_id, display_name=owner_id, owner_kind="LOCAL_PLAYER")
        owner = service.get_wallet_summary(owner_id)

    page = _parse_bounded_int(request.args.get("page"), default=1, minimum=1, maximum=100000)
    limit = _parse_bounded_int(request.args.get("limit"), default=25, minimum=1, maximum=50)
    direction = (request.args.get("direction", "all") or "all").strip().lower()
    status = (request.args.get("status", "all") or "all").strip().lower()
    entry_type = (request.args.get("entry_type", "") or "").strip().upper()
    reference_query = (request.args.get("reference_query", "") or "").strip()
    created_after = (request.args.get("created_after", "") or "").strip()
    created_before = (request.args.get("created_before", "") or "").strip()

    try:
        history = service.list_ledger_history(
            owner_id,
            limit=limit + 1,
            offset=(page - 1) * limit,
            direction=direction,
            status=status,
            entry_type=entry_type or None,
            reference_query=reference_query,
            created_after=created_after,
            created_before=created_before,
        )
    except InvalidAmountError as exc:
        return (
            render_template(
                "wallet_player.html",
                auth_error=str(exc),
                owner=owner,
                history=[],
                page=1,
                limit=limit,
                has_next=False,
                direction=direction,
                status=status,
                entry_type=entry_type,
                reference_query=reference_query,
                created_after=created_after,
                created_before=created_before,
            ),
            400,
        )
    has_next = len(history) > limit

    return render_template(
        "wallet_player.html",
        auth_error="",
        owner=owner,
        history=history[:limit],
        page=page,
        limit=limit,
        has_next=has_next,
        direction=direction,
        status=status,
        entry_type=entry_type,
        reference_query=reference_query,
        created_after=created_after,
        created_before=created_before,
    )


@app.get("/market/listings")
def market_listings():
    status = request.args.get("status")
    limit = max(1, min(int(request.args.get("limit", "25") or "25"), 200))
    service = _market_service()

    with service._connect() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    """
                    SELECT id, seller_discord_id, buyer_discord_id, listing_type,
                           item_classname, vehicle_label, vehicle_running, quantity,
                           price, delivery_mode, status, created_at, updated_at
                    FROM player_listing
                    WHERE status = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (status, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, seller_discord_id, buyer_discord_id, listing_type,
                           item_classname, vehicle_label, vehicle_running, quantity,
                           price, delivery_mode, status, created_at, updated_at
                    FROM player_listing
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()

    listings = []
    for row in rows:
        listings.append(
            {
                "id": int(row[0]),
                "seller_discord_id": row[1],
                "buyer_discord_id": row[2],
                "listing_type": row[3],
                "item_classname": row[4],
                "vehicle_label": row[5],
                "vehicle_running": bool(row[6]),
                "quantity": int(row[7]),
                "price": int(row[8]),
                "delivery_mode": row[9],
                "status": row[10],
                "created_at": row[11].isoformat() if row[11] else None,
                "updated_at": row[12].isoformat() if row[12] else None,
            }
        )

    return jsonify(
        {
            "count": len(listings),
            "rows": listings,
            "mode": "read-only",
        }
    )


@app.get("/market/listings/<int:listing_id>")
def market_listing_detail(listing_id: int):
    service = _market_service()
    with service._connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, seller_discord_id, buyer_discord_id, listing_type,
                       item_classname, vehicle_label, vehicle_running, quantity,
                       price, delivery_mode, status, created_at, updated_at, closed_at
                FROM player_listing
                WHERE id = %s
                """,
                (listing_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "listing not found"}), 404

    return jsonify(
        {
            "id": int(row[0]),
            "seller_discord_id": row[1],
            "buyer_discord_id": row[2],
            "listing_type": row[3],
            "item_classname": row[4],
            "vehicle_label": row[5],
            "vehicle_running": bool(row[6]),
            "quantity": int(row[7]),
            "price": int(row[8]),
            "delivery_mode": row[9],
            "status": row[10],
            "created_at": row[11].isoformat() if row[11] else None,
            "updated_at": row[12].isoformat() if row[12] else None,
            "closed_at": row[13].isoformat() if row[13] else None,
            "mode": "read-only",
        }
    )


@app.post("/market/listings/preview")
def market_listing_preview():
    payload = request.get_json(silent=True) or {}
    listing_type = (payload.get("listing_type") or "").strip().upper()
    item_classname = payload.get("item_classname")
    vehicle_label = payload.get("vehicle_label")
    vehicle_running = bool(payload.get("vehicle_running", True))
    quantity = int(payload.get("quantity") or 0)
    price = int(payload.get("price") or 0)

    errors = []
    if listing_type not in {"ITEM", "VEHICLE"}:
        errors.append("listing_type must be ITEM or VEHICLE")
    if quantity <= 0:
        errors.append("quantity must be > 0")
    if price <= 0:
        errors.append("price must be > 0")
    if listing_type == "VEHICLE" and not vehicle_running:
        errors.append("non-running vehicles cannot be listed")

    return jsonify(
        {
            "mode": "dry-run",
            "delivery_mode": "P2P_PHYSICAL",
            "listing_type": listing_type,
            "item_classname": item_classname,
            "vehicle_label": vehicle_label,
            "vehicle_running": vehicle_running,
            "quantity": quantity,
            "price": price,
            "valid": len(errors) == 0,
            "errors": errors,
            "spawn_behavior": "not-supported",
            "applied": False,
        }
    )


@app.get("/market/escrow/<int:escrow_id>")
def market_escrow_status(escrow_id: int):
    service = _market_service()
    with service._connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, listing_id, seller_discord_id, buyer_discord_id,
                       amount, status, pickup_confirmed_by_buyer, pickup_confirmed_at,
                       dispute_reason, created_at, updated_at
                FROM market_escrow
                WHERE id = %s
                """,
                (escrow_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "escrow not found"}), 404

    return jsonify(
        {
            "id": int(row[0]),
            "listing_id": int(row[1]),
            "seller_discord_id": row[2],
            "buyer_discord_id": row[3],
            "amount": int(row[4]),
            "status": row[5],
            "pickup_confirmed_by_buyer": bool(row[6]),
            "pickup_confirmed_at": row[7].isoformat() if row[7] else None,
            "dispute_reason": row[8],
            "created_at": row[9].isoformat() if row[9] else None,
            "updated_at": row[10].isoformat() if row[10] else None,
            "mode": "read-only",
        }
    )


@app.get("/market/escrow/<int:escrow_id>/timeline")
def market_escrow_timeline(escrow_id: int):
    service = _market_service()
    with service._connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_type, actor_discord_id, details, created_at
                FROM market_escrow_event
                WHERE escrow_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (escrow_id,),
            )
            rows = cur.fetchall()

    events = []
    for row in rows:
        events.append(
            {
                "id": int(row[0]),
                "event_type": row[1],
                "actor_discord_id": row[2],
                "details": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
            }
        )

    return jsonify(
        {
            "escrow_id": escrow_id,
            "count": len(events),
            "rows": events,
            "mode": "read-only",
        }
    )


@app.get("/autotrader/products")
def autotrader_products():
    limit = max(1, min(int(request.args.get("limit", "25") or "25"), 200))
    service = _autotrader_service()
    rows = service.list_products(enabled_only=True, limit=limit)

    return jsonify(
        {
            "count": len(rows),
            "rows": rows,
            "mode": "read-only",
            "domain": "autotrader",
        }
    )


@app.post("/autotrader/orders/preview")
def autotrader_order_preview():
    payload = request.get_json(silent=True) or {}
    product_id = int(payload.get("product_id") or 0)
    quantity = int(payload.get("quantity") or 0)

    service = _autotrader_service()
    out = service.preview_order(product_id=product_id, quantity=quantity)
    out["domain"] = "autotrader"
    return jsonify(out)


@app.get("/autotrader/orders")
def autotrader_orders():
    buyer_discord_id = request.args.get("buyer_discord_id")
    limit = max(1, min(int(request.args.get("limit", "25") or "25"), 200))
    service = _autotrader_service()
    rows = service.list_orders(buyer_discord_id=buyer_discord_id, limit=limit)

    return jsonify(
        {
            "count": len(rows),
            "rows": rows,
            "mode": "read-only",
            "domain": "autotrader",
        }
    )


@app.get("/autotrader/orders/<int:order_id>")
def autotrader_order_detail(order_id: int):
    service = _autotrader_service()
    try:
        order = service.get_order(order_id)
    except Exception:
        return jsonify({"error": "order not found"}), 404

    return jsonify(
        {
            "order": order,
            "mode": "read-only",
            "domain": "autotrader",
        }
    )


@app.get("/autotrader/orders/<int:order_id>/history")
def autotrader_order_history(order_id: int):
    service = _autotrader_service()
    events = service.list_order_events(order_id)
    return jsonify(
        {
            "order_id": order_id,
            "count": len(events),
            "rows": events,
            "mode": "read-only",
            "domain": "autotrader",
        }
    )


@app.get("/autotrader/scheduler/requests")
@moderator_or_higher(message="moderator role is required for scheduler workspace")
def autotrader_scheduler_requests():
    limit = max(1, min(int(request.args.get("limit", "25") or "25"), 200))
    service = _scheduler_service()
    rows = service.list_requests(limit=limit)
    for row in rows:
        row["enqueue_at"] = row["enqueue_at"].isoformat() if row["enqueue_at"] else None
        row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None
        row["updated_at"] = row["updated_at"].isoformat() if row["updated_at"] else None

    return jsonify(
        {
            "count": len(rows),
            "rows": rows,
            "mode": "read-only",
            "domain": "autotrader_scheduler",
        }
    )


@app.get("/autotrader/scheduler/orders/<int:order_id>/status")
@moderator_or_higher(message="moderator role is required for scheduler workspace")
def autotrader_scheduler_order_status(order_id: int):
    service = _scheduler_service()
    request_row = service.get_request_for_order(order_id)
    if not request_row:
        return jsonify({"error": "scheduler request not found"}), 404

    attempts = service.list_attempts(order_id=order_id, limit=20)
    alerts = service.list_alerts(order_id=order_id, limit=20)
    events = service.list_events(order_id=order_id, limit=50)

    request_row["enqueue_at"] = request_row["enqueue_at"].isoformat() if request_row["enqueue_at"] else None
    request_row["created_at"] = request_row["created_at"].isoformat() if request_row["created_at"] else None
    request_row["updated_at"] = request_row["updated_at"].isoformat() if request_row["updated_at"] else None

    for row in attempts:
        row["attempted_at"] = row["attempted_at"].isoformat() if row["attempted_at"] else None

    for row in alerts:
        row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None
        row["acknowledged_at"] = row["acknowledged_at"].isoformat() if row["acknowledged_at"] else None

    for row in events:
        row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None

    return jsonify(
        {
            "order_id": order_id,
            "request": request_row,
            "attempt_count": len(attempts),
            "alert_count": len(alerts),
            "event_count": len(events),
            "attempts": attempts,
            "alerts": alerts,
            "events": events,
            "mode": "read-only",
            "domain": "autotrader_scheduler",
        }
    )


@app.get("/games/sessions")
def game_sessions():
    discord_user_id = request.args.get("discord_user_id")
    limit = max(1, min(int(request.args.get("limit", "25") or "25"), 200))
    service = _game_service()
    rows = service.list_sessions(discord_user_id=discord_user_id, limit=limit)
    for row in rows:
        row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None

    return jsonify(
        {
            "count": len(rows),
            "rows": rows,
            "mode": "read-only",
            "domain": "game_economy",
        }
    )


@app.post("/games/coinflip/preview")
def game_coinflip_preview():
    payload = request.get_json(silent=True) or {}
    pick_value = str(payload.get("pick_value") or "").strip().upper()
    wager_amount = int(payload.get("wager_amount") or 0)
    server_seed = str(payload.get("server_seed") or "").strip()

    if not server_seed:
        return jsonify({"error": "server_seed is required"}), 400
    if wager_amount <= 0:
        return jsonify({"error": "wager_amount must be > 0"}), 400
    if pick_value not in {"HEADS", "TAILS"}:
        return jsonify({"error": "pick_value must be HEADS or TAILS"}), 400

    out = DeterministicCoinFlipEngine.compute_outcome(server_seed=server_seed, pick_value=pick_value)
    payout_amount = wager_amount * 2 if out["is_win"] else 0
    return jsonify(
        {
            "mode": "dry-run",
            "domain": "game_economy",
            "game_code": "COIN_FLIP",
            "pick_value": pick_value,
            "outcome_value": out["outcome_value"],
            "is_win": bool(out["is_win"]),
            "wager_amount": wager_amount,
            "payout_amount": payout_amount,
            "server_seed_hash": out["server_seed_hash"],
            "applied": False,
        }
    )


@app.get("/tasks/progress/<discord_user_id>")
def task_progress(discord_user_id: str):
    limit = max(1, min(int(request.args.get("limit", "25") or "25"), 200))
    service = _task_service()
    rows = service.list_task_progress(discord_user_id=discord_user_id, limit=limit)
    for row in rows:
        row["completed_at"] = row["completed_at"].isoformat() if row["completed_at"] else None
        row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None

    return jsonify(
        {
            "discord_user_id": discord_user_id,
            "count": len(rows),
            "rows": rows,
            "mode": "read-only",
            "domain": "tasks",
        }
    )


@app.get("/achievements/unlocks/<discord_user_id>")
def achievement_unlocks(discord_user_id: str):
    limit = max(1, min(int(request.args.get("limit", "25") or "25"), 200))
    service = _task_service()
    rows = service.list_achievement_unlocks(discord_user_id=discord_user_id, limit=limit)
    for row in rows:
        row["unlocked_at"] = row["unlocked_at"].isoformat() if row["unlocked_at"] else None

    return jsonify(
        {
            "discord_user_id": discord_user_id,
            "count": len(rows),
            "rows": rows,
            "mode": "read-only",
            "domain": "achievements",
        }
    )


@app.get("/missions")
def mission_list():
    limit = max(1, min(int(request.args.get("limit", "25") or "25"), 200))
    service = _mission_service()
    rows = service.list_missions(limit=limit)
    for row in rows:
        row["starts_at"] = row["starts_at"].isoformat() if row["starts_at"] else None
        row["expires_at"] = row["expires_at"].isoformat() if row["expires_at"] else None
        row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None

    return jsonify(
        {
            "count": len(rows),
            "rows": rows,
            "mode": "read-only",
            "domain": "missions",
        }
    )


@app.get("/missions/progress/<discord_user_id>")
def mission_progress(discord_user_id: str):
    limit = max(1, min(int(request.args.get("limit", "25") or "25"), 200))
    service = _mission_service()
    rows = service.list_progress(discord_user_id=discord_user_id, limit=limit)
    for row in rows:
        row["claimed_at"] = row["claimed_at"].isoformat() if row["claimed_at"] else None
        row["updated_at"] = row["updated_at"].isoformat() if row["updated_at"] else None

    return jsonify(
        {
            "discord_user_id": discord_user_id,
            "count": len(rows),
            "rows": rows,
            "mode": "read-only",
            "domain": "missions",
        }
    )


@app.get("/admin/map")
@admin_or_higher(message="admin role is required for map admin workspace")
def admin_map_workspace():
    tool = _normalize_choice(
        request.args.get("tool"),
        allowed=MAP_ALLOWED_TOOLS,
        default="point",
    )
    coord_mode = _normalize_choice(
        request.args.get("coord_mode"),
        allowed=MAP_ALLOWED_COORD_MODES,
        default="world",
    )
    as_role = _request_role_hint() or "admin"

    min_x = _parse_bounded_float(
        request.args.get("min_x"),
        default=MAP_PREVIEW_DEFAULT_MIN,
        minimum=-1000000.0,
        maximum=1000000.0,
    )
    max_x = _parse_bounded_float(
        request.args.get("max_x"),
        default=MAP_PREVIEW_DEFAULT_MAX,
        minimum=-1000000.0,
        maximum=1000000.0,
    )
    min_z = _parse_bounded_float(
        request.args.get("min_z"),
        default=MAP_PREVIEW_DEFAULT_MIN,
        minimum=-1000000.0,
        maximum=1000000.0,
    )
    max_z = _parse_bounded_float(
        request.args.get("max_z"),
        default=MAP_PREVIEW_DEFAULT_MAX,
        minimum=-1000000.0,
        maximum=1000000.0,
    )

    errors: list[str] = []
    if max_x <= min_x:
        errors.append("max_x must be greater than min_x")
        max_x = min_x + 1.0
    if max_z <= min_z:
        errors.append("max_z must be greater than min_z")
        max_z = min_z + 1.0

    raw_x = request.args.get("x", "")
    raw_z = request.args.get("z", "")
    raw_x2 = request.args.get("x2", "")
    raw_z2 = request.args.get("z2", "")

    point_input = _map_parse_optional_pair(raw_x, raw_z, label="Primary point", errors=errors)
    secondary_input = _map_parse_optional_pair(raw_x2, raw_z2, label="Secondary point", errors=errors)

    marker_rows: list[dict[str, object]] = []
    region_preview: dict[str, object] | None = None
    applied_preview = False

    def to_world_pair(pair: tuple[float, float]) -> tuple[float, float]:
        if coord_mode == "normalized":
            x_norm = max(0.0, min(pair[0], 1.0))
            z_norm = max(0.0, min(pair[1], 1.0))
            return (min_x + (max_x - min_x) * x_norm, min_z + (max_z - min_z) * z_norm)
        return pair

    def append_marker(label: str, world_x: float, world_z: float) -> None:
        normalized_x = _map_normalize(world_x, minimum=min_x, maximum=max_x)
        normalized_z = _map_normalize(world_z, minimum=min_z, maximum=max_z)
        marker_rows.append(
            {
                "label": label,
                "world_x": round(world_x, 3),
                "world_z": round(world_z, 3),
                "normalized_x": round(normalized_x, 6),
                "normalized_z": round(normalized_z, 6),
                "percent_x": round(normalized_x * 100.0, 2),
                "percent_z": round(normalized_z * 100.0, 2),
                "quadrant": _map_quadrant(normalized_x=normalized_x, normalized_z=normalized_z),
                "grid_key": f"{int(normalized_x * 10)}:{int(normalized_z * 10)}",
            }
        )

    if point_input is not None and not errors:
        point_world = to_world_pair(point_input)
        append_marker("Point A", point_world[0], point_world[1])
        applied_preview = True

    if tool == "region" and secondary_input is not None and not errors:
        if point_input is None:
            errors.append("Region preview requires Primary point values")
        else:
            secondary_world = to_world_pair(secondary_input)
            append_marker("Point B", secondary_world[0], secondary_world[1])
            first = marker_rows[0]
            second = marker_rows[1]
            x1 = float(first["world_x"])
            z1 = float(first["world_z"])
            x2 = float(second["world_x"])
            z2 = float(second["world_z"])
            region_preview = {
                "min_x": round(min(x1, x2), 3),
                "max_x": round(max(x1, x2), 3),
                "min_z": round(min(z1, z2), 3),
                "max_z": round(max(z1, z2), 3),
                "width": round(abs(x2 - x1), 3),
                "height": round(abs(z2 - z1), 3),
                "center_x": round((x1 + x2) / 2.0, 3),
                "center_z": round((z1 + z2) / 2.0, 3),
            }
            applied_preview = True

    progress_hint = _map_workspace_progress_hint()
    return render_template(
        "admin_map.html",
        as_role=as_role,
        auth_error="",
        tool=tool,
        coord_mode=coord_mode,
        min_x=min_x,
        max_x=max_x,
        min_z=min_z,
        max_z=max_z,
        raw_x=raw_x,
        raw_z=raw_z,
        raw_x2=raw_x2,
        raw_z2=raw_z2,
        marker_rows=marker_rows,
        region_preview=region_preview,
        applied_preview=applied_preview,
        errors=errors,
        progress_hint=progress_hint,
    )


@app.get("/admin/operations")
@admin_or_higher(message="admin role is required for operations workspace")
def admin_operations_workspace():
    limit = _parse_bounded_int(request.args.get("limit"), default=OPS_PAGE_SIZE, minimum=1, maximum=OPS_MAX_PAGE_SIZE)
    moderation_page = _parse_bounded_int(request.args.get("moderation_page"), default=1, minimum=1, maximum=100000)
    ticket_page = _parse_bounded_int(request.args.get("ticket_page"), default=1, minimum=1, maximum=100000)
    scheduler_page = _parse_bounded_int(request.args.get("scheduler_page"), default=1, minimum=1, maximum=100000)

    target_discord_id = (request.args.get("target_discord_id") or "").strip()
    moderation_action = _normalize_choice(
        request.args.get("moderation_action"),
        allowed=OPS_ALLOWED_MODERATION_ACTIONS,
        default="",
    )
    ticket_status = _normalize_choice(
        request.args.get("ticket_status"),
        allowed=OPS_ALLOWED_TICKET_STATUS,
        default="",
    )
    delivery_state = _normalize_choice(
        request.args.get("delivery_state"),
        allowed=OPS_ALLOWED_DELIVERY_STATES,
        default="",
    )

    moderation_rows, moderation_has_next, moderation_error = _ops_fetch_moderation_rows(
        target_discord_id=target_discord_id,
        moderation_action=moderation_action,
        limit=limit,
        offset=(moderation_page - 1) * limit,
    )
    ticket_rows, ticket_has_next, ticket_error = _ops_fetch_ticket_rows(
        ticket_status=ticket_status,
        limit=limit,
        offset=(ticket_page - 1) * limit,
    )
    scheduler_rows, scheduler_has_next, scheduler_error = _ops_fetch_scheduler_rows(
        delivery_state=delivery_state,
        limit=limit,
        offset=(scheduler_page - 1) * limit,
    )

    summary = _ops_fetch_summary_counts()
    feature_flags = _ops_feature_flags()
    as_role = _request_role_hint() or "admin"
    moderation_has_prev = moderation_page > 1
    ticket_has_prev = ticket_page > 1
    scheduler_has_prev = scheduler_page > 1

    base_query = {
        "as_role": as_role,
        "limit": limit,
        "target_discord_id": target_discord_id,
        "moderation_action": moderation_action,
        "ticket_status": ticket_status,
        "delivery_state": delivery_state,
        "moderation_page": moderation_page,
        "ticket_page": ticket_page,
        "scheduler_page": scheduler_page,
    }

    moderation_summary = _ops_section_summary(
        shown=len(moderation_rows),
        page=moderation_page,
        limit=limit,
        has_prev=moderation_has_prev,
        has_next=moderation_has_next,
        error=moderation_error,
        row_label="Moderation rows",
    )
    ticket_summary = _ops_section_summary(
        shown=len(ticket_rows),
        page=ticket_page,
        limit=limit,
        has_prev=ticket_has_prev,
        has_next=ticket_has_next,
        error=ticket_error,
        row_label="Ticket rows",
    )
    scheduler_summary = _ops_section_summary(
        shown=len(scheduler_rows),
        page=scheduler_page,
        limit=limit,
        has_prev=scheduler_has_prev,
        has_next=scheduler_has_next,
        error=scheduler_error,
        row_label="Scheduler rows",
    )

    return render_template(
        "admin_operations.html",
        is_admin_actor=True,
        as_role=as_role,
        auth_error="",
        active_filters={
            "target_discord_id": bool(target_discord_id),
            "moderation_action": bool(moderation_action),
            "ticket_status": bool(ticket_status),
            "delivery_state": bool(delivery_state),
        },
        summary=summary,
        env_rows=_ops_env_presence_rows(),
        feature_flags=feature_flags,
        moderation_summary=moderation_summary,
        moderation_rows=moderation_rows,
        moderation_error=moderation_error,
        moderation_has_prev=moderation_has_prev,
        moderation_has_next=moderation_has_next,
        moderation_prev_url=_ops_build_url(base_query, moderation_page=moderation_page - 1),
        moderation_next_url=_ops_build_url(base_query, moderation_page=moderation_page + 1),
        ticket_summary=ticket_summary,
        ticket_rows=ticket_rows,
        ticket_error=ticket_error,
        ticket_has_prev=ticket_has_prev,
        ticket_has_next=ticket_has_next,
        ticket_prev_url=_ops_build_url(base_query, ticket_page=ticket_page - 1),
        ticket_next_url=_ops_build_url(base_query, ticket_page=ticket_page + 1),
        scheduler_summary=scheduler_summary,
        scheduler_rows=scheduler_rows,
        scheduler_error=scheduler_error,
        scheduler_has_prev=scheduler_has_prev,
        scheduler_has_next=scheduler_has_next,
        scheduler_prev_url=_ops_build_url(base_query, scheduler_page=scheduler_page - 1),
        scheduler_next_url=_ops_build_url(base_query, scheduler_page=scheduler_page + 1),
        limit=limit,
        target_discord_id=target_discord_id,
        moderation_action=moderation_action,
        ticket_status=ticket_status,
        delivery_state=delivery_state,
        moderation_page=moderation_page,
        ticket_page=ticket_page,
        scheduler_page=scheduler_page,
    )


@app.route("/")
def dashboard():
    db = _db_check()
    return render_template("dashboard.html", db=db)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
