"""Booking site webhook (brief 0816, plan booking-site-v1).

paid session  -> lock, re-check, reservation (source 'site') + mails;
                 nights sold meanwhile -> full automatic refund + mails.
expired/failed session -> booking expired, hold released.
Every path is idempotent: Stripe retries until the handler returns.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

from . import booking_site, config, db, host_i18n, mail, stripe_connect

log = logging.getLogger(__name__)

PAID_EVENTS = ("checkout.session.completed", "checkout.session.async_payment_succeeded")
END_EVENTS = ("checkout.session.expired", "checkout.session.async_payment_failed")
EVENTS = PAID_EVENTS + END_EVENTS


def is_booking_event(event: Dict[str, Any]) -> bool:
    obj = (event.get("data") or {}).get("object") or {}
    return event.get("type") in EVENTS and bool((obj.get("metadata") or {}).get("site_booking_id"))


def handle(event: Dict[str, Any]) -> None:
    obj = (event.get("data") or {}).get("object") or {}
    booking = booking_site.by_session(str(obj.get("id") or ""))
    if booking is None:
        log.warning("booking webhook: no booking for session %s", obj.get("id"))
        return
    if event.get("type") in END_EVENTS:
        _expire(booking)
        return
    if obj.get("payment_status") != "paid":
        return  # async method still pending; async_payment_succeeded follows
    if booking["status"] not in ("pending", "expired"):
        return  # already handled
    _confirm(booking, str(obj.get("payment_intent") or ""))


def _expire(booking: Dict[str, Any]) -> None:
    if booking["status"] != "pending":
        return
    booking_site.set_status(int(booking["id"]), "expired")
    if booking.get("hold_id"):
        db.execute("DELETE FROM booking_hold WHERE id = ?", (booking["hold_id"],))


def _confirm(booking: Dict[str, Any], payment_intent: str) -> None:
    now = db.utcnow()
    reservation_id: Optional[int] = None
    with db.immediate() as cur:
        db.lock_key(cur, "booking_site_dates", int(booking["apartment_id"]))
        # handle() copies status before this lock. Stripe often delivers
        # completed and async_payment_succeeded together, so a second call
        # still looks pending. Without this re-read, the reservation we just
        # wrote looks like a double booking and the guest is refunded in full.
        cur.execute(
            "SELECT status FROM site_booking WHERE id = ?", (booking["id"],)
        )
        live = cur.fetchone()
        if live is None or live["status"] not in ("pending", "expired"):
            return
        cur.execute(
            "SELECT id FROM reservation WHERE apartment_id = ? AND status = 'active'"
            " AND date_from < ? AND date_to > ?",
            (booking["apartment_id"], booking["date_to"], booking["date_from"]),
        )
        clash = cur.fetchone() is not None
        if not clash:
            cur.execute(
                "INSERT INTO reservation (apartment_id, source, uid, date_from, date_to,"
                " summary, expected_guests_override, guest_email, status, created_at, updated_at)"
                " VALUES (?, 'site', ?, ?, ?, ?, ?, ?, 'active', ?, ?) RETURNING id",
                (booking["apartment_id"], f"site-{booking['id']}", booking["date_from"],
                 booking["date_to"], booking["guest_name"], booking["guests"],
                 booking["guest_email"], now, now),
            )
            reservation_id = int(cur.fetchone()["id"])
            cur.execute(
                "UPDATE site_booking SET status = 'paid', reservation_id = ?,"
                " stripe_payment_intent_id = ?, paid_at = ?, updated_at = ?"
                " WHERE id = ? AND status IN ('pending', 'expired')",
                (reservation_id, payment_intent or None, now, now, booking["id"]),
            )
        if booking.get("hold_id"):
            cur.execute("DELETE FROM booking_hold WHERE id = ?", (booking["hold_id"],))
    if clash:
        _refund_clash(booking, payment_intent)
        return
    db.audit("site_booking_paid", f"id={booking['id']} reservation={reservation_id}",
             owner_user_id=int(booking["owner_user_id"]))
    _mail_confirmed(booking_site.get(int(booking["id"])) or booking, int(reservation_id))
    try:  # best effort: the booking is already confirmed and mailed
        from . import booking_invoice

        booking_invoice.ensure(int(booking["id"]))
    except Exception:
        log.exception("site booking %s: invoice failed", booking["id"])


def _refund_clash(booking: Dict[str, Any], payment_intent: str) -> None:
    """Double booking: full refund on the host's account (raises -> Stripe retries)."""
    account = stripe_connect.account_for_owner(int(booking["owner_user_id"]))
    if account is None or not payment_intent:
        raise RuntimeError(f"site booking {booking['id']}: cannot refund (no account or intent)")
    api = stripe_connect._api()
    api.v1.refunds.create(
        params={"payment_intent": payment_intent,
                "metadata": {"site_booking_id": str(booking["id"])}},
        options={"stripe_account": account["stripe_account_id"],
                 "idempotency_key": f"site_booking_clash_refund_{booking['id']}"},
    )
    booking_site.set_status(int(booking["id"]), "clash_refunded",
                            refunded_czk=int(booking["total_czk"]),
                            stripe_payment_intent_id=payment_intent)
    db.audit("site_booking_clash_refunded", f"id={booking['id']} amount={booking['total_czk']}",
             owner_user_id=int(booking["owner_user_id"]))
    _mail_clash(booking)


