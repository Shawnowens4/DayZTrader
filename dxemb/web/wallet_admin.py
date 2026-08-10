from __future__ import annotations

import json
from urllib.parse import urlencode

from flask import Blueprint
from flask import abort
from flask import redirect
from flask import render_template
from flask import request

try:
    from web.local_auth import admin_or_higher
    from web.local_auth import get_request_role_hint
    from web.local_auth import get_resolved_identity
    from web.local_auth import has_role
except ModuleNotFoundError:
    from local_auth import admin_or_higher
    from local_auth import get_request_role_hint
    from local_auth import get_resolved_identity
    from local_auth import has_role

from shared.wallet_ledger_service import InvalidAmountError
from shared.wallet_ledger_service import InvalidOwnerError
from shared.wallet_ledger_service import InsufficientFundsError
from shared.wallet_ledger_service import MetadataValidationError
from shared.wallet_ledger_service import WalletLedgerService

wallet_admin_bp = Blueprint("wallet_admin", __name__)

PAGE_SIZE = 25
MAX_PAGE_SIZE = 50
AUTH_NOTICE = "Local admin tooling only. No real authentication or production authorization is implemented in this Flask app."
CAPABILITY_NOTICE = "Virtual credits only. No real-money payment capability, no player purchase flow, and no game-server action occurs here."


def _wallet_service() -> WalletLedgerService:
    return WalletLedgerService()


def _request_role_hint() -> str:
    return get_request_role_hint()


def _is_admin_actor() -> bool:
    return has_role(get_resolved_identity(), "admin")


def _wallet_admin_adjust_auth_error(message: str, status_code: int):
    owner_id = ""
    if request.view_args:
        owner_id = str(request.view_args.get("owner_id") or "")

    service = _wallet_service()
    owner = service.get_wallet_summary(owner_id) if owner_id else None
    if owner is None:
        owner = {
            "account_id": 0,
            "owner_id": owner_id,
            "owner_kind": "LOCAL_PLAYER",
            "owner_label": None,
            "balance_minor": 0,
            "created_at": None,
            "updated_at": None,
            "transaction_count": 0,
            "latest_activity": None,
            "total_credits_minor": 0,
            "total_debits_minor": 0,
            "ledger_net_minor": 0,
            "last_ledger_at": None,
            "recent_reference": None,
        }

    return (
        render_template(
            "wallet_admin_detail.html",
            owner=owner,
            history=[],
            direction="all",
            status="all",
            entry_type="",
            reference_query="",
            created_after="",
            created_before="",
            page=1,
            limit=PAGE_SIZE,
            has_next=False,
            reconciliation={
                "owner_id": owner_id,
                "account_balance_minor": 0,
                "ledger_total_minor": 0,
                "entry_count": 0,
                "matches": True,
            },
            highlighted_entry=None,
            highlight_ledger_id=0,
            as_role=_request_role_hint(),
            is_admin_actor=False,
            admin_message="",
            admin_errors=[message],
            auth_notice=AUTH_NOTICE,
            capability_notice=CAPABILITY_NOTICE,
            form_values={},
        ),
        status_code,
    )


@wallet_admin_bp.get("/wallet/admin")
@admin_or_higher(message="admin role is required for wallet admin workspace")
def wallet_admin_list():
    query = (request.args.get("q", "") or "").strip()
    page = max(1, int(request.args.get("page", "1") or "1"))
    limit = max(1, min(int(request.args.get("limit", str(PAGE_SIZE)) or str(PAGE_SIZE)), MAX_PAGE_SIZE))

    rows = _wallet_service().list_wallet_owners(query=query, limit=limit + 1, offset=(page - 1) * limit)
    has_next = len(rows) > limit
    visible = rows[:limit]

    return render_template(
        "wallet_admin_list.html",
        owners=visible,
        query=query,
        page=page,
        limit=limit,
        has_next=has_next,
        as_role=_request_role_hint(),
        is_admin_actor=_is_admin_actor(),
        admin_message=(request.args.get("message", "") or "").strip(),
        admin_errors=[],
        auth_notice=AUTH_NOTICE,
        capability_notice=CAPABILITY_NOTICE,
    )


@wallet_admin_bp.get("/wallet/admin/<path:owner_id>")
@admin_or_higher(message="admin role is required for wallet admin workspace")
def wallet_admin_detail(owner_id: str):
    service = _wallet_service()
    owner = service.get_wallet_owner(owner_id)
    if owner is None:
        abort(404, description="Wallet owner not found")

    page = max(1, int(request.args.get("page", "1") or "1"))
    limit = max(1, min(int(request.args.get("limit", str(PAGE_SIZE)) or str(PAGE_SIZE)), MAX_PAGE_SIZE))
    history = service.list_ledger_entries(owner_id, limit=limit + 1, offset=(page - 1) * limit)
    has_next = len(history) > limit
    visible = history[:limit]
    reconciliation = service.reconcile_balance(owner_id)

    return render_template(
        "wallet_admin_detail.html",
        owner=owner,
        history=visible,
        page=page,
        limit=limit,
        has_next=has_next,
        reconciliation=reconciliation,
        as_role=_request_role_hint(),
        is_admin_actor=_is_admin_actor(),
        admin_message=(request.args.get("message", "") or "").strip(),
        admin_errors=[],
        auth_notice=AUTH_NOTICE,
        capability_notice=CAPABILITY_NOTICE,
    )


