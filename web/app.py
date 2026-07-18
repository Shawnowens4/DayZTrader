"""
DayZ Trader Bot - Flask Web API & Dashboard
All endpoints require X-API-Key header (except public map/status)
"""

import os
import json
import sqlite3
from functools import wraps
from datetime import datetime
from flask import Flask, jsonify, request, render_template, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "60 per minute"])

API_KEY  = os.getenv("WEB_API_KEY", "changeme")
DB_PATH  = os.path.join(os.path.dirname(__file__), "..", "db", "trader.db")


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

def row_to_dict(row):
    return dict(row) if row else None


# ── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/map")
def map_page():
    return render_template("map.html")


# ── Status (public) ──────────────────────────────────────────────────────────

@app.route("/api/status")
def status():
    return jsonify({"status": "online", "timestamp": datetime.utcnow().isoformat()})


# ── Economy ──────────────────────────────────────────────────────────────────

@app.route("/api/economy/balances")
@require_api_key
def get_balances():
    page     = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    offset   = (page - 1) * per_page
    with get_db() as db:
        rows = db.execute(
            "SELECT discord_id, username, balance, total_earned, total_spent FROM users "
            "ORDER BY balance DESC LIMIT ? OFFSET ?", (per_page, offset)
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])

@app.route("/api/economy/adjust", methods=["POST"])
@require_api_key
def adjust_balance():
    data       = request.get_json()
    discord_id = data.get("discord_id")
    amount     = data.get("amount")
    reason     = data.get("reason", "Admin adjustment")
    if not discord_id or amount is None:
        return jsonify({"error": "discord_id and amount required"}), 400
    with get_db() as db:
        db.execute("UPDATE users SET balance = balance + ? WHERE discord_id = ?", (amount, discord_id))
        db.execute(
            "INSERT INTO audit_log (trade_type, actor_id, target_id, amount, notes) VALUES (?,?,?,?,?)",
            ("admin_adjust", 0, discord_id, amount, reason)
        )
        db.commit()
    return jsonify({"success": True})

@app.route("/api/economy/transactions")
@require_api_key
def get_transactions():
    discord_id = request.args.get("discord_id")
    limit      = int(request.args.get("limit", 50))
    with get_db() as db:
        if discord_id:
            rows = db.execute(
                "SELECT * FROM transactions WHERE discord_id=? ORDER BY created_at DESC LIMIT ?",
                (discord_id, limit)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


# ── Shop ─────────────────────────────────────────────────────────────────────

@app.route("/api/shop/items", methods=["GET"])
def list_items():
    category = request.args.get("category")
    with get_db() as db:
        if category:
            rows = db.execute("SELECT * FROM shop_items WHERE enabled=1 AND category=? ORDER BY price", (category,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM shop_items WHERE enabled=1 ORDER BY category, price").fetchall()
    return jsonify([row_to_dict(r) for r in rows])

@app.route("/api/shop/items", methods=["POST"])
@require_api_key
def create_item():
    data = request.get_json()
    required = ["item_id", "class_name", "display_name", "price"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {required}"}), 400
    with get_db() as db:
        db.execute(
            "INSERT INTO shop_items (item_id, class_name, display_name, price, category, "
            "is_bundle, bundle_data, bundle_discount, stock, enabled, admin_only, description, created_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                data["item_id"], data["class_name"], data["display_name"], data["price"],
                data.get("category", "misc"), int(data.get("is_bundle", False)),
                json.dumps(data.get("bundle_data")) if data.get("bundle_data") else None,
                data.get("bundle_discount", 0), data.get("stock", -1),
                int(data.get("enabled", True)), int(data.get("admin_only", False)),
                data.get("description"), data.get("created_by")
            )
        )
        db.commit()
    return jsonify({"success": True, "item_id": data["item_id"]}), 201

@app.route("/api/shop/items/<item_id>", methods=["PATCH"])
@require_api_key
def update_item(item_id):
    data    = request.get_json()
    allowed = ["price", "stock", "enabled", "display_name", "description", "category", "admin_only"]
    sets    = ", ".join(f"{k}=?" for k in data if k in allowed)
    vals    = [data[k] for k in data if k in allowed] + [item_id]
    if not sets:
        return jsonify({"error": "No valid fields to update"}), 400
    with get_db() as db:
        db.execute(f"UPDATE shop_items SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE item_id=?", vals)
        db.commit()
    return jsonify({"success": True})

@app.route("/api/shop/items/<item_id>", methods=["DELETE"])
@require_api_key
def delete_item(item_id):
    with get_db() as db:
        db.execute("UPDATE shop_items SET enabled=0 WHERE item_id=?", (item_id,))
        db.commit()
    return jsonify({"success": True})


# ── Market ───────────────────────────────────────────────────────────────────

@app.route("/api/market/listings", methods=["GET"])
def get_listings():
    status = request.args.get("status", "pending")
    with get_db() as db:
        rows = db.execute(
            "SELECT l.*, u.username as seller_name FROM market_listings l "
            "LEFT JOIN users u ON l.seller_id=u.discord_id "
            "WHERE l.status=? ORDER BY l.created_at DESC", (status,)
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])

@app.route("/api/market/listings/<listing_id>/confirm", methods=["POST"])
@require_api_key
def confirm_delivery(listing_id):
    with get_db() as db:
        db.execute("UPDATE market_listings SET status='delivered' WHERE listing_id=?", (listing_id,))
        listing = db.execute("SELECT * FROM market_listings WHERE listing_id=?", (listing_id,)).fetchone()
        if listing and listing["escrow_held"] > 0:
            db.execute("UPDATE users SET balance=balance+? WHERE discord_id=?",
                       (listing["escrow_held"], listing["seller_id"]))
        db.execute(
            "INSERT INTO audit_log (trade_type, item_ref, amount, notes) VALUES (?,?,?,?)",
            ("delivery_confirmed", listing_id, listing["escrow_held"] if listing else 0, "Admin confirmed via web")
        )
        db.commit()
    return jsonify({"success": True})

@app.route("/api/market/listings/<listing_id>/dispute", methods=["POST"])
@require_api_key
def resolve_dispute(listing_id):
    data       = request.get_json()
    resolution = data.get("resolution", "refunded")
    with get_db() as db:
        listing = db.execute("SELECT * FROM market_listings WHERE listing_id=?", (listing_id,)).fetchone()
        if listing and resolution == "refunded" and listing["escrow_held"] > 0:
            db.execute("UPDATE users SET balance=balance+? WHERE discord_id=?",
                       (listing["escrow_held"], listing["buyer_id"]))
        db.execute("UPDATE market_listings SET status='cancelled' WHERE listing_id=?", (listing_id,))
        db.execute("UPDATE market_disputes SET resolved=1, resolution=? WHERE listing_id=?",
                   (resolution, listing_id))
        db.commit()
    return jsonify({"success": True})


# ── Delivery ─────────────────────────────────────────────────────────────────

@app.route("/api/delivery/queue", methods=["GET"])
@require_api_key
def get_delivery_queue():
    status = request.args.get("status", "pending")
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM delivery_queue WHERE status=? ORDER BY queued_at ASC", (status,)
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])