# --- mails ---------------------------------------------------------------------


def _apartment(booking: Dict[str, Any]):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (booking["apartment_id"],))


def _host_email(apartment) -> str:
    from . import mail_notify

    return mail_notify._entity_contact_email(apartment["legal_entity_id"]) if apartment else ""


def _dates(booking: Dict[str, Any], lang: str) -> str:
    def one(iso: str) -> str:
        d = date.fromisoformat(iso)
        return f"{d.day}. {d.month}. {d.year}" if lang == "cs" else iso
    return f"{one(booking['date_from'])} – {one(booking['date_to'])}"


def _facts(booking: Dict[str, Any], apartment, lang: str) -> Dict[str, Any]:
    return {
        "property": apartment["internal_name"] if apartment else "",
        "dates": _dates(booking, lang),
        "guests": booking["guests"],
        "total": booking["total_czk"],
        "name": booking["guest_name"] or "",
        "email": booking["guest_email"] or "",
        "policy": host_i18n.translate(lang, f"pp.book.policy.{booking['cancellation_policy']}"),
    }


def _mail_confirmed(booking: Dict[str, Any], reservation_id: int) -> None:
    from . import guest_slug

    apartment = _apartment(booking)
    host_email = _host_email(apartment)
    lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
    facts = _facts(booking, apartment, lang)
    key = guest_slug.link_key(apartment) if apartment else ""
    link = f"{config.PUBLIC_BASE_URL.rstrip('/')}/l/{key}/{reservation_id}" if key else ""
    text_key = ("site_booking.mail.guest_text_direct" if booking.get("pay_method") == "direct"
                else "site_booking.mail.guest_text")
    text = host_i18n.translate(lang, text_key, **facts)
    if link:
        text += "\n\n" + host_i18n.translate(lang, "site_booking.mail.guest_register", link=link)
    manage_key = ("site_booking.mail.guest_manage_direct" if booking.get("pay_method") == "direct"
                  else "site_booking.mail.guest_manage")
    text += "\n\n" + host_i18n.translate(
        lang, manage_key, link=booking_site.manage_url(booking))
    if booking["guest_email"]:
        mail.enqueue(
            kind="site_booking_confirmed",
            idempotency_key=f"site_booking:{booking['id']}:confirmed",
            to_email=booking["guest_email"],
            subject=host_i18n.translate(lang, "site_booking.mail.guest_subject", **facts),
            payload={"text": text, "lang": lang, "reply_to": host_email},
            reservation_id=reservation_id,
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    if host_email:
        host_facts = _facts(booking, apartment, "cs")
        host_key = ("site_booking.mail.host_text_direct" if booking.get("pay_method") == "direct"
                    else "site_booking.mail.host_text")
        mail.enqueue(
            kind="site_booking_host",
            idempotency_key=f"site_booking:{booking['id']}:host_new",
            to_email=host_email,
            subject=host_i18n.translate("cs", "site_booking.mail.host_subject", **host_facts),
            payload={"text": host_i18n.translate("cs", host_key, **host_facts),
                     "lang": "cs"},
            reservation_id=reservation_id,
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )


def _mail_clash(booking: Dict[str, Any]) -> None:
    apartment = _apartment(booking)
    host_email = _host_email(apartment)
    lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
    facts = _facts(booking, apartment, lang)
    if booking["guest_email"]:
        mail.enqueue(
            kind="site_booking_refunded",
            idempotency_key=f"site_booking:{booking['id']}:clash_refund",
            to_email=booking["guest_email"],
            subject=host_i18n.translate(lang, "site_booking.mail.clash_subject", **facts),
            payload={"text": host_i18n.translate(lang, "site_booking.mail.clash_text", **facts),
                     "lang": lang, "reply_to": host_email},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    if host_email:
        host_facts = _facts(booking, apartment, "cs")
        mail.enqueue(
            kind="site_booking_host",
            idempotency_key=f"site_booking:{booking['id']}:host_clash",
            to_email=host_email,
            subject=host_i18n.translate("cs", "site_booking.mail.host_clash_subject", **host_facts),
            payload={"text": host_i18n.translate("cs", "site_booking.mail.host_clash_text", **host_facts),
                     "lang": "cs"},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
