"""Card rail (brief 0435, payments P1.3): Stripe Payment Links per request.

ubyhost never touches funds: the link is created on the host's connected
account (application fee 0, merchant of record = the host) and Stripe's
receipt is automatic. Every Stripe call goes through stripe_connect._api(),
so the shared monthly cap applies. Webhook events arrive at the
connected-accounts destination endpoint registered by the owner (0428).
"""
from __future__ import annotations

from typing import Any, Dict

from . import db, stripe_connect


def _request_or_none(request_id: int) -> Dict[str, Any] | None:
    row = db.query_one("SELECT * FROM payment_request WHERE id = ?", (request_id,))
    return dict(row) if row else None


def send(request_id: int) -> str | None:
    """Create the Payment Link for a card-rail request; store the id.

    Returns the link URL, or None with a refusal reason when the host's
    Stripe account cannot take payments yet (the caller shows the calm
    connect-first copy).
    """
    row = _request_or_none(request_id)
    if row is None:
        return None
    if row["rail"] != "card":
        raise ValueError("card rail only")
    account = stripe_connect.account_for_owner(int(row["owner_user_id"]))
    if account is None or account["onboarding_state"] != "complete":
        return None
    link = stripe_connect._api().payment_links.create(
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": "czk",
                    "unit_amount": int(row["amount_czk"]) * 100,
                    "product_data": {"name": f"UbyHost payment request #{row['id']}"},
                },
            }
        ],
        stripe_account=account["stripe_account_id"],
    )
    db.execute(
        "UPDATE payment_request SET stripe_payment_link_id = ?, updated_at = ?"
        " WHERE id = ?",
        (link["id"], db.utcnow(), request_id),
    )
    db.audit(
        "payment_link_created",
        f"id={request_id} link={link['id']}",
        owner_user_id=int(row["owner_user_id"]),
    )
    return str(link["url"])


def on_paid(event: Dict[str, Any]) -> None:
    """Webhook: a Payment Link was paid. Flip the matching request to paid."""
    obj = event.get("data", {}).get("object", {}) or {}
    link_id = obj.get("payment_link") or obj.get("id")
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
    from datetime import date

    # The webhook can beat the host's own Send click (or arrive while the row
    # is still a draft): paid is a legal jump from draft/sent/awaiting alike,
    # so walk through sent when the row has not been sent yet.
    if row["status"] == "draft":
        model.set_status(int(row["id"]), "sent", today=date.today())
    model.mark_paid(int(row["id"]), today=date.today(), via="stripe_webhook")
