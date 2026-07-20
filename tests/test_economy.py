"""
tests/test_economy.py — Characterization tests for EconomyService.

Pins actual confirmed behavior derived from reading economy.py (SHA a492609).

CONFIRMED FACTS FROM SOURCE:
  - __init__() takes no arguments. DB path is hardcoded.
  - ensure_user(discord_id, username) -> dict (all user columns)
  - get_balance(discord_id) -> int. Returns 0 if user not found (not None).
  - update_balance(discord_id, amount, reason) -> int (new balance).
    Does NOT clamp negative balances. Raw SQL: balance = balance + amount.
    Overdraft is silently permitted.
  - claim_daily(discord_id, username, amount=500) -> dict always.
    On cooldown:  {'success': False, 'message': str}
    On success:   {'success': True, 'amount': int, 'new_balance': int}
  - get_leaderboard(limit=10) -> list[dict] with keys 'username', 'balance',
    ordered DESC by balance.
  - DB resolves to: <project_root>/db/trader.db (hardcoded, not injectable).
    Tests patch svc.db_path after construction to avoid touching live DB.

Usage:
    pytest tests/test_economy.py -v
"""
import asyncio
import sqlite3
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bot.services.economy import EconomyService

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")

UID_A = 111222333444555666
UID_B = 999888777666555444


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def economy(tmp_path):
    """EconomyService wired to a fresh tmp DB. Patches the hardcoded db_path."""
    db_file = str(tmp_path / "test_economy.db")
    with open(SCHEMA_PATH) as f:
        schema = f.read()
    conn = sqlite3.connect(db_file)
    conn.executescript(schema)
    conn.commit()
    conn.close()
    svc = EconomyService()
    svc.db_path = db_file  # patch hardcoded path — works against SHA a492609
    return svc


class TestEnsureUser:
    def test_returns_dict(self, economy):
        result = run(economy.ensure_user(UID_A, "Alice"))
        assert isinstance(result, dict)

    def test_dict_contains_discord_id(self, economy):
        result = run(economy.ensure_user(UID_A, "Alice"))
        assert result["discord_id"] == UID_A

    def test_idempotent_second_call(self, economy):
        run(economy.ensure_user(UID_A, "Alice"))
        result2 = run(economy.ensure_user(UID_A, "Alice"))
        assert result2["discord_id"] == UID_A

    def test_new_user_starts_with_balance_1000(self, economy):
        result = run(economy.ensure_user(UID_A, "Alice"))
        # schema.sql: balance INTEGER DEFAULT 1000
        assert result["balance"] == 1000


class TestGetBalance:
    def test_returns_int(self, economy):
        run(economy.ensure_user(UID_A, "Alice"))
        bal = run(economy.get_balance(UID_A))
        assert isinstance(bal, int)

    def test_nonexistent_user_returns_zero(self, economy):
        # Confirmed: returns row[0] if row else 0
        bal = run(economy.get_balance(9999999999999999))
        assert bal == 0

    def test_matches_ensure_user_balance(self, economy):
        user = run(economy.ensure_user(UID_A, "Alice"))
        bal = run(economy.get_balance(UID_A))
        assert bal == user["balance"]


class TestUpdateBalance:
    def test_add_returns_new_balance(self, economy):
        run(economy.ensure_user(UID_A, "Alice"))
        before = run(economy.get_balance(UID_A))
        result = run(economy.update_balance(UID_A, 500, "test"))
        assert isinstance(result, int)
        assert result == before + 500

    def test_subtract_returns_new_balance(self, economy):
        run(economy.ensure_user(UID_A, "Alice"))
        before = run(economy.get_balance(UID_A))
        result = run(economy.update_balance(UID_A, -200, "test"))
        assert result == before - 200

    def test_overdraft_allowed_silently(self, economy):
        # Confirmed: no clamp, no raise. balance = balance + amount directly.
        run(economy.ensure_user(UID_A, "Alice"))
        start = run(economy.get_balance(UID_A))  # 1000 from schema default
        result = run(economy.update_balance(UID_A, -(start + 500), "overdraft"))
        assert result == start - (start + 500)  # -500
        assert result < 0

    def test_audit_log_entry_created(self, economy):
        run(economy.ensure_user(UID_A, "Alice"))
        run(economy.update_balance(UID_A, 100, "audit_test"))
        conn = sqlite3.connect(economy.db_path)
        row = conn.execute(
            "SELECT trade_type, actor_id, amount, notes FROM audit_log "
            "WHERE notes='audit_test'"
        ).fetchone()
        conn.close()
        assert row is not None, "audit_log row not created"
        assert row[3] == "audit_test"


class TestClaimDaily:
    def test_returns_dict(self, economy):
        run(economy.ensure_user(UID_A, "Alice"))
        result = run(economy.claim_daily(UID_A, "Alice"))
        assert isinstance(result, dict)

    def test_success_keys(self, economy):
        run(economy.ensure_user(UID_A, "Alice"))
        result = run(economy.claim_daily(UID_A, "Alice"))
        assert result["success"] is True
        assert "amount" in result
        assert "new_balance" in result
        assert isinstance(result["amount"], int)
        assert isinstance(result["new_balance"], int)

    def test_default_amount_is_500(self, economy):
        run(economy.ensure_user(UID_A, "Alice"))
        result = run(economy.claim_daily(UID_A, "Alice"))
        assert result["amount"] == 500

    def test_cooldown_on_second_call(self, economy):
        run(economy.ensure_user(UID_A, "Alice"))
        run(economy.claim_daily(UID_A, "Alice"))
        result2 = run(economy.claim_daily(UID_A, "Alice"))
        assert result2["success"] is False
        assert "message" in result2
        assert isinstance(result2["message"], str)


class TestLeaderboard:
    def test_returns_list(self, economy):
        result = run(economy.get_leaderboard())
        assert isinstance(result, list)

    def test_entries_have_username_and_balance(self, economy):
        run(economy.ensure_user(UID_A, "Alice"))
        run(economy.ensure_user(UID_B, "Bob"))
        result = run(economy.get_leaderboard())
        assert len(result) >= 2
        for entry in result:
            assert "username" in entry
            assert "balance" in entry

    def test_ordered_desc_by_balance(self, economy):
        run(economy.ensure_user(UID_A, "Alice"))
        run(economy.ensure_user(UID_B, "Bob"))
        run(economy.update_balance(UID_A, 5000, "seed"))
        result = run(economy.get_leaderboard())
        balances = [r["balance"] for r in result]
        assert balances == sorted(balances, reverse=True)
