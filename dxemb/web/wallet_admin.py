from __future__ import annotations

import json
import uuid
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


def _actor_id_default() -> str:
    return (
        (request.form.get("actor_id") or "").strip()
        or (request.headers.get("X-DXEMB-ACTOR-ID") or "").strip()
        or "local_admin"
    )


def _parse_bounded_int(raw_value: str | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int((raw_value or "").strip() or str(default))
    except ValueError:
        return default
    return max(minimum, min(parsed, maximum))


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
    page = _parse_bounded_int(request.args.get("page"), default=1, minimum=1, maximum=100000)
    limit = _parse_bounded_int(request.args.get("limit"), default=PAGE_SIZE, minimum=1, maximum=MAX_PAGE_SIZE)

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
    owner = service.get_wallet_summary(owner_id)
    if owner is None:
        abort(404, description="Wallet owner not found")

    page = _parse_bounded_int(request.args.get("page"), default=1, minimum=1, maximum=100000)
    limit = _parse_bounded_int(request.args.get("limit"), default=PAGE_SIZE, minimum=1, maximum=MAX_PAGE_SIZE)
    direction = (request.args.get("direction", "all") or "all").strip().lower()
    status = (request.args.get("status", "all") or "all").strip().lower()
    entry_type = (request.args.get("entry_type", "") or "").strip().upper() or None
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
            entry_type=entry_type,
            reference_query=reference_query,
            created_after=created_after,
            created_before=created_before,
        )
    except InvalidAmountError as exc:
        return (
            render_template(
                "wallet_admin_detail.html",
                owner=owner,
                history=[],
                direction=direction,
                status=status,
                entry_type=entry_type or "",
                reference_query=reference_query,
                created_after=created_after,
                created_before=created_before,
                page=1,
                limit=limit,
                has_next=False,
                reconciliation=service.reconcile_balance(owner_id),
                highlighted_entry=None,
                highlight_ledger_id=0,
                as_role=_request_role_hint(),
                is_admin_actor=_is_admin_actor(),
                admin_message="",
                admin_errors=[str(exc)],
                auth_notice=AUTH_NOTICE,
                capability_notice=CAPABILITY_NOTICE,
            ),
            400,
        )
    has_next = len(history) > limit
    visible = history[:limit]
    reconciliation = service.reconcile_balance(owner_id)
    try:
        highlight_ledger_id = int(request.args.get("highlight_ledger_id", "0") or "0")
    except ValueError:
        highlight_ledger_id = 0
    highlighted_entry = service.get_ledger_entry(owner_id, highlight_ledger_id) if highlight_ledger_id > 0 else None

    return render_template(
        "wallet_admin_detail.html",
        owner=owner,
        history=visible,
        direction=direction,
        status=status,
        entry_type=entry_type or "",
        reference_query=reference_query,
        created_after=created_after,
        created_before=created_before,
        page=page,
        limit=limit,
        has_next=has_next,
        reconciliation=reconciliation,
        highlighted_entry=highlighted_entry,
        highlight_ledger_id=highlight_ledger_id,
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

    page = _parse_bounded_int(request.form.get("page"), default=1, minimum=1, maximum=100000)
    limit = _parse_bounded_int(request.form.get("limit"), default=PAGE_SIZE, minimum=1, maximum=MAX_PAGE_SIZE)
    direction_filter = (request.form.get("direction", "all") or "all").strip().lower()
    status_filter = (request.form.get("status", "all") or "all").strip().lower()
    entry_type_filter = (request.form.get("entry_type", "") or "").strip().upper()
    reference_query_filter = (request.form.get("reference_query", "") or "").strip()
    created_after_filter = (request.form.get("created_after", "") or "").strip()
    created_before_filter = (request.form.get("created_before", "") or "").strip()
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

        actor_id = _actor_id_default()
        header_actor_id = (request.headers.get("X-DXEMB-ACTOR-ID") or "").strip()
        form_actor_id = (request.form.get("actor_id") or "").strip()
        if header_actor_id and form_actor_id and header_actor_id != form_actor_id:
            raise InvalidAmountError("actor_id must match X-DXEMB-ACTOR-ID when header is provided")
        if header_actor_id:
            actor_id = header_actor_id
        operation_ref = (request.form.get("operation_ref", "") or "").strip()
        idempotency_key = (request.form.get("idempotency_key", "") or "").strip() or operation_ref
        if not operation_ref:
            operation_ref = f"wallet-admin-{uuid.uuid4().hex[:12]}"
        if not idempotency_key:
            idempotency_key = operation_ref

        metadata = _parse_metadata_json((request.form.get("metadata_json", "") or "").strip())

        if entry_mode in {"credit", "debit", "adjustment"}:
            amount_minor = int((request.form.get("amount_minor", "") or "0").strip())
            if amount_minor <= 0:
                raise InvalidAmountError("amount must be greater than zero")
            direction = (request.form.get("direction", "credit") or "credit").strip().lower()
            normalized_mode = entry_mode
            if normalized_mode == "adjustment":
                if direction not in {"credit", "debit"}:
                    raise InvalidAmountError("direction must be credit or debit")
                signed_amount = amount_minor if direction == "credit" else -amount_minor
            elif normalized_mode == "credit":
                signed_amount = amount_minor
            else:
                signed_amount = -amount_minor
            expected_confirmation = f"APPLY {signed_amount:+d}"
            confirmation = (request.form.get("confirmation", "") or "").strip()
            if confirmation != expected_confirmation:
                raise InvalidAmountError(f"confirmation phrase must exactly match {expected_confirmation}")

            result = service.create_authorized_entry(
                owner_id=owner_id,
                operation=normalized_mode,
                amount_minor=signed_amount if normalized_mode == "adjustment" else amount_minor,
                reason_text=reason_text,
                actor_id=actor_id,
                actor_source="local_admin",
                idempotency_key=idempotency_key,
                reference_id=operation_ref,
                reason_code=f"ADMIN_{(direction if normalized_mode == 'adjustment' else normalized_mode).upper()}",
                metadata=metadata,
            )
            signed_display = result.signed_amount
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
            else (
                f"Posted wallet entry {result.entry_type} {signed_display:+d}; "
                f"resulting balance {result.balance_after}; operation reference {operation_ref}."
            )
        )
        params = {
            "message": message,
            "page": page,
            "limit": limit,
            "highlight_ledger_id": result.ledger_id,
            "as_role": _request_role_hint() or "admin",
            "direction": direction_filter,
            "status": status_filter,
            "entry_type": entry_type_filter,
            "reference_query": reference_query_filter,
            "created_after": created_after_filter,
            "created_before": created_before_filter,
        }
        return redirect(f"/wallet/admin/{owner_id}?{urlencode(params)}")
    except (InvalidAmountError, InvalidOwnerError, InsufficientFundsError, MetadataValidationError, ValueError) as exc:
        owner = service.get_wallet_summary(owner_id)
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
                "total_credits_minor": 0,
                "total_debits_minor": 0,
                "ledger_net_minor": 0,
                "last_ledger_at": None,
                "recent_reference": None,
            }
        history = service.list_ledger_history(owner_id, limit=limit + 1, offset=(page - 1) * limit) if owner.get("account_id") else []
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
                direction=direction_filter,
                status=status_filter,
                entry_type=entry_type_filter,
                reference_query=reference_query_filter,
                created_after=created_after_filter,
                created_before=created_before_filter,
                page=page,
                limit=limit,
                has_next=has_next,
                reconciliation=reconciliation,
                highlighted_entry=None,
                highlight_ledger_id=0,
                as_role=_request_role_hint() or "admin",
                is_admin_actor=_is_admin_actor(),
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