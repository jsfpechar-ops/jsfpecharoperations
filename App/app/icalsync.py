"""Fetching and interpreting OTA iCal feeds (Airbnb, Booking.com, Agoda, …).

What these feeds actually carry is very little, and the design has to accept
that rather than pretend otherwise:

* **Airbnb** (help.airbnb.com/article/99): DTSTART, DTEND, UID, SUMMARY
  ("Reserved", or "Airbnb (Not available)" for host blocks) and a DESCRIPTION
  with the reservation URL and the last four digits of the guest phone. No name,
  no e-mail, no headcount — guest details were removed in December 2019.
  **Cancellations** are not flagged; the VEVENT simply disappears on the next
  poll (same as most OTAs).

* **Booking.com** (partner.booking.com calendar sync): dates and a UID, with a
  generic "CLOSED - Not available" summary for both real bookings and manual
  closures — indistinguishable in the feed. Hosts can mark a false positive as
  "ignored". Poll interval is up to ~2 hours. Cancellations = event removed.

* **Agoda** (partnerhub.agoda.com calendar connections): standard iCal export
  for single-room NHA listings; refreshes several times per day. Same
  block-or-booking model as other OTAs — dates + UID, little guest metadata.

* **Vrbo / Expedia / TripAdvisor / Trip.com**: same iCal pattern — blocked
  dates and reservations as VEVENT rows; cancellations by removal. Some exports
  include guest first name in SUMMARY (legacy); treat as a hint only.

* **STATUS:CANCELLED** (RFC 5545): rarely used by OTAs but honoured when
  present instead of waiting for the event to vanish.

Because feeds only say *someone is arriving on these dates*, that is enough to
open a stay record and start chasing guest data. A stay the host recognises as
not a guest stay can be marked "ignored" and will stay that way across syncs.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from icalendar import Calendar

from . import alerts, db

USER_AGENT = "UbyHost/1.0 (+self-hosted Czech foreign-police reporting)"
FETCH_TIMEOUT = 45

# Summaries that mean "not a guest stay". Airbnb and Vrbo are explicit about
# blocks; Booking.com is not, which is why its feeds are treated as bookings.
BLOCK_PATTERNS = (
    r"not available",
    r"unavailable",
    r"blocked",
    r"nedostupn",
    r"blokov",
    r"^busy$",
    r"preparation",
    r"airbnb \(not available\)",
    r"owner block",
    r"host block",
    r"maintenance",
    r"^closed$",
)
_BLOCK_RE = re.compile("|".join(BLOCK_PATTERNS), re.IGNORECASE)

_URL_RE = re.compile(r"(https?://\S+)")
# Airbnb writes "Phone Number (Last 4 Digits): 0431" - the label itself contains
# a digit, so match the trailing group on the line rather than skipping non-digits.
_PHONE_RE = re.compile(r"phone[^\n]*?(\d{4})\s*$", re.IGNORECASE | re.MULTILINE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_GENERIC_SUMMARY_RE = re.compile(
    r"^(reserved|closed|closed\s*-\s*not available|booking|busy|reservation|booked)$",
    re.IGNORECASE,
)

# Host-facing labels for known calendar sources (stored in reservation.source).
PLATFORM_HINTS = (
    ("airbnb", ("airbnb",)),
    ("booking", ("booking.com", "booking")),
    ("agoda", ("agoda",)),
    ("vrbo", ("vrbo", "homeaway")),
    ("expedia", ("expedia",)),
    ("tripadvisor", ("tripadvisor", "flipkey")),
    ("trip", ("trip.com", "ctrip")),
    ("google", ("google.com/calendar", "calendar.google")),
    ("apple", ("icloud.com",)),
)


class FeedError(Exception):
    pass


def fetch_feed(url: str) -> str:
    try:
        response = requests.get(
            url, timeout=FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT, "Accept": "text/calendar"}
        )
    except requests.RequestException as exc:
        raise FeedError(f"Could not download the calendar: {exc}") from exc
    if response.status_code != 200:
        raise FeedError(f"Calendar returned HTTP {response.status_code}.")
    text = response.text or ""
    if "BEGIN:VCALENDAR" not in text.upper():
        raise FeedError(
            "That URL did not return an iCal calendar. Check you copied the whole export link "
            "(it contains '/ical/' and usually ends with '.ics')."
        )
    return text


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _event_status(component) -> str:
    raw = component.get("STATUS")
    return str(raw).strip().upper() if raw else ""


def is_block(summary: str) -> bool:
    text = (summary or "").strip()
    # Booking.com's export uses this exact wording for real reservations as well as
    # manual closures. We import them all as stays; the host can mark a false
    # positive as "ignored" on the stay page.
    if re.match(r"^CLOSED\s*-\s*Not available$", text, re.IGNORECASE):
        return False
    return bool(_BLOCK_RE.search(text))


def _guest_name_hint(summary: str) -> str:
    """Some feeds still put a first name in SUMMARY; use it only as a hint."""
    text = (summary or "").strip()
    if not text or _GENERIC_SUMMARY_RE.match(text) or is_block(text):
        return ""
    return text[:80]


def parse_events(ics_text: str) -> List[Dict[str, Any]]:
    """Extract the stays from an iCal document."""
    calendar = Calendar.from_ical(ics_text)
    events: List[Dict[str, Any]] = []
    for component in calendar.walk("VEVENT"):
        start = _as_date(component.get("DTSTART").dt) if component.get("DTSTART") else None
        end_prop = component.get("DTEND")
        end = _as_date(end_prop.dt) if end_prop else None
        if not start:
            continue
        if not end:
            # A stay with no end is treated as a single night.
            end = start + timedelta(days=1)

        summary = str(component.get("SUMMARY") or "").strip()
        description = str(component.get("DESCRIPTION") or "").replace("\\n", "\n").strip()
        uid = str(component.get("UID") or "").strip()
        if not uid:
            # Fall back to a stable synthetic key so re-syncs do not duplicate.
            uid = f"synthetic-{start.isoformat()}-{end.isoformat()}-{summary[:20]}"

        status = _event_status(component)
        url_match = _URL_RE.search(description) or _URL_RE.search(str(component.get("URL") or ""))
        phone_match = _PHONE_RE.search(description)
        email_match = _EMAIL_RE.search(description)

        events.append(
            {
                "uid": uid,
                "date_from": start.isoformat(),
                "date_to": end.isoformat(),
                "summary": summary,
                "description": description,
                "is_block": is_block(summary),
                "is_cancelled": status == "CANCELLED",
                "reservation_url": url_match.group(1).rstrip(".,);") if url_match else None,
                "phone_last4": phone_match.group(1) if phone_match else None,
                "guest_email": email_match.group(0) if email_match else None,
                "name_hint": _guest_name_hint(summary),
            }
        )
    return events


def platform_of(url: str, ics_text: str = "") -> str:
    """Which portal a calendar came from, for labelling stays on the dashboard."""
    text = f"{url or ''} {ics_text[:800]}".lower()
    for name, hints in PLATFORM_HINTS:
        if any(hint in text for hint in hints):
            return name
    return "ical"


def _cancel_existing_stay(apartment_id: int, uid: str, date_from: str, now: str, stats: Dict[str, Any]) -> None:
    """Mark an active future stay as cancelled when the feed signals cancellation."""
    existing = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND uid = ?",
        (apartment_id, uid),
    )
    if not existing or existing["status"] != "active":
        return
    if existing["date_from"] < date.today().isoformat():
        return
    reported = db.query_one(
        "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ? AND submit_state = 'sent'",
        (existing["id"],),
    )
    if reported and reported["n"]:
        alerts.raise_alert(
            "warning",
            "cancelled_after_report",
            f"A stay from {existing['date_from']} was cancelled in the calendar after it had "
            "already been reported to the police.",
            "Check whether the booking was cancelled or merely moved.",
            dedupe_key=f"cancelled_after_report:{existing['id']}",
            apartment_id=apartment_id,
            reservation_id=existing["id"],
        )
        return
    db.update("reservation", existing["id"], {"status": "cancelled", "updated_at": now})
    stats["cancelled"] += 1


def sync_feed(feed, keep_past_days: int = 400) -> Dict[str, Any]:
    """Reconcile one feed into the reservation table."""
    now = db.utcnow()
    stats = {"created": 0, "updated": 0, "cancelled": 0, "blocks_skipped": 0}
    try:
        ics_text = fetch_feed(feed["url"])
        events = parse_events(ics_text)
    except (FeedError, ValueError) as exc:
        db.update(
            "ical_feed",
            feed["id"],
            {"last_sync_at": now, "last_status": "error", "last_error": str(exc)},
        )
        alerts.raise_alert(
            "warning",
            "feed_error",
            f"Calendar '{feed['own_name'] or feed['label'] or feed['id']}' could not be synchronised.",
            str(exc),
            dedupe_key=f"feed_error:{feed['id']}",
            apartment_id=feed["apartment_id"],
        )
        return {"error": str(exc), **stats}

    alerts.resolve(f"feed_error:{feed['id']}")
    platform = platform_of(feed["url"], ics_text)
    seen_uids: List[str] = []

    for event in events:
        if event["is_block"]:
            stats["blocks_skipped"] += 1
            continue
        if event.get("is_cancelled"):
            _cancel_existing_stay(feed["apartment_id"], event["uid"], event["date_from"], now, stats)
            continue
        seen_uids.append(event["uid"])
        existing = db.query_one(
            "SELECT * FROM reservation WHERE apartment_id = ? AND uid = ?",
            (feed["apartment_id"], event["uid"]),
        )
        payload = {
            "date_from": event["date_from"],
            "date_to": event["date_to"],
            "summary": event["summary"] or event["name_hint"] or None,
            "reservation_url": event["reservation_url"],
            "phone_last4": event["phone_last4"],
            "ical_feed_id": feed["id"],
            "updated_at": now,
        }
        if existing:
            # A host decision to ignore a range is never undone by a re-sync.
            if existing["status"] == "ignored":
                continue
            changed = {
                k: v
                for k, v in payload.items()
                if k != "updated_at" and (existing[k] if k in existing.keys() else None) != v
            }
            if existing["status"] == "cancelled":
                changed["status"] = "active"
            if changed:
                changed["updated_at"] = now
                db.update("reservation", existing["id"], changed)
                stats["updated"] += 1
            if event["guest_email"] and not existing["guest_email"]:
                db.update("reservation", existing["id"], {"guest_email": event["guest_email"]})
        else:
            db.insert(
                "reservation",
                {
                    "apartment_id": feed["apartment_id"],
                    "ical_feed_id": feed["id"],
                    "source": platform,
                    "uid": event["uid"],
                    "date_from": event["date_from"],
                    "date_to": event["date_to"],
                    "summary": payload["summary"],
                    "reservation_url": event["reservation_url"],
                    "phone_last4": event["phone_last4"],
                    "guest_email": event["guest_email"],
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            stats["created"] += 1

    # A future stay that has vanished from the feed was cancelled upstream.
    # Past stays are left alone: they may already be reported to the police.
    cutoff = date.today().isoformat()
    candidates = db.query(
        "SELECT id, uid, date_from FROM reservation "
        "WHERE apartment_id = ? AND ical_feed_id = ? AND status = 'active' AND date_from >= ?",
        (feed["apartment_id"], feed["id"], cutoff),
    )
    for row in candidates:
        if row["uid"] in seen_uids:
            continue
        reported = db.query_one(
            "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ? AND submit_state = 'sent'",
            (row["id"],),
        )
        if reported and reported["n"]:
            alerts.raise_alert(
                "warning",
                "cancelled_after_report",
                f"A stay from {row['date_from']} disappeared from the calendar after it had "
                "already been reported to the police.",
                "Check whether the booking was cancelled or merely moved.",
                dedupe_key=f"cancelled_after_report:{row['id']}",
                apartment_id=feed["apartment_id"],
                reservation_id=row["id"],
            )
            continue
        db.update("reservation", row["id"], {"status": "cancelled", "updated_at": now})
        stats["cancelled"] += 1

    db.update(
        "ical_feed",
        feed["id"],
        {"last_sync_at": now, "last_status": "ok", "last_error": None},
    )
    return stats


def sync_all(apartment_id: Optional[int] = None) -> Dict[str, Any]:
    """Sync every active feed, optionally limited to one apartment."""
    if apartment_id:
        feeds = db.query(
            "SELECT * FROM ical_feed WHERE active = 1 AND apartment_id = ?", (apartment_id,)
        )
    else:
        feeds = db.query(
            "SELECT f.* FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id "
            "WHERE f.active = 1 AND a.active = 1"
        )
    totals = {"feeds": 0, "created": 0, "updated": 0, "cancelled": 0, "errors": 0}
    for feed in feeds:
        totals["feeds"] += 1
        stats = sync_feed(feed)
        if stats.get("error"):
            totals["errors"] += 1
            continue
        for key in ("created", "updated", "cancelled"):
            totals[key] += stats.get(key, 0)
    db.set_setting("last_ical_sync", db.utcnow())
    return totals
