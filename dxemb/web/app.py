# =============================================================
# DXEMB Web — app.py  (Epic A4)
# Flask admin panel entry point.
# Routes:
#   GET /         — HTML status dashboard (admin-facing)
#   GET /health   — JSON health check (bot + monitoring use)
# =============================================================
import os
import time

import psycopg2
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://dxemb:dxemb@db:5432/dxemb",
)

TABLES = ["player", "item", "escrow_transaction"]


# ------------------------------------------------------------------
# DB helper — synchronous psycopg2 (Flask is sync; asyncpg is bot-only)
# ------------------------------------------------------------------
def _db_check() -> dict:
    """Run a quick DB ping and table row-count check.
    Returns a dict with status, latency_ms, and per-table counts.
    """
    result = {"ok": False, "latency_ms": None, "tables": {}, "error": None}
    try:
        t0 = time.monotonic()
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        cur = conn.cursor()
        for table in TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            result["tables"][table] = cur.fetchone()[0]
        cur.close()
        conn.close()
        result["latency_ms"] = round((time.monotonic() - t0) * 1000)
        result["ok"] = True
    except Exception as exc:
        result["error"] = str(exc)
    return result


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


# ------------------------------------------------------------------
# GET /  — HTML status dashboard
# ------------------------------------------------------------------
_DASHBOARD_TMPL = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DXEMB Admin — Status</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0f0f0f; color: #d4d4d4; min-height: 100dvh;
      padding: 2rem 1.5rem;
    }
    h1  { font-size: 1.4rem; font-weight: 700; color: #f0f0f0; margin-bottom: 0.25rem; }
    .sub { font-size: 0.8rem; color: #666; margin-bottom: 2rem; }
    .card {
      background: #1a1a1a; border: 1px solid #2a2a2a;
      border-radius: 0.5rem; padding: 1.25rem 1.5rem; margin-bottom: 1rem;
      max-width: 560px;
    }
    .card h2 { font-size: 0.75rem; text-transform: uppercase;
               letter-spacing: 0.08em; color: #666; margin-bottom: 0.75rem; }
    .row { display: flex; justify-content: space-between;
           align-items: center; padding: 0.3rem 0;
           border-bottom: 1px solid #222; font-size: 0.875rem; }
    .row:last-child { border-bottom: none; }
    .label { color: #999; }
    .val   { color: #f0f0f0; font-variant-numeric: tabular-nums; }
    .badge {
      display: inline-block; padding: 0.15rem 0.5rem;
      border-radius: 9999px; font-size: 0.7rem; font-weight: 600;
      letter-spacing: 0.04em; text-transform: uppercase;
    }
    .ok  { background: #14532d; color: #4ade80; }
    .err { background: #450a0a; color: #f87171; }
  </style>
</head>
<body>
  <h1>&#x1F6E1;&#xFE0F; DXEMB Admin Panel</h1>
  <p class="sub">DayZ Xbox Trader — status dashboard</p>

  <div class="card">
    <h2>System</h2>
    <div class="row">
      <span class="label">Web service</span>
      <span class="badge ok">online</span>
    </div>
    <div class="row">
      <span class="label">Database</span>
      <span class="badge {{ 'ok' if db.ok else 'err' }}">
        {{ 'connected' if db.ok else 'error' }}
      </span>
    </div>
    {% if db.ok %}
    <div class="row">
      <span class="label">DB latency</span>
      <span class="val">{{ db.latency_ms }} ms</span>
    </div>
    {% endif %}
    {% if db.error %}
    <div class="row">
      <span class="label">Error</span>
      <span class="val" style="color:#f87171;font-size:0.8rem">{{ db.error }}</span>
    </div>
    {% endif %}
  </div>

  {% if db.ok %}
  <div class="card">
    <h2>Table Row Counts</h2>
    {% for table, count in db.tables.items() %}
    <div class="row">
      <span class="label">{{ table }}</span>
      <span class="val">{{ count }}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}

</body>
</html>
"""


@app.route("/")
def dashboard():
    db = _db_check()
    return render_template_string(_DASHBOARD_TMPL, db=db)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
