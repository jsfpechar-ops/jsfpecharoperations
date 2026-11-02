"""Card rail (brief 0435, payments P1.3; hardened in 0622): Stripe Payment
Links per request.

ubyhost never touches funds: the link is created on the host's connected
account (application fee 0, merchant of record = the host) and Stripe's
receipt is automatic. Every Stripe call goes through stripe_connect._api(),
so the shared monthly cap applies. The connected account goes in the request
options (the Stripe-Account header), never in params: in params Stripe reads
it as an unknown body field and refuses the call (0622). Each link accepts
exactly one completed payment and carries the request id in metadata.
Webhook events arrive at the connected-accounts endpoint (0428).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict

from . import db, host_i18n, stripe_connect

# Checkout events that can mean "money arrived". completed fires for every
# finished checkout, but bank-redirect methods finish unpaid and settle later
# via async_payment_succeeded; only payment_status == "paid" counts.
PAID_EVENTS = ("checkout.session.completed", "checkout.session.async_payment_succeeded")


def _request_or_none(request_id: int) -> Dict[str, Any] | None:
    row = db.query_one("SELECT * FROM payment_request WHERE id = ?", (request_id,))
    return dict(row) if row else None


def product_name(row: Dict[str, Any]) -> str:
    """What the guest sees on Stripe Checkout and the receipt (Czech)."""
    reason = host_i18n.translate("cs", f"payments.reason.{row['reason']}")
    return f"{reason} (žádost č. {row['id']})"


def _existing_url(api, link_id: str, stripe_account: str) -> str | None:
    """The URL of a still-active link from an earlier send, else None."""
    link = api.v1.payment_links.retrieve(link_id, options={"stripe_account": stripe_account})
    if link.get("active"):
        return str(link["url"])
    return None


def send(request_id: int) -> str | None:
    """Create (or reuse) the Payment Link for a card-rail request.

    Returns the link URL, or None when the host's Stripe account cannot take
    payments yet (the caller shows the calm connect-first copy). A resend
    returns the same active link, so a guest can never hold two live links
    for one request.
    """
    row = _request_or_none(request_id)
    if row is None:
        return None
    if row["rail"] != "card":
        raise ValueError("card rail only")
    account = stripe_connect.account_for_owner(int(row["owner_user_id"]))
    if account is None or account["onboarding_state"] != "complete":
        return None
    stripe_account = account["stripe_account_id"]
    api = stripe_connect._api()
    owner_id = int(row["owner_user_id"])
    created_id = created_url = None
    # Two overlapping Send clicks used to mint two live Stripe links (each
    # accepts one payment), so a guest could be charged twice. Take the row
    # lock before the Stripe create; a second caller waits, re-reads, and
    # reuses the link the first caller stored.
    with db.immediate() as cur:
        db.lock_key(cur, "payment_request", request_id)
        locked = cur.execute(
            "SELECT * FROM payment_request WHERE id = ?", (request_id,)
        ).fetchone()
        if locked is None:
            return None
        link_id = locked["stripe_payment_link_id"]
        if link_id:
            url = _existing_url(api, link_id, stripe_account)
            if url:
                return url
        link = api.v1.payment_links.create(
            params={
                "line_items": [
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": "czk",
                            "unit_amount": int(locked["amount_czk"]) * 100,
                            "product_data": {"name": product_name(dict(locked))},
                        },
                    }
                ],
                "restrictions": {"completed_sessions": {"limit": 1}},
                "metadata": {"payment_request_id": str(locked["id"])},
                "payment_intent_data": {"metadata": {"payment_request_id": str(locked["id"])}},
            },
            options={"stripe_account": stripe_account},
        )
        cur.execute(
            "UPDATE payment_request SET stripe_payment_link_id = ?, updated_at = ?"
            " WHERE id = ?",
            (link["id"], db.utcnow(), request_id),
        )
        created_id = link["id"]
        created_url = str(link["url"])
    db.audit(
        "payment_link_created",
        f"id={request_id} link={created_id}",
        owner_user_id=owner_id,
    )
    return created_url


def on_paid(event: Dict[str, Any]) -> None:
    """Webhook: a checkout for one of our links finished. Flip the request
    to paid only when Stripe says the money is there."""
    obj = event.get("data", {}).get("object", {}) or {}
    if obj.get("payment_status") != "paid":
        return
    link_id = obj.get("payment_link")
    if not link_id:
        return
    row = db.query_one(
        "SELECT id, status, owner_user_id FROM payment_request"
        " WHERE stripe_payment_link_id = ?",
        (link_id,),
    )
    if row is None or row["status"] == "paid":
        return
    from . import payment_request as model

    # The webhook can beat the host's own Send click (or arrive while the row
    # is still a draft): paid is a legal jump from draft/sent/awaiting alike,
    # so walk through sent when the row has not been sent yet. Expired and
    # cancelled rows may also be paid late (0623): money received is the truth.
    if row["status"] == "draft":
        model.set_status(int(row["id"]), "sent", today=date.today())
    model.mark_paid(int(row["id"]), today=date.today(), via="stripe_webhook")
