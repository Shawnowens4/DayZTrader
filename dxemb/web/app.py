# =============================================================
# DXEMB Web — app.py  (Epic A4 / A9)
# Flask admin panel entry point.
# Routes:
#   GET /         — HTML status dashboard (admin-facing)
#   GET /health   — JSON health check (bot + monitoring use)
# =============================================================
import sys
import os
from pathlib import Path

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
    from web.ui import register_ui_helpers
except ModuleNotFoundError:
    from ui import register_ui_helpers

app = Flask(__name__)
register_ui_helpers(app)
app.register_blueprint(catalog_bp)
app.register_blueprint(wallet_admin_bp)
app.register_blueprint(vehicle_bp)

TABLES = ["player", "item", "escrow_transaction"]


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
    limit = max(1, min(int(request.args.get("limit", "25") or "25"), 200))
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
    amount = int(payload.get("amount") or 0)
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


@app.route("/")
def dashboard():
    db = _db_check()
    return render_template("dashboard.html", db=db)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