@wallet_admin_bp.post("/wallet/admin/<path:owner_id>/adjust")
@admin_or_higher(message="admin role is required for wallet mutations", on_fail=_wallet_admin_adjust_auth_error)
def wallet_admin_adjust(owner_id: str):
    service = _wallet_service()
    page = max(1, int(request.form.get("page", "1") or "1"))
    limit = max(1, min(int(request.form.get("limit", str(PAGE_SIZE)) or str(PAGE_SIZE)), MAX_PAGE_SIZE))
    form_values = {
        key: request.form.getlist(key)[-1]
        for key in request.form.keys()
        if request.form.getlist(key)
    }

    try:
        owner_kind = (request.form.get("owner_kind", "LOCAL_PLAYER") or "LOCAL_PLAYER").strip().upper()
        owner_label = (request.form.get("owner_label", "") or "").strip() or None
        service.ensure_wallet_owner(owner_id=owner_id, display_name=owner_label, owner_kind=owner_kind)

        entry_mode = (request.form.get("entry_mode", "adjustment") or "adjustment").strip().lower()
        reason_text = (request.form.get("reason_text", "") or "").strip()
        if not reason_text:
            raise InvalidAmountError("reason text is required")

        actor_id = (request.form.get("actor_id", "local_admin") or "local_admin").strip() or "local_admin"
        idempotency_key = (request.form.get("idempotency_key", "") or "").strip()
        if not idempotency_key:
            raise InvalidAmountError("idempotency key is required")

        metadata = _parse_metadata_json((request.form.get("metadata_json", "") or "").strip())

        if entry_mode == "adjustment":
            amount_minor = int((request.form.get("amount_minor", "") or "0").strip())
            if amount_minor <= 0:
                raise InvalidAmountError("amount must be greater than zero")
            direction = (request.form.get("direction", "credit") or "credit").strip().lower()
            if direction not in {"credit", "debit"}:
                raise InvalidAmountError("direction must be credit or debit")
            signed_amount = amount_minor if direction == "credit" else -amount_minor
            expected_confirmation = f"APPLY {signed_amount:+d}"
            confirmation = (request.form.get("confirmation", "") or "").strip()
            if confirmation != expected_confirmation:
                raise InvalidAmountError(f"confirmation phrase must exactly match {expected_confirmation}")

            result = service.admin_adjust(
                discord_user_id=owner_id,
                signed_amount=signed_amount,
                reference_id=idempotency_key,
                reason_code=f"ADMIN_{direction.upper()}",
                reason_text=reason_text,
                actor_discord_id=actor_id,
                actor_source="local_admin",
                idempotency_key=idempotency_key,
                metadata=metadata,
            )
            signed_display = signed_amount
        else:
            original_ledger_id = int((request.form.get("original_ledger_id", "") or "0").strip())
            if original_ledger_id <= 0:
                raise InvalidAmountError("original ledger id is required for reversal or refund")
            original_entry = service.get_ledger_entry(owner_id, original_ledger_id)
            if original_entry is None:
                raise InvalidOwnerError("original ledger entry not found for wallet owner")
            signed_display = -int(original_entry["signed_amount"])
            expected_confirmation = f"APPLY {signed_display:+d}"
            confirmation = (request.form.get("confirmation", "") or "").strip()
            if confirmation != expected_confirmation:
                raise InvalidAmountError(f"confirmation phrase must exactly match {expected_confirmation}")

            result = service.reverse_entry(
                owner_id=owner_id,
                original_ledger_id=original_ledger_id,
                transaction_type=entry_mode.upper(),
                idempotency_key=idempotency_key,
                actor_id=actor_id,
                actor_source="local_admin",
                reason_text=reason_text,
                metadata=metadata,
            )

        message = (
            f"Wallet entry reused existing idempotency key {result.idempotency_key}."
            if result.idempotent
            else f"Posted wallet entry {result.entry_type} {signed_display:+d}; resulting balance {result.balance_after}."
        )
        params = {"message": message, "page": page, "limit": limit}
        return redirect(f"/wallet/admin/{owner_id}?{urlencode(params)}")
    except (InvalidAmountError, InvalidOwnerError, InsufficientFundsError, MetadataValidationError, ValueError) as exc:
        owner = service.get_wallet_owner(owner_id)
        if owner is None:
            owner = {
                "account_id": 0,
                "owner_id": owner_id,
                "owner_kind": request.form.get("owner_kind", "LOCAL_PLAYER"),
                "owner_label": request.form.get("owner_label", "") or None,
                "balance_minor": 0,
                "created_at": None,
                "updated_at": None,
                "transaction_count": 0,
                "latest_activity": None,
            }
        history = service.list_ledger_entries(owner_id, limit=limit + 1, offset=(page - 1) * limit) if owner.get("account_id") else []
        has_next = len(history) > limit
        reconciliation = service.reconcile_balance(owner_id) if owner.get("account_id") else {
            "owner_id": owner_id,
            "account_balance_minor": 0,
            "ledger_total_minor": 0,
            "entry_count": 0,
            "matches": True,
        }
        return (
            render_template(
                "wallet_admin_detail.html",
                owner=owner,
                history=history[:limit],
                page=page,
                limit=limit,
                has_next=has_next,
                reconciliation=reconciliation,
                admin_message="",
                admin_errors=[str(exc)],
                auth_notice=AUTH_NOTICE,
                capability_notice=CAPABILITY_NOTICE,
                form_values=form_values,
            ),
            400,
        )


def _parse_metadata_json(raw: str) -> dict[str, object]:
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MetadataValidationError("metadata JSON must be a valid object") from exc
    if not isinstance(decoded, dict):
        raise MetadataValidationError("metadata JSON must decode to an object")
    return decoded