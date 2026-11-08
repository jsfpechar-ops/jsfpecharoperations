"""Data for the guest booking page (brief 0821)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

from . import booking_cancel, booking_site, db

VISIBLE = ("paid", "cancelled", "refunded", "clash_refunded")


def mask_email(email: str) -> str:
    local, _, domain = (email or "").partition("@")
    return f"{local[:1]}***@{domain}" if local and domain else ""


def day_label(iso: str, lang: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day}. {d.month}. {d.year}" if lang == "cs" else iso


def deadline_label(booking: Dict[str, Any], checkin_hour: int, lang: str) -> str:
    """Until when the full refund holds; "" for a non-refundable booking."""
    moment = booking_site.check_in_moment(booking["date_from"], checkin_hour)
    policy = booking["cancellation_policy"]
    if policy == "flexible":
        moment -= timedelta(hours=24)
    elif policy == "moderate":
        moment -= timedelta(days=5)
    else:
        return ""
    if lang == "cs":
        return f"{moment.day}. {moment.month}. {moment.year} {moment:%H:%M}"
    return f"{moment:%Y-%m-%d %H:%M}"


def view(booking: Dict[str, Any], lang: str) -> Dict[str, Any]:
    """Everything booking_manage.html prints."""
    s = booking_site.settings(int(booking["apartment_id"]))
    apartment = db.query_one("SELECT internal_name FROM apartment WHERE id = ?",
                             (booking["apartment_id"],))
    status = booking["status"]
    state = "refunded" if status == "refunded" else status
    nights = int(booking["nights"])
    can_cancel = (status == "paid" and booking.get("pay_method") != "direct" and not booking_cancel.started(booking))
    return {
        "id": int(booking["id"]),
        "state": state,
        "tone": "done" if status == "paid" else "neutral",
        "name": (apartment["internal_name"] if apartment else "") or "",
        "arrive": day_label(booking["date_from"], lang),
        "depart": day_label(booking["date_to"], lang),
        "guests": int(booking["guests"]),
        "total": int(booking["total_czk"]),
        "refunded": int(booking["refunded_czk"] or 0),
        "email": mask_email(booking["guest_email"] or ""),
        "city_tax": int(s["city_tax_czk"]) * int(booking["guests"]) * nights,
        "policy": booking["cancellation_policy"],
        "deadline": deadline_label(booking, s["checkin_hour"], lang),
        "can_cancel": can_cancel,
        "refund_now": booking_cancel.refund_now(booking, by_host=False) if can_cancel else 0,
        "has_invoice": bool(booking.get("invoice_id")),
        "has_correction": bool(booking.get("invoice_id")) and db.query_one(
            "SELECT id FROM invoice WHERE corrects_invoice_id = ?",
            (int(booking["invoice_id"]),)) is not None,
    }


def calendar_ics(booking: Dict[str, Any], name: str) -> str:
    """One all-day event for the guest's own calendar. No personal data."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    start = date.fromisoformat(booking["date_from"]).strftime("%Y%m%d")
    end = date.fromisoformat(booking["date_to"]).strftime("%Y%m%d")
    summary = (name or "").replace("\\", " ").replace(",", " ").replace(";", " ").replace("\n", " ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//UbyHost//Booking//CS", "BEGIN:VEVENT",
             f"UID:ubyhost-booking-{int(booking['id'])}@ubyhost.cz", f"DTSTAMP:{stamp}",
             f"DTSTART;VALUE=DATE:{start}", f"DTEND;VALUE=DATE:{end}",
             f"SUMMARY:{summary}", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def host_rows(apartment_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """The host's recent site bookings: short name, dates, total, status, actions."""
    rows = db.query(
        "SELECT * FROM site_booking WHERE apartment_id = ? AND status IN ('requested', 'expired',"
        " 'paid', 'cancelled', 'refunded', 'clash_refunded')"
        " AND (status != 'expired' OR pay_method = 'direct')"
        " ORDER BY date_from DESC, id DESC LIMIT ?",
        (apartment_id, limit),
    )
    out = []
    for row in rows:
        b = dict(row)
        parts = (b["guest_name"] or "").split()
        short = parts[0] + (f" {parts[-1][:1]}." if len(parts) > 1 else "") if parts else ""
        d_from, d_to = date.fromisoformat(b["date_from"]), date.fromisoformat(b["date_to"])
        out.append({
            "id": int(b["id"]), "name": short, "status": b["status"],
            "dates": f"{d_from.day}.–{d_to.day}. {d_to.month}.",
            "total": int(b["total_czk"]),
            "direct": b["pay_method"] == "direct",
            "can_confirm": b["pay_method"] == "direct" and b["status"] in ("requested", "expired"),
            "can_decline": b["pay_method"] == "direct" and b["status"] in ("requested", "expired"),
            "can_cancel": b["status"] == "paid",
            "can_retry": (b["status"] == "cancelled" and b["pay_method"] != "direct"
                          and not int(b["refunded_czk"] or 0)),
            "status_key": ("cancelled_direct" if b["pay_method"] == "direct" and b["status"] == "cancelled"
                           else b["status"]),
        })
    return out

