"""Stripe Connect provisioning for host payment requests (brief 0428).

ubyhost never receives or holds funds. Each host gets their own connected
account (merchant of record, application fee 0) created with the current
controller API: ubyhost is never the fees payer, Stripe is the losses
collector, Stripe collects requirements and hosts get the Express dashboard.
ubyhost creates the account, hosts the one-time onboarding redirect and
mirrors non-sensitive status back — never API keys, never identity documents,
never bank details (those live only in Stripe, plan ubyhost-complete-stripe
§12). The webhook handler verifies the raw body against the whsec secret and
dedupes by event id, because Stripe retries until 2xx.

Every Stripe call counts against the shared monthly cap (lock_api_usage,
provider 'stripe'), the same guard pattern as TTLock.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Optional

import stripe

from . import config, db

# Requirement field names worth mirroring; everything else in the requirements
# hash is either a superset of these or Stripe-internal noise.
_REQUIREMENT_KEYS = ("currently_due", "past_due", "eventually_due", "disabled_reason")

# Rejection codes that mean Stripe turned the host down (never stored beyond
# the requirement field names themselves; see _mirror).
_REJECT_CODES = ("rejected", "listed", "fraudulent")


def enabled() -> bool:
    """Direct payments are on only in test/live mode with a secret key set."""
    return config.STRIPE_MODE in ("test", "live") and bool(config.STRIPE_SECRET_KEY)


def calls_this_month() -> int:
    row = db.query_one(
        "SELECT calls FROM lock_api_usage WHERE month = ? AND provider = 'stripe'",
        (_month_key(),),
    )
    return int(row["calls"]) if row and row["calls"] is not None else 0


def _month_key() -> str:
    return db.utcnow()[:7]


def _budget_allows() -> bool:
    limit = config.STRIPE_MONTHLY_API_CALLS
    if limit <= 0:
        return True
    return calls_this_month() < limit


def _count_call() -> None:
    month = _month_key()
    db.execute(
        "INSERT INTO lock_api_usage (month, provider, calls) VALUES (?, 'stripe', 1) "
        "ON CONFLICT(month, provider) DO UPDATE SET calls = calls + 1",
        (month,),
    )


class StripeOff(Exception):
    """Raised when code calls Stripe while the feature is off or out of budget."""


def _client():
    """The StripeClient every guarded call uses (brief 0437).

    Accounts v2 (``client.v2.core.accounts``) needs the client instance; the
    v1 endpoints used for Account Links (``client.account_links``) work on the
    same object, so one client serves both.
    """
    return stripe.StripeClient(config.STRIPE_SECRET_KEY)


def _api():
    """The configured Stripe client; every call goes through this guard.

    Kept under its 0428 name because the rails (payment_links) call it; it now
    returns the StripeClient (call sites: .Account.create -> .v2.core.accounts
    .create in 0437; AccountLink/PaymentLink stay on the client's v1-style
    services, which accept v2 account ids).
    """
    if not enabled():
        raise StripeOff("stripe is off: UBYHOST_STRIPE_MODE/UBYHOST_STRIPE_SECRET_KEY")
    if not _budget_allows():
        raise StripeOff("monthly Stripe API call cap reached")
    _count_call()
    stripe.api_key = config.STRIPE_SECRET_KEY
    return _client()


# --- connected account -----------------------------------------------------


def _identity_params(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Accounts v2 identity block (brief 0437): business_details replaces the
    v1 business_profile, and entity_type comes from the host's explicit
    business_type choice (migration 0032) — company hosts get Stripe's
    representative/beneficial-ownership KYC; individuals are the default.

    The v1 controller design maps 1:1 to v2 responsibilities: fees payer =
    account -> fees_collector = stripe (host pays their own Stripe fees);
    losses = stripe -> losses_collector = stripe; Express dashboard -> the
    dashboard property; requirement collection follows automatically from
    those. Responsibilities are immutable after creation, so they are set
    here, once, correctly.
    """
    entity_type = "company" if entity.get("business_type") == "company" else "individual"
    return {
        "country": "CZ",
        "entity_type": entity_type,
        "business_details": {
            "registered_name": entity["name"],
            "url": config.PUBLIC_BASE_URL,
            # One sentence, accommodation-shaped, for Stripe's underwriting
            # review; also the MCC signal so classification never falls
            # through to the 5734 default (MCC round 2, Q1).
            "product_description": (
                "Short-term accommodation rentals: the host rents out their "
                "own property to guests (booking payments, extra-guest fees, "
                "cleaning and repair contributions)."
            ),
        },
    }


