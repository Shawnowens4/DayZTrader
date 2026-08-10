from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

from flask import g, jsonify, request


ROLE_RANKS = {
    "player": 10,
    "moderator": 20,
    "admin": 30,
    "owner": 40,
}

FailHandler = Callable[[str, int], Any]


@dataclass(frozen=True)
class LocalRequestIdentity:
    player_id: str | None
    role: str
    actor_id: str


def _normalize_role(role_hint: str | None) -> str:
    candidate = (role_hint or "").strip().lower()
    return candidate if candidate in ROLE_RANKS else "player"


def _request_value(name: str) -> str:
    return (
        (request.form.get(name) or "").strip()
        or (request.args.get(name) or "").strip()
        or (request.headers.get(name) or "").strip()
    )


def _resolve_player_id() -> tuple[str | None, str | None, int]:
    header_id = (request.headers.get("X-DXEMB-PLAYER-ID") or "").strip()
    query_id = (request.args.get("discord_user_id") or "").strip()
    form_id = (request.form.get("discord_user_id") or "").strip()

    if header_id and query_id and header_id != query_id:
        return None, "header and query identity mismatch", 403
    if header_id and form_id and header_id != form_id:
        return None, "header and form identity mismatch", 403

    resolved = header_id or query_id or form_id or None
    return resolved, None, 200


def resolve_local_identity() -> tuple[LocalRequestIdentity, str | None, int]:
    player_id, err, status = _resolve_player_id()
    role = _normalize_role(_request_value("as_role") or request.headers.get("X-DXEMB-ROLE"))
    actor_id = _request_value("actor_id") or "local_actor"

    identity = LocalRequestIdentity(
        player_id=player_id,
        role=role,
        actor_id=actor_id,
    )
    return identity, err, status


def get_request_role_hint() -> str:
    identity, _, _ = resolve_local_identity()
    return identity.role


def get_resolved_identity() -> LocalRequestIdentity:
    cached = getattr(g, "dxemb_identity", None)
    if cached is not None:
        return cached

    identity, _, _ = resolve_local_identity()
    g.dxemb_identity = identity
    return identity


def has_role(identity: LocalRequestIdentity, minimum_role: str) -> bool:
    required = ROLE_RANKS.get(minimum_role, ROLE_RANKS["admin"])
    current = ROLE_RANKS.get(identity.role, ROLE_RANKS["player"])
    return current >= required


def _handle_auth_failure(message: str, status_code: int, on_fail: FailHandler | None) -> Any:
    if on_fail is not None:
        return on_fail(message, status_code)

    if request.path.startswith("/api/"):
        return jsonify({"error": message}), status_code
    return message, status_code


def authenticated_player(on_fail: FailHandler | None = None):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            identity, err, status = resolve_local_identity()
            if err:
                return _handle_auth_failure(err, status, on_fail)
            if not identity.player_id:
                return _handle_auth_failure(
                    "player identity is required via X-DXEMB-PLAYER-ID or discord_user_id",
                    401,
                    on_fail,
                )
            g.dxemb_identity = identity
            return func(*args, **kwargs)

        return wrapped

    return decorator


def require_role(minimum_role: str, *, message: str | None = None, on_fail: FailHandler | None = None):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            identity, err, status = resolve_local_identity()
            if err:
                return _handle_auth_failure(err, status, on_fail)
            if not has_role(identity, minimum_role):
                fail_message = message or f"{minimum_role} role is required"
                return _handle_auth_failure(fail_message, 403, on_fail)
            g.dxemb_identity = identity
            return func(*args, **kwargs)

        return wrapped

    return decorator


def moderator_or_higher(*, message: str | None = None, on_fail: FailHandler | None = None):
    return require_role("moderator", message=message, on_fail=on_fail)


def admin_or_higher(*, message: str | None = None, on_fail: FailHandler | None = None):
    return require_role("admin", message=message, on_fail=on_fail)