@app.route("/api/delivery/zones", methods=["GET"])
def get_zones():
    with get_db() as db:
        rows = db.execute("SELECT * FROM delivery_zones WHERE enabled=1").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


# ── Raffle ───────────────────────────────────────────────────────────────────

@app.route("/api/raffle/current", methods=["GET"])
def get_current_raffle():
    with get_db() as db:
        row = db.execute("SELECT * FROM raffles WHERE status='open' ORDER BY created_at DESC LIMIT 1").fetchone()
    return jsonify(row_to_dict(row))

@app.route("/api/raffle/start", methods=["POST"])
@require_api_key
def start_raffle():
    data = request.get_json()
    required = ["vehicle", "vehicle_display", "entry_cost", "end_time"]
    if not all(k in data for k in required):
        return jsonify({"error": f"Required: {required}"}), 400
    with get_db() as db:
        from datetime import datetime as dt
        week = dt.utcnow().isocalendar()[1]
        db.execute(
            "INSERT INTO raffles (week_number, vehicle, vehicle_display, entry_cost, max_entries, start_time, end_time, status) "
            "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP,?,?)",
            (week, data["vehicle"], data["vehicle_display"], data["entry_cost"],
             data.get("max_entries", 10), data["end_time"], "open")
        )
        db.commit()
    return jsonify({"success": True}), 201

@app.route("/api/raffle/history", methods=["GET"])
def raffle_history():
    with get_db() as db:
        rows = db.execute("SELECT * FROM raffles ORDER BY created_at DESC LIMIT 20").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


# ── Audit Log ────────────────────────────────────────────────────────────────

@app.route("/api/audit", methods=["GET"])
@require_api_key
def get_audit():
    limit = int(request.args.get("limit", 100))
    ttype = request.args.get("type")
    with get_db() as db:
        if ttype:
            rows = db.execute(
                "SELECT * FROM audit_log WHERE trade_type=? ORDER BY timestamp DESC LIMIT ?", (ttype, limit)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


# ── Casino Stats ─────────────────────────────────────────────────────────────

@app.route("/api/casino/stats", methods=["GET"])
@require_api_key
def casino_stats():
    with get_db() as db:
        rows = db.execute(
            "SELECT u.username, cs.* FROM casino_stats cs "
            "JOIN users u ON cs.discord_id=u.discord_id "
            "ORDER BY cs.total_wagered DESC LIMIT 50"
        ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
