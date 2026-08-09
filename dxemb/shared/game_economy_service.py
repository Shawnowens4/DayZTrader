"""Deterministic local-safe game economy service.

Supports a single starter game (coin flip) with auditable deterministic RNG.
Wallet mutation is optional and disabled by default via feature flag.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from psycopg2.extras import Json

from shared.wallet_ledger_service import WalletLedgerService


DEFAULT_DATABASE_URL = "postgresql://dxemb:dxemb@db:5432/dxemb"


class GameEconomyError(Exception):
    """Base game economy error."""


class GameDisabledError(GameEconomyError):
    """Raised when a game feature is disabled."""


class InvalidWagerError(GameEconomyError):
    """Raised when wager or pick are invalid."""


class LivePayoutDisabledError(GameEconomyError):
    """Raised when wallet settlement is disabled by feature flag."""


@dataclass(frozen=True)
class CoinFlipResult:
    session_id: int
    session_reference: str
    game_code: str
    wager_amount: int
    pick_value: str
    outcome_value: str
    is_win: bool
    payout_amount: int
    mode: str
    idempotent: bool


class DeterministicCoinFlipEngine:
    GAME_CODE = "COIN_FLIP"

    @staticmethod
    def generate_server_seed() -> str:
        return secrets.token_hex(16)

    @staticmethod
    def compute_outcome(*, server_seed: str, pick_value: str) -> dict[str, Any]:
        normalized_pick = pick_value.strip().upper()
        if normalized_pick not in {"HEADS", "TAILS"}:
            raise InvalidWagerError("pick_value must be HEADS or TAILS")

        digest = hashlib.sha256(server_seed.encode("utf-8")).hexdigest()
        bit = int(digest[-1], 16) % 2
        outcome_value = "HEADS" if bit == 0 else "TAILS"
        is_win = normalized_pick == outcome_value
        return {
            "outcome_value": outcome_value,
            "is_win": is_win,
            "rng_value": bit,
            "server_seed_hash": digest,
        }


class GameEconomyService:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.wallet = WalletLedgerService(database_url=self.database_url)

    def _connect(self):
        import psycopg2

        return psycopg2.connect(self.database_url, connect_timeout=5)

    def _get_feature_flag(self, cur, game_code: str) -> dict[str, Any]:
        cur.execute(
            """
            SELECT id, is_enabled, allow_live_payout, min_wager, max_wager
            FROM game_feature_flag
            WHERE game_code = %s
            """,
            (game_code,),
        )
        row = cur.fetchone()
        if not row:
            raise GameDisabledError(f"game not configured: {game_code}")
        return {
            "id": int(row[0]),
            "is_enabled": bool(row[1]),
            "allow_live_payout": bool(row[2]),
            "min_wager": int(row[3]),
            "max_wager": int(row[4]),
        }

    def set_feature_flag(
        self,
        *,
        game_code: str,
        is_enabled: bool,
        allow_live_payout: bool,
        min_wager: int,
        max_wager: int,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO game_feature_flag (
                        game_code,
                        is_enabled,
                        allow_live_payout,
                        min_wager,
                        max_wager
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (game_code)
                    DO UPDATE SET
                        is_enabled = EXCLUDED.is_enabled,
                        allow_live_payout = EXCLUDED.allow_live_payout,
                        min_wager = EXCLUDED.min_wager,
                        max_wager = EXCLUDED.max_wager,
                        updated_at = NOW()
                    """,
                    (game_code, is_enabled, allow_live_payout, min_wager, max_wager),
                )

    def play_coin_flip(
        self,
        *,
        discord_user_id: str,
        wager_amount: int,
        pick_value: str,
        idempotency_key: str,
        actor_discord_id: str,
        mode: str = "dry-run",
    ) -> CoinFlipResult:
        if wager_amount <= 0:
            raise InvalidWagerError("wager_amount must be > 0")
        if mode not in {"dry-run", "wallet-settle"}:
            raise InvalidWagerError("mode must be dry-run or wallet-settle")

        self.wallet.ensure_player(discord_user_id)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, session_reference, game_code, wager_amount, pick_value,
                           outcome_value, is_win, payout_amount, mode
                    FROM game_session
                    WHERE discord_user_id = %s
                      AND game_code = %s
                      AND idempotency_key = %s
                    """,
                    (discord_user_id, DeterministicCoinFlipEngine.GAME_CODE, idempotency_key),
                )
                existing = cur.fetchone()
                if existing:
                    return CoinFlipResult(
                        session_id=int(existing[0]),
                        session_reference=existing[1],
                        game_code=existing[2],
                        wager_amount=int(existing[3]),
                        pick_value=existing[4],
                        outcome_value=existing[5],
                        is_win=bool(existing[6]),
                        payout_amount=int(existing[7]),
                        mode=existing[8],
                        idempotent=True,
                    )

                flag = self._get_feature_flag(cur, DeterministicCoinFlipEngine.GAME_CODE)
                if not flag["is_enabled"]:
                    raise GameDisabledError("coin flip is disabled")
                if wager_amount < flag["min_wager"] or wager_amount > flag["max_wager"]:
                    raise InvalidWagerError(
                        f"wager_amount must be between {flag['min_wager']} and {flag['max_wager']}"
                    )

                normalized_pick = pick_value.strip().upper()
                server_seed = DeterministicCoinFlipEngine.generate_server_seed()
                deterministic = DeterministicCoinFlipEngine.compute_outcome(
                    server_seed=server_seed,
                    pick_value=normalized_pick,
                )
                payout_multiplier = Decimal("2.0") if deterministic["is_win"] else Decimal("0")
                payout_amount = int(Decimal(wager_amount) * payout_multiplier)

                debit_reference_id = None
                payout_reference_id = None
                debit_ledger_id = None
                payout_ledger_id = None

                if mode == "wallet-settle":
                    if not flag["allow_live_payout"]:
                        raise LivePayoutDisabledError("wallet settlement is disabled for coin flip")

                    debit_reference_id = f"GAME_WAGER:{DeterminsticRef.build(discord_user_id, idempotency_key)}"
                    debit = self.wallet.debit(
                        discord_user_id=discord_user_id,
                        amount=wager_amount,
                        reference_type="GAME_WAGER",
                        reference_id=debit_reference_id,
                        reason_code="COIN_FLIP_WAGER",
                        actor_discord_id=actor_discord_id,
                        metadata={"game_code": DeterministicCoinFlipEngine.GAME_CODE},
                    )
                    debit_ledger_id = debit.ledger_id

                    if payout_amount > 0:
                        payout_reference_id = f"GAME_PAYOUT:{DeterminsticRef.build(discord_user_id, idempotency_key)}"
                        payout = self.wallet.credit(
                            discord_user_id=discord_user_id,
                            amount=payout_amount,
                            reference_type="GAME_PAYOUT",
                            reference_id=payout_reference_id,
                            reason_code="COIN_FLIP_PAYOUT",
                            actor_discord_id=actor_discord_id,
                            metadata={"game_code": DeterministicCoinFlipEngine.GAME_CODE},
                        )
                        payout_ledger_id = payout.ledger_id

                session_reference = f"GAME:{discord_user_id}:{idempotency_key}"
                cur.execute(
                    """
                    INSERT INTO game_session (
                        session_reference,
                        discord_user_id,
                        game_code,
                        feature_flag_id,
                        idempotency_key,
                        wager_amount,
                        pick_value,
                        outcome_value,
                        is_win,
                        payout_multiplier,
                        payout_amount,
                        server_seed,
                        server_seed_hash,
                        rng_algorithm,
                        rng_value,
                        debit_reference_id,
                        payout_reference_id,
                        debit_ledger_id,
                        payout_ledger_id,
                        mode,
                        metadata
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        session_reference,
                        discord_user_id,
                        DeterministicCoinFlipEngine.GAME_CODE,
                        flag["id"],
                        idempotency_key,
                        wager_amount,
                        normalized_pick,
                        deterministic["outcome_value"],
                        deterministic["is_win"],
                        payout_multiplier,
                        payout_amount,
                        server_seed,
                        deterministic["server_seed_hash"],
                        "sha256_mod2",
                        deterministic["rng_value"],
                        debit_reference_id,
                        payout_reference_id,
                        debit_ledger_id,
                        payout_ledger_id,
                        mode,
                        Json({"actor_discord_id": actor_discord_id}),
                    ),
                )
                session_id = int(cur.fetchone()[0])

                return CoinFlipResult(
                    session_id=session_id,
                    session_reference=session_reference,
                    game_code=DeterministicCoinFlipEngine.GAME_CODE,
                    wager_amount=wager_amount,
                    pick_value=normalized_pick,
                    outcome_value=deterministic["outcome_value"],
                    is_win=bool(deterministic["is_win"]),
                    payout_amount=payout_amount,
                    mode=mode,
                    idempotent=False,
                )

    def list_sessions(self, *, discord_user_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as conn:
            with conn.cursor() as cur:
                if discord_user_id:
                    cur.execute(
                        """
                        SELECT id, session_reference, discord_user_id, game_code, wager_amount,
                               pick_value, outcome_value, is_win, payout_amount, mode, created_at
                        FROM game_session
                        WHERE discord_user_id = %s
                        ORDER BY created_at DESC, id DESC
                        LIMIT %s
                        """,
                        (discord_user_id, safe_limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, session_reference, discord_user_id, game_code, wager_amount,
                               pick_value, outcome_value, is_win, payout_amount, mode, created_at
                        FROM game_session
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
                    "session_reference": row[1],
                    "discord_user_id": row[2],
                    "game_code": row[3],
                    "wager_amount": int(row[4]),
                    "pick_value": row[5],
                    "outcome_value": row[6],
                    "is_win": bool(row[7]),
                    "payout_amount": int(row[8]),
                    "mode": row[9],
                    "created_at": row[10],
                }
            )
        return out


class DeterminsticRef:
    @staticmethod
    def build(discord_user_id: str, idempotency_key: str) -> str:
        return f"{discord_user_id}:{idempotency_key}"
