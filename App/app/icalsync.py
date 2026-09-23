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

Two things these feeds can express that this model cannot are reported to the
host instead of being guessed at: a repeating event (``RRULE``/``RDATE``) is
imported as its first occurrence only, and a UID that appears more than once in
one document is imported once.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from icalendar import Calendar

from . import alerts, config, db, deadlines, host_i18n
from .feed_fetch import CalendarFetchError, fetch_calendar_text
from .feed_url import FeedUrlError

log = logging.getLogger("ubyhost.icalsync")

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


# Properties that make an event repeat. We import the first occurrence only -
# expanding a recurrence would invent stays (and reporting deadlines) the feed
# never confirmed - so a host has to be told the rest are missing.
RECURRENCE_PROPERTIES = ("RRULE", "RDATE", "EXDATE")

# A feed must still return at least this fraction of the future stays already
# stored for it before any of them is treated as cancelled upstream. Below it,
# the sync is assumed to be broken rather than the calendar empty.
FEED_COMPLETENESS_THRESHOLD = 0.5


def fetch_feed(url: str) -> str:
    try:
        return fetch_calendar_text(url)
    except CalendarFetchError as exc:
        raise FeedError(str(exc)) from exc
    except FeedUrlError as exc:
        raise FeedError(str(exc)) from exc


def _as_date(value: Any) -> Optional[date]:
    """The local calendar date an iCal value means.

    ``DTSTART:20260910T230000Z`` is 10 September 23:00 UTC, which in Prague is
    01:00 on the 11th: taking ``.date()`` off the aware datetime stores a stay
    that starts a day early. So an aware value is converted to
    ``config.TIMEZONE`` first. A floating value (no tzinfo) already means local
    wall-clock time to the feed's author, and a ``VALUE=DATE`` value is a bare
    date, so both are taken as they are.
    """
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(ZoneInfo(config.TIMEZONE))
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


def _synthetic_uid(summary: str, description: str, sequence: str) -> str:
    """A key for a feed that sends no UID at all.

    Deliberately not built from the dates: a UID-less booking that moves would
    otherwise look like a new booking and the old one would be cancelled, losing
    the guest details collected against it.
    """
    digest = hashlib.sha1(
        "\x1f".join([summary or "", description or "", sequence or ""]).encode("utf-8")
    ).hexdigest()
    return f"synthetic-{digest[:16]}"


def _legacy_synthetic_uid(date_from: str, date_to: str, summary: str) -> str:
    """The key used before W4.6, which embedded the dates. Read-only."""
    return f"synthetic-{date_from}-{date_to}-{summary[:20]}"


def parse_events(ics_text: str) -> List[Dict[str, Any]]:
    """Extract the stays from an iCal document."""
    calendar = Calendar.from_ical(ics_text)
    calendar_cancelled = str(calendar.get("METHOD") or "").strip().upper() == "CANCEL"
    events: List[Dict[str, Any]] = []
    synthetic_seen: set = set()
    for component in calendar.walk("VEVENT"):
        start = _as_date(component.get("DTSTART").dt) if component.get("DTSTART") else None
        end_prop = component.get("DTEND")
        end = _as_date(end_prop.dt) if end_prop else None
        if not start:
            continue
        if not end:
            duration_prop = component.get("DURATION")
            duration = duration_prop.dt if duration_prop else None
            if isinstance(duration, timedelta) and duration > timedelta(0):
                end = start + duration
            else:
                # A stay with no end or duration is treated as a single night.
                end = start + timedelta(days=1)

        summary = str(component.get("SUMMARY") or "").strip()
        description = str(component.get("DESCRIPTION") or "").replace("\\n", "\n").strip()
        sequence = str(component.get("SEQUENCE") or "").strip()
        uid = str(component.get("UID") or "").strip()
        if not uid:
            # Fall back to a stable synthetic key so re-syncs do not duplicate.
            uid = _synthetic_uid(summary, description, sequence)
            if uid in synthetic_seen:
                # Two bookings this feed left unlabelled and identically
                # worded are still two bookings. The collision is ours, not
                # the feed's, so the dates keep them apart and neither is
                # dropped as a duplicate.
                uid = f"{uid}-{start.isoformat()}"
            synthetic_seen.add(uid)

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
                "is_cancelled": calendar_cancelled or status in ("CANCELLED", "CANCELED"),
                "recurring": any(component.get(name) for name in RECURRENCE_PROPERTIES),
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
    if existing["date_from"] < deadlines.local_now().date().isoformat():
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
            params={"date": existing["date_from"], "variant": "cancelled"},
        )
        return
    db.update("reservation", existing["id"], {"status": "cancelled", "updated_at": now})
    from . import claim as stay_claim

    stay_claim.expire_on_cancel(existing)
    stats["cancelled"] += 1


