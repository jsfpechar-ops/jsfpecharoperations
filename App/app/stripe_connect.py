"""Stripe Connect (brief 0426): Express connected accounts for hosts.

ubyhost is a Connect platform; each host is the merchant of record on their
own connected account (direct charges, fee collector = the account, no
application fee). Stripe collects KYC in its hosted onboarding flow — we
prefill only name, e-mail and the page URL, never identity documents or
sensitive personal data. The local ``stripe_account`` row mirrors non-sensitive
status only (plan: ubyhost-complete-stripe, Appendix D 12b).

Everything here is inert unless ``UBYHOST_STRIPE_MODE`` is test/live with a
secret key set (config.stripe_enabled()).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import stripe

from . import alerts, config, db, payment_request

log = logging.getLogger(__name__)

LOW = "low"
NORMAL = "normal"

# The only Stripe requests this module may make (outbound requests have a
# reason in the PR, AGENTS.md rule 2).
ALLOWED = ("v2.core.accounts.create", "accounts.retrieve", "account_links.create")


class StripeDisabledError(RuntimeError):
    """Raised when the Stripe feature is off or the budget is exhausted."""


def _month_key() -> str:
    row = db.query_one("SELECT strftime('%Y-%m', 'now') AS k")
    return row["k"]


def calls_this_month() -> int:
    row = db.query_one(
        "SELECT calls FROM lock_api_usage WHERE month = ? AND provider = 'stripe'",
        (_month_key(),),
    )
    return int(row["calls"]) if row and row["calls"] is not None else 0


def _budget_allows(priority: str) -> bool:
    limit = config.STRIPE_MONTHLY_API_CALLS
    if limit <= 0:
        return True
    ratio = calls_this_month() / limit
    if ratio >= 0.95 and priority == LOW:
        return False
    return True


def _count_call() -> None:
    db.execute(
        "INSERT INTO lock_api_usage (month, provider, calls) VALUES (?, 'stripe', 1) "
        "ON CONFLICT (month, provider) DO UPDATE SET calls = calls + 1",
        (_month_key(),),
    )


def _client() -> stripe.StripeClient:
    if not config.stripe_enabled():
        raise StripeDisabledError("stripe mode is off or the secret key is unset")
    return stripe.StripeClient(config.STRIPE_SECRET_KEY)


def _entity(owner_user_id: int) -> Optional[Dict[str, Any]]:
    return db.query_one(
        "SELECT name, contact_email FROM legal_entity WHERE owner_user_id = ?",
        (owner_user_id,),
    )


def account_row(owner_user_id: int) -> Optional[Dict[str, Any]]:
    return db.query_one(
        "SELECT * FROM stripe_account WHERE owner_user_id = ? AND mode = ?",
        (owner_user_id, config.STRIPE_MODE if config.STRIPE_MODE in ("test", "live") else "test"),
    )


def ensure_account(owner_user_id: int, *, base_url: str, priority: str = NORMAL) -> Dict[str, Any]:
    """Find or create the host's connected account; returns the mirror row.

    Prefills name/e-mail/url only — Stripe's hosted onboarding collects the
    rest (DOB, address, ID, IBAN) and the service agreement acceptance.
    """
    if not config.stripe_enabled():
        raise StripeDisabledError("stripe mode is off")
    row = account_row(owner_user_id)
    if row:
        return dict(row)
    if not _budget_allows(priority):
        raise StripeDisabledError("stripe monthly api budget exhausted")
    entity = _entity(owner_user_id)
    if entity is None:
        raise ValueError("host has no legal entity; cannot create a Stripe account")
    # Accounts v2 (POST /v2/core/accounts): v1 creation is disabled on new
    # platforms. Responsibilities map 1:1 to our locked v1 controller design:
    # fees_collector=stripe (host pays their own Stripe fees), losses_collector
    # =stripe (Stripe carries negative balances), dashboard=express, and KYC
    # collection follows automatically from those (requirements_collector
    # becomes stripe). Immutable: set correctly at creation.
    acct = _client().v2.core.accounts.create(
        contact_email=entity["contact_email"] or None,
        display_name=entity["name"],
        dashboard="express",
        identity={
            "country": "CZ",
            "entity_type": "individual",
            "business_details": {
                "registered_name": entity["name"],
                "url": base_url,
                "product_description": (
                    "Short-term accommodation rental by the host (ubyhost page)"
                ),
            },
        },
        configuration={
            "merchant": {
                "capabilities": {
                    "card_payments": {"requested": True},
                    "stripe_balance.payouts": {"requested": True},
                }
            }
        },
        defaults={
            "currency": "czk",
            "responsibilities": {
                "fees_collector": "stripe",
                "losses_collector": "stripe",
            },
        },
    )
    _count_call()
    now = db.utcnow()
    mirror_id = db.insert(
        "stripe_account",
        {
            "owner_user_id": owner_user_id,
            "stripe_account_id": acct.id,
            "mode": config.STRIPE_MODE,
            "onboarding_state": "pending",
            "charges_enabled": 0,
            "payouts_enabled": 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    db.audit("stripe_account_created", f"id={mirror_id} account={acct.id}", owner_user_id=owner_user_id)
    return dict(account_row(owner_user_id))


def onboarding_link(
    owner_user_id: int, *, return_url: str, refresh_url: str, priority: str = NORMAL
) -> str:
    """Single-use hosted-onboarding URL. Show it only in the authenticated app."""
    row = ensure_account(owner_user_id, base_url=_page_url(owner_user_id))
    if not _budget_allows(priority):
        raise StripeDisabledError("stripe monthly api budget exhausted")
    link = _client().account_links.create(
        account=row["stripe_account_id"],
        type="account_onboarding",
        refresh_url=refresh_url,
        return_url=return_url,
        collection_options={"fields": "eventually_due"},
    )
    _count_call()
    db.audit(
        "stripe_onboarding_link",
        f"account={row['stripe_account_id']}",
        owner_user_id=owner_user_id,
    )
    return link.url


def _page_url(owner_user_id: int) -> str:
    # The host's dashboard base URL; the property page URL lands here once
    # pages exist (0430+). Kept as the host's own page reference for MCC.
    from .config import app_base_url

    return app_base_url()


def sync_account(owner_user_id: int, *, priority: str = NORMAL) -> Dict[str, Any]:
    """Re-retrieve the account and refresh the mirror row (return != verified)."""
    row = account_row(owner_user_id)
    if row is None:
        raise ValueError("no stripe account for this host")
    if not _budget_allows(priority):
        raise StripeDisabledError("stripe monthly api budget exhausted")
    acct = _client().accounts.retrieve(row["stripe_account_id"])
    _count_call()
    return _apply_account_state(owner_user_id, acct)


def _apply_account_state(owner_user_id: int, acct: Any) -> Dict[str, Any]:
    # acct is an SDK Account or the webhook's data.object dict.
    def _get(name, default=None):
        if isinstance(acct, dict):
            return acct.get(name, default)
        return getattr(acct, name, default)

    reqs = _get("requirements", {}) or {}
    currently_due = list(reqs.get("currently_due") or [])
    past_due = list(reqs.get("past_due") or [])
    disabled_reason = str(reqs.get("disabled_reason") or "")
    charges = bool(_get("charges_enabled", False))
    payouts = bool(_get("payouts_enabled", False))
    account_id = _get("id", "")
    if charges and payouts and not past_due:
        state = "complete"
    elif "rejected" in disabled_reason:
        state = "rejected"
    elif account_id and (currently_due or past_due) and (charges or payouts):
        state = "action_required"
    elif _get("details_submitted", False) or charges or payouts:
        state = "action_required" if (currently_due or past_due) else "complete"
    else:
        state = "pending"
    db.execute(
        "UPDATE stripe_account SET charges_enabled = ?, payouts_enabled = ?,"
        " onboarding_state = ?, requirements_json = ?, updated_at = ?"
        " WHERE owner_user_id = ? AND mode = ?",
        (
            int(charges),
            int(payouts),
            state,
            json.dumps(
                {
                    "currently_due": currently_due,
                    "past_due": past_due,
                    "disabled_reason": disabled_reason or None,
                }
            ),
            db.utcnow(),
            owner_user_id,
            config.STRIPE_MODE if config.STRIPE_MODE in ("test", "live") else "test",
        ),
    )
    db.audit("stripe_account_sync", f"account={account_id} state={state}", owner_user_id=owner_user_id)
    return dict(account_row(owner_user_id))


def verify_and_parse(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """Verify the webhook signature over the RAW body; raises on failure."""
    if not config.STRIPE_WEBHOOK_SECRET:
        raise ValueError("stripe webhook secret unset")
    event = stripe.Webhook.construct_event(payload, sig_header, config.STRIPE_WEBHOOK_SECRET)
    return event


def _event_seen(event_id: str) -> bool:
    key = f"stripe_event:{event_id}"
    row = db.query_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row is not None


def _mark_event_seen(event_id: str) -> None:
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, '1') ON CONFLICT (key) DO NOTHING",
        (f"stripe_event:{event_id}",),
    )


def handle_event(event: Any) -> None:
    """Idempotent webhook dispatch. Never raises on unknown event types."""
    event_id = getattr(event, "id", "") or ""
    etype = getattr(event, "type", "") or ""
    if event_id and _event_seen(event_id):
        return
    if event_id:
        _mark_event_seen(event_id)
    obj = getattr(event, "data", None)
    obj = getattr(obj, "object", None) or {}
    try:
        if etype == "account.updated":
            row = db.query_one(
                "SELECT owner_user_id FROM stripe_account WHERE stripe_account_id = ?",
                (obj.get("id"),),
            )
            if row:
                _apply_account_state(int(row["owner_user_id"]), obj)
        elif etype in ("checkout.session.completed", "payment_intent.succeeded"):
            _mark_request_paid(obj)
        elif etype == "charge.dispute.created":
            row = db.query_one(
                "SELECT owner_user_id FROM stripe_account WHERE stripe_account_id = ?",
                (obj.get("account") or "",),
            )
            db.audit("stripe_dispute", f"id={obj.get('id')} account={obj.get('account')}")
            if row:
                alerts.raise_alert(
                    "error",
                    "stripe_dispute",
                    "A guest opened a dispute — check your Stripe Express Dashboard.",
                    detail=f"dispute={obj.get('id')}",
                    owner_user_id=int(row["owner_user_id"]),
                )
        elif etype in ("payout.paid", "payout.failed"):
            db.audit("stripe_payout_event", f"type={etype} id={obj.get('id')}")
        else:
            log.info("stripe webhook: unhandled event type %s", etype)
    except Exception:
        # A webhook must never crash into a 5xx loop; Stripe retries delivery.
        log.exception("stripe webhook handling failed for %s", etype)


def _mark_request_paid(obj: Dict[str, Any]) -> None:
    """Find the payment request by any Stripe id and mark it paid (idempotent).

    payment_intent.succeeded: obj["id"] is the PaymentIntent; a Checkout
    Session's payment_intent rides under obj["payment_intent"].
    """
    candidates = [
        ("stripe_payment_intent_id", obj.get("payment_intent") or obj.get("id")),
        ("stripe_session_id", obj.get("id")),
    ]
    for column, value in candidates:
        if not value:
            continue
        row = db.query_one(
            f"SELECT id, owner_user_id, status FROM payment_request WHERE {column} = ?",
            (value,),
        )
        if row and row["status"] not in ("paid", "expired", "cancelled"):
            payment_request.mark_paid(int(row["id"]), today=_today(), via="card")
            return


def _today():
    from datetime import date

    return date.today()
