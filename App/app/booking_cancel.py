"""Booking site cancellation and refunds (brief 0821, plan booking-site-v1).

paid -> cancelled (dates freed, intended refund stored) -> Stripe refund ->
refunded. A failed refund leaves the booking `cancelled`; a retry refunds
exactly once (one idempotency key per booking, intended amount stored first).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from . import booking_site, booking_webhook, claim, db, host_i18n, mail, stripe_connect

log = logging.getLogger(__name__)


def _intent_key(booking_id: int) -> str:
    return f"site_booking_refund_intent:{int(booking_id)}"


def refund_now(booking: Dict[str, Any], *, by_host: bool, now: Optional[datetime] = None) -> int:
    s = booking_site.settings(int(booking["apartment_id"]))
    return booking_site.refund_czk(booking, checkin_hour=s["checkin_hour"],
                                   by_host=by_host, now=now)


def started(booking: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    s = booking_site.settings(int(booking["apartment_id"]))
    return booking_site.check_in_moment(booking["date_from"], s["checkin_hour"]) <= booking_site._now(now)


def cancel(booking_id: int, *, by_host: bool, now: Optional[datetime] = None) -> Dict[str, Any]:
    """{"error": None, "refund_czk": n} or {"error": not_found | not_cancellable
    | started | busy | refund_failed}. Safe to call twice."""
    booking = booking_site.get(booking_id)
    if booking is None:
        return {"error": "not_found"}
    if booking.get("pay_method") == "direct" and not by_host:
        return {"error": "not_cancellable"}
    owner = int(booking["owner_user_id"])
    if booking["status"] == "paid":
        if not by_host and started(booking, now):
            return {"error": "started"}
        amount = refund_now(booking, by_host=by_host, now=now)
        if booking.get("pay_method") == "direct":
            amount = 0
        db.set_setting(_intent_key(booking_id), f"{amount}:{'h' if by_host else 'g'}")
        if not booking_site.set_status(booking_id, "cancelled", cancelled_at=db.utcnow()):
            return {"error": "busy"}
        _free_reservation(booking)
        db.audit("site_booking_cancelled",
                 f"id={booking_id} by={'host' if by_host else 'guest'} refund={amount}",
                 owner_user_id=owner)
    elif booking["status"] == "cancelled" and not int(booking["refunded_czk"] or 0):
        raw = db.get_setting(_intent_key(booking_id)) or ""
        number, _, who = raw.partition(":")
        if not number.isdigit() or who not in ("h", "g"):
            return {"error": "not_cancellable"}
        amount, by_host = int(number), who == "h"  # retry after a failed refund
    else:
        return {"error": "not_cancellable"}
    if amount > 0:
        try:
            _stripe_refund(booking, amount)
        except Exception:
            log.exception("site booking %s: refund failed", booking_id)
            _mail_refund_failed(booking)
            return {"error": "refund_failed", "refund_czk": amount}
        booking_site.set_status(booking_id, "refunded", refunded_czk=amount)
        db.audit("site_booking_refunded", f"id={booking_id} amount={amount}", owner_user_id=owner)
        if amount >= int(booking["total_czk"]):
            _storno_invoice(booking_site.get(booking_id) or booking)
        elif booking.get("invoice_id"):
            _correct_invoice_partial(booking, amount)
    _mail_cancelled(booking_site.get(booking_id) or booking, amount, by_host)
    return {"error": None, "refund_czk": amount}


def _free_reservation(booking: Dict[str, Any]) -> None:
    if not booking.get("reservation_id"):
        return
    row = db.query_one("SELECT * FROM reservation WHERE id = ?", (booking["reservation_id"],))
    if row is None or row["status"] != "active":
        return
    db.update("reservation", row["id"], {"status": "cancelled", "updated_at": db.utcnow()})
    from . import icalsync

    claim.expire_on_cancel(row)
    icalsync._warn_if_guests_registered(row, int(booking["apartment_id"]), "cancelled")


def _stripe_refund(booking: Dict[str, Any], amount_czk: int) -> None:
    account = stripe_connect.account_for_owner(int(booking["owner_user_id"]))
    intent = booking.get("stripe_payment_intent_id")
    if account is None or not intent:
        raise RuntimeError(f"site booking {booking['id']}: cannot refund (no account or intent)")
    api = stripe_connect._api()
    api.v1.refunds.create(
        params={"payment_intent": intent, "amount": int(amount_czk) * 100,
                "metadata": {"site_booking_id": str(booking["id"])}},
        options={"stripe_account": account["stripe_account_id"],
                 "idempotency_key": f"site_booking_cancel_refund_{booking['id']}"},
    )


def _storno_invoice(booking: Dict[str, Any]) -> None:
    if not booking.get("invoice_id"):
        return
    from . import invoices

    try:
        invoices.cancel(int(booking["invoice_id"]),
                        host_i18n.translate("cs", "site_booking.invoice.cancel_reason"),
                        None, None, today=claim.prague_today())
    except ValueError as exc:
        log.warning("site booking %s: no storno (%s)", booking["id"], exc)
        db.audit("site_invoice_needs_correction", f"id={booking['id']} reason={exc}",
                 owner_user_id=int(booking["owner_user_id"]))


def _correct_invoice_partial(booking: Dict[str, Any], amount: int) -> None:
    """Credit note for the refunded part. Never undoes or blocks the refund, mail or status."""
    from . import invoices

    try:
        invoices.correct_partial(int(booking["invoice_id"]), amount,
                                 host_i18n.translate("cs", "site_booking.invoice.cancel_reason"),
                                 None, today=claim.prague_today())
    except Exception as exc:
        log.warning("site booking %s: no credit note (%s)", booking["id"], exc)
        db.audit("site_invoice_needs_correction", f"id={booking['id']} reason={exc}",
                 owner_user_id=int(booking["owner_user_id"]))


# --- mails ---------------------------------------------------------------------


def _mail_cancelled(booking: Dict[str, Any], amount: int, by_host: bool) -> None:
    apartment = booking_webhook._apartment(booking)
    host_email = booking_webhook._host_email(apartment)
    lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
    facts = booking_webhook._facts(booking, apartment, lang)
    facts["refund"] = amount
    if by_host:
        guest_key = "site_booking.mail.cancel_guest_by_host"
    elif amount > 0:
        guest_key = "site_booking.mail.cancel_guest_refund"
    else:
        guest_key = "site_booking.mail.cancel_guest_none"
    if booking["guest_email"]:
        mail.enqueue(
            kind="site_booking_refunded",
            idempotency_key=f"site_booking:{booking['id']}:cancelled",
            to_email=booking["guest_email"],
            subject=host_i18n.translate(lang, "site_booking.mail.cancel_subject", **facts),
            payload={"text": host_i18n.translate(lang, guest_key, **facts),
                     "lang": lang, "reply_to": host_email},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    if host_email:
        host_facts = booking_webhook._facts(booking, apartment, "cs")
        host_facts["refund"] = amount
        host_key = ("site_booking.mail.cancel_host_by_host" if by_host
                    else "site_booking.mail.cancel_host_by_guest")
        mail.enqueue(
            kind="site_booking_host",
            idempotency_key=f"site_booking:{booking['id']}:host_cancelled",
            to_email=host_email,
            subject=host_i18n.translate("cs", "site_booking.mail.host_cancel_subject", **host_facts),
            payload={"text": host_i18n.translate("cs", host_key, **host_facts), "lang": "cs"},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )


def _mail_refund_failed(booking: Dict[str, Any]) -> None:
    apartment = booking_webhook._apartment(booking)
    host_email = booking_webhook._host_email(apartment)
    if not host_email:
        return
    facts = booking_webhook._facts(booking, apartment, "cs")
    mail.enqueue(
        kind="site_booking_host",
        idempotency_key=f"site_booking:{booking['id']}:refund_failed",
        to_email=host_email,
        subject=host_i18n.translate("cs", "site_booking.mail.refund_failed_subject", **facts),
        payload={"text": host_i18n.translate("cs", "site_booking.mail.refund_failed_text", **facts),
                 "lang": "cs"},
        apartment_id=int(booking["apartment_id"]),
        owner_user_id=int(booking["owner_user_id"]),
    )