def _existing_reservation(apartment_id: int, event: Dict[str, Any], now: str):
    """The stored stay this event refers to, or None.

    Before W4.6 a UID-less event was keyed by its dates, so a moved one looked
    brand new. Rows still carrying that old key are re-keyed on first sight -
    without this, the very first sync after the change would cancel every
    UID-less stay and create a second copy of it, stranding the guest details
    already collected against the original.
    """
    uid = event["uid"]
    row = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND uid = ?",
        (apartment_id, uid),
    )
    if row or not uid.startswith("synthetic-"):
        return row
    legacy = _legacy_synthetic_uid(event["date_from"], event["date_to"], event["summary"])
    if legacy == uid:
        return None
    row = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND uid = ?",
        (apartment_id, legacy),
    )
    if not row:
        return None
    db.update("reservation", row["id"], {"uid": uid, "updated_at": now})
    adopted = dict(row)
    adopted["uid"] = uid
    log.info("ical_synthetic_uid_rekeyed apartment_id=%s reservation_id=%s", apartment_id, row["id"])
    return adopted


def _reopen_guest_access(reservation_id: int) -> bool:
    """Undo a cancellation's guest-access lock, if it is actually set.

    ``claim.reopen_guest_access`` stamps ``guest_access_reopened_at`` whatever
    it finds, so calling it on a stay that was never locked would record a
    reopening that never happened.
    """
    row = db.query_one(
        "SELECT guest_access_locked_at FROM reservation_claim WHERE reservation_id = ?",
        (reservation_id,),
    )
    if not row or not row["guest_access_locked_at"]:
        return False
    from . import claim as stay_claim

    stay_claim.reopen_guest_access(reservation_id)
    return True


def _report_import_limits(
    feed, duplicate_uids: List[str], recurring_uids: List[str], events: List[Dict[str, Any]]
) -> None:
    """Warn about events this importer knowingly does not represent in full.

    Neither is guessed at: a duplicate UID would reconcile two stays onto one
    row, and expanding a recurrence would invent stays and reporting deadlines
    the feed never confirmed. Both leave the host something to do by hand, so
    silence is not an option.
    """
    summaries = {event["uid"]: event["summary"] for event in events}
    property_name = feed["own_name"] or feed["label"] or feed["id"]
    for kind, uids in (
        ("feed_duplicate_uid", duplicate_uids),
        ("feed_recurring_event", recurring_uids),
    ):
        key = f"{kind}:{feed['id']}"
        if not uids:
            alerts.resolve(key)
            continue
        alerts.raise_alert(
            "warning",
            kind,
            host_i18n.translate(
                host_i18n.DEFAULT_LANGUAGE, f"notification.{kind}.title", property=property_name
            ),
            host_i18n.translate(host_i18n.DEFAULT_LANGUAGE, f"notification.reason.{kind}"),
            dedupe_key=key,
            apartment_id=feed["apartment_id"],
        )
        log.warning(
            "ical_%s apartment_id=%s feed_id=%s count=%s summaries=%s",
            kind,
            feed["apartment_id"],
            feed["id"],
            len(uids),
            "; ".join((summaries.get(uid) or uid) for uid in uids[:5]),
        )


