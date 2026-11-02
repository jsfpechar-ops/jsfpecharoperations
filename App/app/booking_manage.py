"""Data for the guest booking page (brief 0821)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict

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
    can_cancel = status == "paid" and not booking_cancel.started(booking)
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
