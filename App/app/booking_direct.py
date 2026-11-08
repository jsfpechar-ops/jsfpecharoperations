"""Host confirmation of a direct booking request (brief 0998).

The guest paid the host outside the platform (IBAN, Revolut, cash). The host
marks it paid by hand; only then is the reservation created. Nothing here
talks to Stripe and nothing is refunded automatically.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from . import booking_site, config, db, host_i18n, mail

log = logging.getLogger(__name__)


def confirm(booking_id: int, owner_user_id: int) -> Dict[str, Any]:
    """{"error": None} or {"error": not_found | not_confirmable | taken}.
    A request that expired can still be confirmed while its dates are free."""
    booking = booking_site.get(booking_id)
    if (booking is None or int(booking["owner_user_id"]) != owner_user_id
            or booking["pay_method"] != "direct"):
        return {"error": "not_found"}
    now = db.utcnow()
    with db.immediate() as cur:
        db.lock_key(cur, "booking_site_dates", int(booking["apartment_id"]))
        cur.execute("SELECT status FROM site_booking WHERE id = ?", (booking_id,))
        live = cur.fetchone()
        if live is None or live["status"] not in ("requested", "expired"):
            return {"error": "not_confirmable"}
        cur.execute(
            "SELECT id FROM reservation WHERE apartment_id = ? AND status = 'active'"
            " AND date_from < ? AND date_to > ?",
            (booking["apartment_id"], booking["date_to"], booking["date_from"]),
        )
        if cur.fetchone() is not None:
            return {"error": "taken"}
        cur.execute(
            "SELECT id FROM booking_hold WHERE apartment_id = ? AND expires_at > ?"
            " AND date_from < ? AND date_to > ? AND id != ?",
            (booking["apartment_id"], now, booking["date_to"], booking["date_from"],
             booking["hold_id"] or 0),
        )
        if cur.fetchone() is not None:
            return {"error": "taken"}
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
            "UPDATE site_booking SET status = 'paid', reservation_id = ?, paid_at = ?,"
            " updated_at = ? WHERE id = ? AND status IN ('requested', 'expired')",
            (reservation_id, now, now, booking_id),
        )
        if booking["hold_id"]:
            cur.execute("DELETE FROM booking_hold WHERE id = ?", (booking["hold_id"],))
    db.audit("site_booking_paid", f"id={booking_id} reservation={reservation_id} direct",
             owner_user_id=owner_user_id)
    from . import booking_webhook

    booking_webhook._mail_confirmed(booking_site.get(booking_id) or booking, reservation_id)
    return {"error": None}


def decline(booking_id: int, owner_user_id: int) -> Dict[str, Any]:
    """The host refuses a request: it becomes `cancelled` and the dates are freed."""
    booking = booking_site.get(booking_id)
    if (booking is None or int(booking["owner_user_id"]) != owner_user_id
            or booking["pay_method"] != "direct"):
        return {"error": "not_found"}
    with db.immediate() as cur:
        db.lock_key(cur, "booking_site_dates", int(booking["apartment_id"]))
        cur.execute(
            "UPDATE site_booking SET status = 'cancelled', cancelled_at = ?, updated_at = ?"
            " WHERE id = ? AND status IN ('requested', 'expired')",
            (db.utcnow(), db.utcnow(), booking_id))
        if cur.rowcount != 1:
            return {"error": "not_confirmable"}
    if booking["hold_id"]:
        db.execute("DELETE FROM booking_hold WHERE id = ?", (booking["hold_id"],))
    db.audit("site_booking_declined", f"id={booking_id}", owner_user_id=owner_user_id)
    _mail_declined(booking)
    return {"error": None}


def _mail_declined(booking: Dict[str, Any]) -> None:
    """Tell the guest the host declined, so they do not pay. Best effort."""
    try:
        from . import booking_webhook

        if not booking["guest_email"]:
            return
        apartment = booking_webhook._apartment(booking)
        lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
        facts = booking_webhook._facts(booking, apartment, lang)
        mail.enqueue(
            kind="site_booking_refunded",
            idempotency_key=f"site_booking:{booking['id']}:declined",
            to_email=booking["guest_email"],
            subject=host_i18n.translate(lang, "site_booking.mail.declined_subject", **facts),
            payload={"text": host_i18n.translate(lang, "site_booking.mail.declined_text", **facts),
                     "lang": lang, "reply_to": booking_webhook._host_email(apartment)},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    except Exception:
        log.exception("site booking %s: decline mail failed", booking.get("id"))


def notify_request(booking: Dict[str, Any]) -> None:
    """One short mail to the host: a request is waiting. Best effort."""
    try:
        from . import booking_webhook

        apartment = booking_webhook._apartment(booking)
        host_email = booking_webhook._host_email(apartment)
        if not host_email:
            return
        facts = booking_webhook._facts(booking, apartment, "cs")
        facts["link"] = (f"{config.PUBLIC_BASE_URL.rstrip('/')}"
                         f"/apartments/{int(booking['apartment_id'])}/booking-site")
        mail.enqueue(
            kind="site_booking_request_host",
            idempotency_key=f"site_booking:{booking['id']}:request_host",
            to_email=host_email,
            subject=host_i18n.translate("cs", "site_booking.mail.request_subject", **facts),
            payload={"text": host_i18n.translate("cs", "site_booking.mail.request_text", **facts),
                     "lang": "cs"},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    except Exception:
        log.exception("site booking %s: request mail failed", booking.get("id"))


def notify_request_guest(booking: Dict[str, Any]) -> None:
    """The guest's copy of the payment details. Best effort."""
    try:
        from . import booking_rails, booking_webhook

        apartment = booking_webhook._apartment(booking)
        lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
        facts = booking_webhook._facts(booking, apartment, lang)
        lines = []
        for rail in booking_rails.guest_view(int(booking["apartment_id"]), booking):
            if rail["key"] == "iban":
                lines.append(host_i18n.translate(lang, "site_booking.mail.request_guest_iban",
                                                 iban=rail["iban"], vs=rail["vs"], amount=rail["amount"]))
            elif rail["key"] == "revolut":
                lines.append(host_i18n.translate(lang, "site_booking.mail.request_guest_revolut", link=rail["link"]))
            else:
                lines.append(rail["note"] or host_i18n.translate(lang, "pp.book.req_cash_default"))
        facts["ways"] = "\n\n".join(lines)
        facts["link"] = booking_site.manage_url(booking)
        mail.enqueue(
            kind="site_booking_request_guest",
            idempotency_key=f"site_booking:{booking['id']}:request_guest",
            to_email=booking["guest_email"],
            subject=host_i18n.translate(lang, "site_booking.mail.request_guest_subject", **facts),
            payload={"text": host_i18n.translate(lang, "site_booking.mail.request_guest_text", **facts)
                     + "\n\n" + host_i18n.translate(lang, "site_booking.mail.request_guest_link", link=facts["link"]),
                     "lang": lang, "reply_to": booking_webhook._host_email(apartment)},
            apartment_id=int(booking["apartment_id"]),
            owner_user_id=int(booking["owner_user_id"]),
        )
    except Exception:
        log.exception("site booking %s: guest request mail failed", booking.get("id"))
