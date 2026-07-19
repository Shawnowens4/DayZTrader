# Phase 1 Changes

## Overview

Phase 1 is a **zero-runtime-impact scaffold**.
No existing file was modified. No startup behavior changed.
No bot restart or Flask restart required.

---

## Files Created

| File | Type | Purpose |
|---|---|---|
| `db/migrations/001_base.sql` | New | Exact snapshot of `db/schema.sql` at Phase 1. Migration baseline. |
| `db/migrations/002_new_systems.sql` | New | 13 new scaffold tables via `CREATE TABLE IF NOT EXISTS`. |
| `db/migrate.py` | New | Manual migration runner. Never auto-called. |
| `bot/services/idb.py` | New | `IDBService` stub. Phase 2 fills implementation. |
| `bot/services/xml_parser.py` | New | `XMLParserService` stub + data classes. Phase 2 fills implementation. |
| `bot/services/nitrado_monitor.py` | New | `MonitorState`, `MonitorEvent`, `MonitorConfig` definitions only. Phase 7 fills implementation. |
| `tests/__init__.py` | New | Test package marker. |
| `tests/test_schema.py` | New | Characterization tests — pins existing 13-table schema. |
| `tests/test_economy.py` | New | Characterization tests — pins `EconomyService` exact behavior. |
| `tests/test_migration.py` | New | Verifies 001 + 002 are safe on fresh and populated DBs. |
| `tests/verify_services_load.py` | New | Import smoke test for all existing + new stub services. |
| `PHASE1_CHANGES.md` | New | This file. |

---

## Files Extended (Append-Only)

| File | What was appended |
|---|---|
| `config/settings.yaml` | New sections: `nitrado_monitor`, `web_player`, `idb`, `vehicle_builder`, `features` — all feature-flagged off. |
| `.env.example` | Commented-out Phase 1+ placeholder variables only. No parseable new vars. |
| `requirements.txt` | `pytest>=7.4.0` and `pytest-asyncio>=0.23.0` (test-only). |

---

## Files Untouched

Every existing runtime file is byte-for-byte identical after Phase 1:

```
main.py                         SHA: 2eeca7e
web/app.py                      SHA: ebe885e
db/init_db.py                   SHA: 7a70126
db/schema.sql                   SHA: ff21f23
bot/cogs/trader.py              SHA: 5562eda
bot/cogs/admin.py               SHA: e2bc492
bot/cogs/casino.py              SHA: fab1f85
bot/cogs/market.py              SHA: ac70db9
bot/cogs/raffle.py              SHA: a892c0b
bot/services/economy.py         SHA: a492609
bot/services/shop.py            SHA: 4150778
bot/services/market.py          SHA: 203c54e
bot/services/delivery.py        SHA: 076ab15
bot/services/delivery_queue.py  SHA: f5f0e5f
bot/services/raffle.py          SHA: 0bd0a33
bot/services/security.py        SHA: 90430d1
bot/services/casino.py          SHA: 76ce7d4  (flagged dead code — delete pending your approval)
cloudflared/tunnel.yml          SHA: e69b9a3
.gitignore                      SHA: 1edd112
README.md                       SHA: 19d0a4b
manage.ps1                      SHA: d39ed40
setup.ps1                       SHA: 7fe2eec
```

---

## ⚠️ Pre-Existing Bug: DB Path Split (NOT fixed in Phase 1)

Two DB paths exist in the current codebase and they do not agree:

```
db/init_db.py   -> db/dayz_trader.db  (via DB_PATH env var, overridable)
economy.py      -> db/trader.db       (hardcoded, NOT overridable)
```

This means:
- If only `init_db.py` has been run, `economy.py` connects to an empty or missing file.
- If only `economy.py`'s path has been initialized, `init_db.py` creates a second separate DB.
- `db/migrate.py` defaults to `db/dayz_trader.db` to match `init_db.py`.

**Phase 1 does not change either path.**
`tests/test_economy.py` patches `svc.db_path` at test time to avoid this.

**Required fix in Phase 2:**
- Remove the hardcoded path from `economy.py.__init__()`.
- Accept `db_path` as a constructor argument with default from `DB_PATH` env var.
- Update all `EconomyService` instantiation sites to pass the resolved path.
- Run both `init_db.py` and `migrate.py` against the same single DB file.
- Verify `test_economy.py`, `test_schema.py`, and `test_migration.py` all pass
  against the same DB path before merging Phase 2.

---

## Table Count Summary

| State | Count |
|---|---|
| Base tables (`db/schema.sql`) | 13 |
| New tables (`002_new_systems.sql`) | 13 |
| Total after both migrations | 26 |

`002_new_systems.sql` is **not applied automatically**.
Run manually after dev testing: `python db/migrate.py`

---

## Test Commands

```bash
# Install test deps first (if not already installed)
pip install pytest pytest-asyncio

# Schema characterization (structure only — does not require live DB)
pytest tests/test_schema.py -v

# EconomyService characterization (uses isolated tmp DB)
pytest tests/test_economy.py -v

# Migration safety tests (uses isolated tmp DBs)
pytest tests/test_migration.py -v

# Service import smoke test
python tests/verify_services_load.py

# All Phase 1 tests at once
pytest tests/ -v
```

---

## Phase 2 Prerequisites

Before Phase 2 begins:
1. All Phase 1 tests must pass.
2. DB path split bug must be resolved.
3. `bot/services/casino.py` delete must be explicitly approved.
4. `python db/migrate.py` must be run against a dev DB copy and verified.