def _merchant_config() -> Dict[str, Any]:
    """The merchant configuration requested at creation: card payments plus
    payouts, the capabilities the rails need."""
    return {
        "merchant": {
            "capabilities": {
                "card_payments": {"requested": True},
                "stripe_balance.payouts": {"requested": True},
            }
        }
    }


def _responsibilities() -> Dict[str, Any]:
    """v2 responsibilities (immutable after creation): Stripe collects fees
    from the host directly, Stripe carries negative balances."""
    return {
        "currency": "czk",
        "responsibilities": {
            "fees_collector": "stripe",
            "losses_collector": "stripe",
        },
    }


def account_for_owner(owner_user_id: int) -> Optional[Dict[str, Any]]:
    """The mirrored stripe_account row for this owner in the current mode."""
    row = db.query_one(
        "SELECT * FROM stripe_account WHERE owner_user_id = ? AND mode = ?",
        (owner_user_id, config.STRIPE_MODE),
    )
    return dict(row) if row else None


def create_or_get_account(owner_user_id: int) -> Dict[str, Any]:
    """The mirror row for this owner, creating the Stripe account once."""
    row = account_for_owner(owner_user_id)
    if row is not None:
        return row
    entity = db.query_one(
        "SELECT * FROM legal_entity WHERE owner_user_id = ?", (owner_user_id,)
    )
    if entity is None:
        raise ValueError("host has no legal entity; connect needs the business profile")
    # v2 service methods take one params dict (SDK 16.x), not kwargs.
    account = _as_dict(
        _api().v2.core.accounts.create(
            params={
                "contact_email": entity["contact_email"] or None,
                "display_name": entity["name"],
                "dashboard": "express",
                "identity": _identity_params(dict(entity)),
                "configuration": _merchant_config(),
                "defaults": _responsibilities(),
            }
        )
    )
    now = db.utcnow()
    db.insert(
        "stripe_account",
        {
            "owner_user_id": owner_user_id,
            "stripe_account_id": account["id"],
            "mode": config.STRIPE_MODE,
            "onboarding_state": "pending",
            "charges_enabled": 0,
            "payouts_enabled": 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    db.audit("stripe_account_created", f"acct={account['id']}", owner_user_id=owner_user_id)
    _mirror(owner_user_id, dict(account))
    row = account_for_owner(owner_user_id)
    assert row is not None
    return row


def _onboarding_state(account: Dict[str, Any]) -> str:
    """Map Stripe's account state onto our five mirror states."""
    requirements = account.get("requirements") or {}
    if account.get("disabled"):
        return "disabled"
    due = requirements.get("currently_due") or []
    past = requirements.get("past_due") or []
    errors = requirements.get("errors") or []
    if any(word in e.get("code", "") for e in errors for word in _REJECT_CODES):
        return "rejected"
    if account.get("charges_enabled") and not due and not past:
        return "complete"
    if due or past:
        return "action_required"
    return "pending"


def _requirements_json(requirements: Dict[str, Any]) -> Optional[str]:
    """Field names only; never documents, never hashes."""
    if not requirements:
        return None
    subset = {key: requirements.get(key) for key in _REQUIREMENT_KEYS if requirements.get(key)}
    return json.dumps(subset) if subset else None


def _mirror(owner_user_id: int, account: Dict[str, Any]) -> None:
    """Upsert the account state mirror; audit every state transition."""
    row = account_for_owner(owner_user_id)
    if row is None or row["stripe_account_id"] != account.get("id"):
        return
    state = _onboarding_state(account)
    requirements = account.get("requirements") or {}
    changed = db.execute_rowcount(
        "UPDATE stripe_account SET onboarding_state = ?, charges_enabled = ?,"
        " payouts_enabled = ?, requirements_json = ?, updated_at = ?"
        " WHERE owner_user_id = ? AND mode = ? AND onboarding_state != ?",
        (
            state,
            1 if account.get("charges_enabled") else 0,
            1 if account.get("payouts_enabled") else 0,
            _requirements_json(requirements),
            db.utcnow(),
            owner_user_id,
            config.STRIPE_MODE,
            state,
        ),
    )
    if changed:
        db.audit(
            "stripe_account_state",
            f"acct={account.get('id')} state={state}"
            f" charges={1 if account.get('charges_enabled') else 0}"
            f" payouts={1 if account.get('payouts_enabled') else 0}",
            owner_user_id=owner_user_id,
        )


def mirror_by_account_id(account: Dict[str, Any], mode: str) -> None:
    """Webhook entry: find the owner from the Stripe account id and mirror."""
    row = db.query_one(
        "SELECT owner_user_id FROM stripe_account WHERE stripe_account_id = ? AND mode = ?",
        (account.get("id"), mode),
    )
    if row is None:
        return
    _mirror(int(row["owner_user_id"]), account)


# --- onboarding links ------------------------------------------------------


def onboarding_link(owner_user_id: int, *, base_url: str) -> str:
    """A single-use hosted onboarding link. The refresh URL lands back here,
    which regenerates; the return URL checks requirements (return ≠ verified)."""
    row = create_or_get_account(owner_user_id)
    link = _as_dict(
        _api().account_links.create(
            params={
                "account": row["stripe_account_id"],
                "refresh_url": f"{base_url}/payments/connect/start",
                "return_url": f"{base_url}/payments/connect/return",
                "type": "account_onboarding",
            }
        )
    )
    return str(link["url"])


def handle_return(owner_user_id: int) -> str:
    """After Stripe redirects back: re-retrieve and mirror the account."""
    row = account_for_owner(owner_user_id)
    if row is None:
        raise ValueError("no connected account for this host")
    account = _as_dict(_api().accounts.retrieve(row["stripe_account_id"]))
    _mirror(owner_user_id, account)
    updated = account_for_owner(owner_user_id)
    assert updated is not None
    return str(updated["onboarding_state"])


# --- webhooks ---------------------------------------------------------------


def _as_dict(obj: Any) -> Dict[str, Any]:
    """SDK objects expose to_dict() in 16.x; plain dicts pass through."""
    return dict(obj.to_dict()) if hasattr(obj, "to_dict") else dict(obj)


def verify_event(raw: bytes, sig_header: str) -> Dict[str, Any]:
    """Verify the raw body against the whsec secret; raises on mismatch.

    Pure HMAC check — no API call, so it never touches the monthly cap.
    """
    if not config.STRIPE_WEBHOOK_SECRET:
        raise StripeOff("webhook secret unset")
    try:
        event = stripe.Webhook.construct_event(raw, sig_header, config.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError as exc:
        # One failure type for the route to answer with 400, whatever the SDK
        # calls it this year.
        raise ValueError(str(exc)) from exc
    return _as_dict(event)


def event_seen(event_id: str) -> bool:
    return db.query_one(
        "SELECT id FROM stripe_webhook_event WHERE event_id = ?", (event_id,)
    ) is not None


def _record_event(event: Dict[str, Any]) -> bool:
    """First sight returns True; a replay returns False (idempotency gate)."""
    try:
        db.insert(
            "stripe_webhook_event",
            {
                "event_id": event["id"],
                "event_type": event["type"],
                "mode": config.STRIPE_MODE,
                "created_at": db.utcnow(),
            },
        )
    except sqlite3.IntegrityError:
        return False
    return True


def sweep_webhook_events(today) -> int:
    """Prune processed-event rows older than 30 days (brief 0437).

    Stripe retries at most 3 days, so 30 is a generous margin; without this
    the dedupe table grows forever (one row per delivered event).
    """
    cutoff = today.fromordinal(today.toordinal() - 30).isoformat()
    deleted = db.execute_rowcount(
        "DELETE FROM stripe_webhook_event WHERE created_at < ?",
        (cutoff,),
    )
    if deleted:
        db.audit("stripe_webhook_sweep", f"deleted={deleted}")
    return deleted


def process_event(event: Dict[str, Any]) -> None:
    """Dedupe by event id, then dispatch. Only account.updated is handled in
    0428; the card/QR rail events arrive in later briefs and are recorded."""
    if not _record_event(event):
        return
    etype = event.get("type")
    if etype == "account.updated":
        mirror_by_account_id(dict(event["data"]["object"]), config.STRIPE_MODE)
    elif etype in ("payment_link.paid", "checkout.session.completed"):
        from . import payment_links
        payment_links.on_paid(event)
