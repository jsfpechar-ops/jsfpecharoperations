"""Invoice for a paid site booking (brief 0820, plan booking-site-v1).

Reuses the host invoice flow: same numbering, same stored PDF. Best effort:
a host without invoice details (seller name, seat, registry) gets no invoice
and the booking stays valid; the guest's download link retries.
"""
from __future__ import annotations

import logging
from typing import Optional

from . import booking_site, claim, db, host_i18n, invoices

log = logging.getLogger(__name__)


def _form(booking: dict, lang: str) -> dict:
    cleaning = int(booking["cleaning_fee_czk"])
    note = (host_i18n.translate(lang, "site_booking.invoice.note", cleaning=cleaning)
            if cleaning else "")
    return {
        "lang": lang,
        "stay_price": str(int(booking["total_czk"])),
        "stay_vat_rate": "12",
        "buyer_name": booking["guest_name"] or "",
        "buyer_email": booking["guest_email"] or "",
        "already_paid": "1",
        "paid_via": "custom",
        "paid_via_custom": host_i18n.translate(lang, "site_booking.invoice.paid_via"),
        "note": note,
    }


def ensure(booking_id: int) -> Optional[int]:
    """The invoice id of a paid booking, issuing it if needed; None if it cannot be issued."""
    booking = booking_site.get(booking_id)
    if booking is None or booking["status"] not in ("paid", "cancelled", "refunded"):
        return None
    if booking.get("invoice_id"):
        return int(booking["invoice_id"])
    if not booking.get("reservation_id"):
        return None
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (booking["apartment_id"],))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (booking["reservation_id"],))
    entity = (db.query_one("SELECT * FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))
              if apartment is not None and apartment["legal_entity_id"] else None)
    if apartment is None or reservation is None or entity is None:
        _skipped(booking, "no_entity")
        return None
    lang = booking["lang"] if booking["lang"] in ("cs", "en") else "cs"
    stay = {"reservation": reservation, "property_name": apartment["internal_name"] or ""}
    draft = invoices.build_draft(entity, _form(booking, lang), lang,
                                 today=claim.prague_today(), stay=stay)
    draft.update({"legal_entity_id": entity["id"], "owner_user_id": int(booking["owner_user_id"])})
    issues = invoices.validate_for_issue(draft)
    if issues:
        _skipped(booking, issues[0].message)
        return None
    try:
        invoice_id = invoices.issue(draft, None)
    except invoices.StayLimit as limit:
        if not limit.invoice_id:
            _skipped(booking, limit.key)
            return None
        invoice_id = int(limit.invoice_id)  # the host already invoiced this stay by hand
    except ValueError as exc:
        _skipped(booking, str(exc))
        return None
    db.execute(
        "UPDATE site_booking SET invoice_id = ?, updated_at = ? WHERE id = ? AND invoice_id IS NULL",
        (invoice_id, db.utcnow(), booking_id),
    )
    return invoice_id


def _skipped(booking: dict, reason: str) -> None:
    log.warning("site booking %s: no invoice (%s)", booking["id"], reason)
    db.audit("site_invoice_skipped", f"id={booking['id']} reason={reason}",
             owner_user_id=int(booking["owner_user_id"]))