def sync_feed(
    feed, keep_past_days: int = 400, ics_text: Optional[str] = None
) -> Dict[str, Any]:
    """Reconcile one feed into the reservation table.

    ``ics_text`` lets a caller supply calendar text the server already holds,
    so demo seeding never depends on the network or on fetching from itself.
    """
    now = db.utcnow()
    stats = {"created": 0, "updated": 0, "cancelled": 0, "blocks_skipped": 0}
    try:
        if ics_text is None:
            ics_text = fetch_feed(feed["url"])
        events = parse_events(ics_text)
    except Exception as exc:
        # Deliberately broad: an unexpected exception from one malformed feed
        # must not abort the sync of every other apartment.
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
            params={
                "feed": feed["own_name"] or feed["label"] or feed["id"],
                "error": str(exc),
            },
        )
        return {"error": str(exc), **stats}

    alerts.resolve(f"feed_error:{feed['id']}")
    platform = platform_of(feed["url"], ics_text)
    seen_uids: List[str] = []
    handled_uids: set = set()
    duplicate_uids: List[str] = []
    recurring_uids: List[str] = []

    for event in events:
        if event["uid"] in handled_uids:
            # [F6] Two events under one UID reconcile against the same row, so
            # the second would silently overwrite the first. The first wins and
            # the host is told, because one of the two stays is missing.
            duplicate_uids.append(event["uid"])
            continue
        handled_uids.add(event["uid"])
        if event["is_block"]:
            stats["blocks_skipped"] += 1
            blocked = db.query_one(
                "SELECT id, status FROM reservation WHERE apartment_id = ? AND uid = ?",
                (feed["apartment_id"], event["uid"]),
            )
            if blocked and blocked["status"] == "active":
                # [F13] The block wording lives in free-text SUMMARY, so a host
                # who renames a booking must not lose the stay. A block counts
                # only at first sight: the row exists, so the event keeps it
                # alive and the sweep below cannot cancel it.
                seen_uids.append(event["uid"])
                log.warning(
                    "ical_block_summary_kept_existing_stay apartment_id=%s reservation_id=%s",
                    feed["apartment_id"],
                    blocked["id"],
                )
            continue
        if event.get("is_cancelled"):
            _cancel_existing_stay(feed["apartment_id"], event["uid"], event["date_from"], now, stats)
            continue
        seen_uids.append(event["uid"])
        if event.get("recurring"):
            recurring_uids.append(event["uid"])
        existing = _existing_reservation(feed["apartment_id"], event, now)
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
            dates_changed = (
                existing["date_from"] != event["date_from"]
                or existing["date_to"] != event["date_to"]
            )
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
            if existing["status"] == "cancelled":
                # The stay is back, so the cancellation was wrong (or the room
                # was rebooked). Cancelling closed guest access; reopen it so
                # the guests can still reach their forms. A guest who had
                # already claimed is not restored - cancelling destroyed their
                # link - so the host still has to resend the invitation.
                if _reopen_guest_access(existing["id"]):
                    log.info(
                        "ical_revival_reopened_guest_access apartment_id=%s reservation_id=%s",
                        feed["apartment_id"],
                        existing["id"],
                    )
            if dates_changed:
                # Only guests still sitting on the reservation's old dates move
                # with it: one who legitimately leaves earlier keeps their own
                # window. The signature is deliberately left alone - it names
                # the dates the guest actually signed for, so wiping it would
                # destroy evidence the host may still need. The host is told
                # instead.
                db.execute(
                    "UPDATE guest SET stay_from = ?, stay_to = ?, updated_at = ? "
                    "WHERE reservation_id = ? AND submit_state != 'sent' "
                    "AND stay_from = ? AND stay_to = ?",
                    (
                        event["date_from"],
                        event["date_to"],
                        now,
                        existing["id"],
                        existing["date_from"],
                        existing["date_to"],
                    ),
                )
                alerts.raise_alert(
                    "critical",
                    "dates_changed_resign",
                    host_i18n.translate(
                        host_i18n.DEFAULT_LANGUAGE, "notification.dates_changed_resign.title"
                    ),
                    host_i18n.translate(
                        host_i18n.DEFAULT_LANGUAGE, "notification.reason.dates_changed_resign"
                    ),
                    dedupe_key=f"dates_changed_resign:{existing['id']}",
                    apartment_id=feed["apartment_id"],
                    reservation_id=existing["id"],
                )
                log.warning(
                    "ical_dates_changed_resign_required apartment_id=%s reservation_id=%s",
                    feed["apartment_id"],
                    existing["id"],
                )
                reported = db.query_one(
                    "SELECT COUNT(*) AS n FROM guest "
                    "WHERE reservation_id = ? AND submit_state = 'sent'",
                    (existing["id"],),
                )
                if reported and reported["n"]:
                    # [F5] A sent guest keeps the dates that were filed - that
                    # is deliberate, they are evidence - so the register now
                    # holds a stay that has since moved. Only the host can
                    # decide whether to correct and resend or to cancel it.
                    alerts.raise_alert(
                        "warning",
                        "moved_after_report",
                        f"A stay reported to the police for {existing['date_from']} to "
                        f"{existing['date_to']} has moved in the calendar to "
                        f"{event['date_from']} to {event['date_to']}.",
                        f"{reported['n']} filed guest record(s) still carry the old dates. "
                        "Check the booking, correct the guest's dates and resend.",
                        dedupe_key=f"moved_after_report:{existing['id']}",
                        apartment_id=feed["apartment_id"],
                        reservation_id=existing["id"],
                    )
                    log.warning(
                        "ical_moved_after_report apartment_id=%s reservation_id=%s guests=%s",
                        feed["apartment_id"],
                        existing["id"],
                        reported["n"],
                    )
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

    _report_import_limits(feed, duplicate_uids, recurring_uids, events)

    # A future stay that has vanished from the feed was cancelled upstream.
    # Past stays are left alone: they may already be reported to the police.
    cutoff = deadlines.local_now().date().isoformat()
    candidates = db.query(
        "SELECT id, uid, date_from FROM reservation "
        "WHERE apartment_id = ? AND ical_feed_id = ? AND status = 'active' AND date_from >= ?",
        (feed["apartment_id"], feed["id"], cutoff),
    )
    # A feed that suddenly returns a fraction of what is stored is far more
    # likely to be broken than to mean nine guests cancelled at once, so the
    # cancellation sweep waits until the feed is trusted again.
    if candidates and len(seen_uids) < FEED_COMPLETENESS_THRESHOLD * len(candidates):
        db.update(
            "ical_feed",
            feed["id"],
            {"last_sync_at": now, "last_status": "suspect", "last_error": None},
        )
        alerts.raise_alert(
            "warning",
            "feed_incomplete",
            host_i18n.translate(
                host_i18n.DEFAULT_LANGUAGE,
                "notification.feed_incomplete.title",
                property=feed["own_name"] or feed["label"] or feed["id"],
            ),
            host_i18n.translate(
                host_i18n.DEFAULT_LANGUAGE, "notification.reason.feed_incomplete"
            ),
            dedupe_key=f"feed_incomplete:{feed['id']}",
            apartment_id=feed["apartment_id"],
        )
        log.warning(
            "ical_incomplete_feed_retained apartment_id=%s feed_id=%s retained_stays=%s returned_events=%s",
            feed["apartment_id"],
            feed["id"],
            len(candidates),
            len(seen_uids),
        )
        return stats
    alerts.resolve(f"feed_incomplete:{feed['id']}")
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
                params={"date": row["date_from"], "variant": "disappeared"},
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


def sync_all(
    apartment_id: Optional[int] = None, owner_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """Sync active feeds, optionally limited to one apartment or owner."""
    if apartment_id:
        feeds = db.query(
            "SELECT * FROM ical_feed WHERE active = 1 AND apartment_id = ?", (apartment_id,)
        )
    else:
        feeds = db.query(
            "SELECT f.* FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id "
            "WHERE f.active = 1 AND a.active = 1 "
            "AND (? IS NULL OR a.owner_user_id = ?)",
            (owner_user_id, owner_user_id),
        )
    totals = {"feeds": 0, "created": 0, "updated": 0, "cancelled": 0, "errors": 0}
    for feed in feeds:
        totals["feeds"] += 1
        try:
            stats = sync_feed(feed)
        except Exception as exc:  # noqa: BLE001 - one feed must not stop the rest
            log.exception("ical feed %s failed", feed["id"])
            stats = {"error": str(exc)}
        if stats.get("error"):
            totals["errors"] += 1
            continue
        for key in ("created", "updated", "cancelled"):
            totals[key] += stats.get(key, 0)
    db.set_setting("last_ical_sync", db.utcnow())
    return totals
