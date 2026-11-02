"""Booking site iCal export (brief 0817, plan booking-site-v1).

Website and manual stays only, so OTAs block nights sold elsewhere without
their own bookings looping back to them. No personal data in the feed.
"""
from __future__ import annotations

import hmac
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from . import booking_site, db

EXPORT_SOURCES = ("site", "manual")
KEEP_PAST_DAYS = 30


def apartment_for_slug(slug: str) -> Optional[int]:
    """Live or historic slug -> apartment id (feeds survive renames)."""
    row = db.query_one("SELECT apartment_id FROM property_slug WHERE slug = ?", (slug,))
    if row is None:
        row = db.query_one(
            "SELECT apartment_id FROM property_slug_history WHERE old_slug = ?", (slug,)
        )
    return int(row["apartment_id"]) if row else None


def token_ok(apartment_id: int, token: str) -> bool:
    return hmac.compare_digest(booking_site.ical_token(apartment_id), str(token or ""))


def _d(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%Y%m%d")


def export_ics(apartment_id: int, *, today: Optional[date] = None) -> str:
    today = today or date.today()
    since = (today - timedelta(days=KEEP_PAST_DAYS)).isoformat()
    rows = db.query(
        "SELECT id, date_from, date_to FROM reservation"
        " WHERE apartment_id = ? AND status = 'active' AND archived_at IS NULL"
        " AND source IN ('site', 'manual') AND date_to >= ?"
        " ORDER BY date_from, id",
        (apartment_id, since),
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UbyHost//Booking site//CS",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for row in rows:
        lines += [
            "BEGIN:VEVENT",
            f"UID:ubyhost-{row['id']}@ubyhost.cz",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{_d(row['date_from'])}",
            f"DTEND;VALUE=DATE:{_d(row['date_to'])}",
            "SUMMARY:Reserved",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
