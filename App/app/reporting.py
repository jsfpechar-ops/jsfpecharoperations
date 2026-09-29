"""Turning stored guests into UbyPort submissions.

The rules this file exists to honour, all from the Ubyport operating rules:

* 10.3 - three degrees of automation must all be available, and which one is
  used is the host's choice (immediate / scheduled / manual).
* 10.4 - the host must be told about obstacles, must be able to view and save
  the Doručenka, and must be able to correct a record and send it again.
* 10.5(3) - the stored record must always carry the outcome and the timestamp
  of a successful notification.
* Developer notice of 1 Sep 2025 - duplicates are rejected and count against
  the host, so an already-accepted record is never resent automatically.

Timestamps
----------
Every timestamp this module reads back - ``registration_completed_at``,
``guest.updated_at``, ``guest.created_at`` - is **UTC**, because that is what
``db.utcnow`` writes (an offset-aware ``+00:00`` ISO string). The stored values
are compared against ``datetime.now(timezone.utc)``, never against Prague civil
time. A value that arrives without an offset is therefore read as UTC by
``_as_utc`` rather than as local time; ``deadlines.local_now`` deliberately
keeps a *separate* naive Prague-civil convention for the date arithmetic that
legal deadlines are counted in. Do not mix the two: converting a UTC stamp to
Prague civil before comparing it to a deadline is a real calendar-day error,
and the reverse silently shifts every automation window by an hour or two.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import secrets
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from . import access, alerts, codelists, config, db, deadlines, mail_notify, passport_photos, validation
from .ubyport import errors as uby_errors
from .ubyport.client import SubmissionResult, UbyportAuthError, UbyportClient, UbyportError, UbyportOutcomeUnknownError, UbyportTransportError

log = logging.getLogger("ubyhost.reporting")

# guest.submit_state values
PENDING = "pending"
SENT = "sent"
ERROR = "error"
BLOCKED = "blocked"  # rejected in a way that resending cannot fix
NOT_REQUIRED = "not_required"  # Czech nationals: house book only

AUTOMATION_MODES = ("immediate", "scheduled", "manual")
SUBMISSION_CLAIM_TTL_SECONDS = 5 * 60

# Scheduled mode waits for the host's review window, but never past this
# many hours before the statutory deadline (owner decision OD-2).
AUTOMATIC_SEND_DEADLINE_MARGIN_HOURS = 6

# A record filed by hand from a paper house book carries no signature to
# collect. The host vouches for it instead of forging one, so the marker stands
# in for a drawn signature everywhere completeness is judged.
IMPORTED_SIGNATURE = "imported"

# Shown to the host on the entry form, where "sign on the host form" is the
# instruction that can actually be followed. The guest link passes its own
# catalog string to ``guest_issues`` instead.
HOST_SIGNATURE_REQUIRED_MESSAGE = (
    "A guest signature is required. Use the guest link or sign on the host form."
)

# How many times the unattended sweep may offer the same guest before it stops
# and asks a human to look. A code 112 covers both an interrupted connection
# (where retrying is exactly right) and a bad value in the generated record
# (where retrying is futile and the register records another refusal), and the
# response does not say which. Retrying a few times therefore costs little, but
# retrying forever is not a policy: it is an unbounded stream of rejections
# nobody is watching. This bounds it, and crossing the bound raises an alert so
# the stop is visible rather than silent.
#
# Only the automatic sweep is bound. A host-initiated send always goes through,
# and saving the guest form resets the count, so "fix the data and send again"
# is never blocked by this.
SUBMISSION_MAX_AUTO_ATTEMPTS = 3

# How long a stay must go untouched before the party is taken as final. A guest
# link holder can raise the declared headcount, so the completion gate must not
# wait forever for forms that are never coming: once every form on file is
# complete and none has been touched for this long, the stay is ready to file
# and any shortfall is raised as a headcount_mismatch warning.
HEADCOUNT_QUIET_HOURS = 12


# --- payload mapping -----------------------------------------------------

def header_from_apartment(ap) -> Dict[str, Optional[str]]:
    """Map an apartment row onto the SeznamUbytovanych header fields."""
    return {
        "uIdub": (ap["uby_idub"] or "").strip() or None,
        "uMark": (ap["uby_mark"] or "").strip().upper() or None,
        "uName": (ap["uby_name"] or "").strip()[:35] or None,
        "uCont": (ap["uby_contact"] or "").strip()[:50] or None,
        "uOkr": (ap["addr_okres"] or "").strip()[:32] or None,
        "uOb": (ap["addr_obec"] or "").strip()[:48] or None,
        "uObCa": (ap["addr_obec_cast"] or "").strip()[:48] or None,
        "uStr": (ap["addr_street"] or "").strip()[:48] or None,
        "uHomN": (ap["addr_house_no"] or "").strip().upper() or None,
        "uOriN": (ap["addr_orient_no"] or "").strip().upper() or None,
        "uPsc": validation.normalise_zip(ap["addr_zip"]) or None,
    }


def _stay_dates(guest, reservation) -> Tuple[date, date]:
    start = validation.parse_iso_date(guest["stay_from"]) or validation.parse_iso_date(
        reservation["date_from"]
    )
    end = validation.parse_iso_date(guest["stay_to"]) or validation.parse_iso_date(
        reservation["date_to"]
    )
    return start, end


def guest_payload(guest, reservation) -> Dict[str, Any]:
    """Map a guest row onto the Ubytovany fields."""
    start, end = _stay_dates(guest, reservation)
    residence = validation.compose_residence(
        guest["res_street"] or "", guest["res_city"] or "", (guest["res_country"] or "").upper()
    )
    purpose = (guest["purpose"] or "").strip()
    return {
        "cFrom": f"{start.isoformat()}T00:00:00" if start else None,
        "cUntil": f"{end.isoformat()}T00:00:00" if end else None,
        "cSurN": guest["surname"] or None,
        "cFirstN": guest["first_name"] or None,
        "cDate": guest["birth_date"] or None,
        "cPlac": None,  # documented as unused
        "cNati": (guest["nationality"] or "").upper() or None,
        "cDocN": guest["doc_number"] or None,
        "cVisN": guest["visa_number"] or None,
        "cResi": residence or None,
        "cPurp": int(purpose) if purpose.isdigit() else None,
        "cSpz": None,  # documented as unused
        "cNote": guest["note"] or None,
    }


# --- readiness -----------------------------------------------------------

def guest_dict(guest) -> Dict[str, Optional[str]]:
    return {
        "surname": guest["surname"],
        "first_name": guest["first_name"],
        "birth_date": guest["birth_date"],
        "nationality": guest["nationality"],
        "doc_number": guest["doc_number"],
        "visa_number": guest["visa_number"],
        "res_street": guest["res_street"],
        "res_city": guest["res_city"],
        "res_country": guest["res_country"],
        "purpose": guest["purpose"],
        "note": guest["note"],
    }


def guest_has_signature(guest) -> bool:
    """True when the record has a drawn signature or a declared paper import."""
    signature = (guest["signature_png"] or "").strip()
    if signature == IMPORTED_SIGNATURE:
        return True
    return signature.startswith("data:image/")


def guest_signature_issue(value: Optional[str], translate=None, *,
                          allow_imported: bool = True) -> Optional[validation.Issue]:
    """The one ``signature`` issue a value raises, or ``None`` when it is fine.

    Both the stored-record check and the two save paths read this, so a value
    one of them rejects can never be filed as collected by another.

    ``translate`` is the guest catalog lookup: the host sees the form and needs
    to be told where the signature can come from, while a guest is looking at
    the pad itself, so the guest route passes its own (already localised)
    sentence instead.

    ``allow_imported`` is True for a stored record and for the host's own
    entry, where ``IMPORTED_SIGNATURE`` records that the host has the signature
    on paper. A guest submission passes False: a guest posting
    ``signature=imported`` used to be accepted and stored as signed, which made
    an unsigned record sendable.
    """
    text = (value or "").strip()
    if text == IMPORTED_SIGNATURE:
        if allow_imported:
            return None
        if translate is not None:
            return validation.Issue("signature", translate("signature_missing"))
        return validation.Issue("signature", HOST_SIGNATURE_REQUIRED_MESSAGE)
    if not text:
        if translate is not None:
            return validation.Issue("signature", translate("signature_missing"))
        return validation.Issue("signature", HOST_SIGNATURE_REQUIRED_MESSAGE)
    return validation.signature_issue(value)


def guest_identity_verified(guest) -> bool:
    """True when the host has confirmed the record against a travel document."""
    if not validation.guest_is_reportable(guest["nationality"]):
        return True
    return bool(guest["identity_verified_at"])


def _guest_entered_by(guest) -> str:
    try:
        return guest["entered_by"] or "guest"
    except (KeyError, IndexError, TypeError):
        return "guest"


def guest_has_passport_photo(guest) -> bool:
    """True when a temporary passport photo is on file for host review."""
    if not validation.guest_is_reportable(guest["nationality"]):
        return False
    if _guest_entered_by(guest) == "host":
        return False
    try:
        guest_id = guest["id"]
    except (KeyError, IndexError, TypeError):
        return False
    if not guest_id:
        return False
    return bool(guest["passport_photo_at"]) and passport_photos.has_photo(int(guest_id))


def guest_needs_passport_photo(guest, apartment) -> bool:
    """Online foreign guests upload a photo only when the property requires it.

    ``apartment`` is required: every caller holds one, and the ad-hoc
    reservation-to-apartment lookup this used to fall back to was a second,
    unscoped way to reach the same row.
    """
    policy = "off"
    if apartment is not None:
        try:
            policy = (apartment["passport_photo_policy"] or "off").strip().lower()
        except (KeyError, IndexError, TypeError):
            policy = "off"
    if policy != "required_foreign":
        return False
    return (
        validation.guest_is_reportable(guest["nationality"])
        and _guest_entered_by(guest) != "host"
        and not guest_identity_verified(guest)
    )


def guest_issues(guest, reservation, translate=None) -> List[validation.Issue]:
    """Everything wrong with a stored guest record - the single completeness source.

    ``translate`` is an optional catalog lookup for the one sentence here that
    is shown to a person rather than logged; without it the host wording is used.
    """
    start, end = _stay_dates(guest, reservation)
    issues = validation.validate_guest(guest_dict(guest), start, end)
    signature = guest_signature_issue(guest["signature_png"], translate)
    if signature is not None:
        issues.append(signature)
    return issues


def guest_is_complete(guest, reservation) -> bool:
    return not validation.errors_only(guest_issues(guest, reservation))


def guest_form_locked(guest, reservation) -> bool:
    """Guests may not reopen a form once it is complete and signed.

    After police reporting the record is final; before that, a completed and
    signed form is still locked so another person cannot change it from the
    guest link.
    """
    if guest["submit_state"] == SENT:
        return True
    signature = (guest["signature_png"] or "").strip()
    return signature.startswith("data:image/") and guest_is_complete(guest, reservation)


def expected_guest_count(reservation) -> Optional[int]:
    """Host override wins over what the lead guest declared."""
    if reservation["expected_guests_override"]:
        return reservation["expected_guests_override"]
    return reservation["declared_guests"]


def reservation_progress(reservation) -> Dict[str, Any]:
    """How far along this reservation is, for the dashboard."""
    guests = db.query(
        "SELECT * FROM guest WHERE reservation_id = ? AND archived_at IS NULL "
        "ORDER BY is_lead DESC, id",
        (reservation["id"],),
    )
    expected = expected_guest_count(reservation)
    complete = [g for g in guests if guest_is_complete(g, reservation)]
    complete_ids = {g["id"] for g in complete}
    reportable = [g for g in complete if validation.guest_is_reportable(g["nationality"])]
    unverified = [g for g in reportable if not guest_identity_verified(g)]
    sent = [g for g in guests if g["submit_state"] == SENT]
    failed = [g for g in guests if g["submit_state"] in (ERROR, BLOCKED)]
    # The complement of ``complete`` rather than a second pass of the same
    # predicate: validating every guest twice per dashboard row was the single
    # most expensive thing on the queue.
    incomplete = [g for g in guests if g["id"] not in complete_ids]

    missing = None
    # People nobody has registered at all, as opposed to a guest who started
    # the form and has not finished it. Only this count makes "send the link to
    # the others / lower the guest count" the right advice; an unsigned guest
    # needs the signature hint instead.
    not_registered = None
    if expected is not None:
        missing = max(0, expected - len(complete))
        not_registered = max(0, expected - len(guests))

    if failed:
        status = "failed"
    elif expected is None and not guests:
        status = "awaiting_guest"
    elif missing:
        status = "incomplete"
    elif incomplete:
        status = "incomplete"
    elif reportable and len(sent) < len(reportable):
        status = "awaiting_verification" if unverified else "ready"
    elif reportable and len(sent) == len(reportable):
        status = "reported"
    elif complete and not reportable:
        status = "not_required"
    else:
        status = "awaiting_guest"

    return {
        "guests": guests,
        "expected": expected,
        "filled": len(complete),
        "missing": missing,
        "not_registered": not_registered,
        "incomplete": incomplete,
        "reportable": reportable,
        "unverified": unverified,
        "sent": sent,
        "failed": failed,
        "status": status,
    }


# Statuses only the host can clear. "awaiting_verification" belongs here even
# though sending would verify implicitly: a manual apartment never sends on its
# own, so leaving it off the queue means nobody is told before the window shuts.
HOST_ACTION_STATUSES = ("failed", "incomplete", "ready", "awaiting_verification")
FINISHED_STATUSES = ("reported", "not_required")


def queue_groups(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Split dashboard rows into the four buckets of the Overview work queue.

    Every row lands in exactly one bucket, so the counts beside the headings
    can be trusted.
    """
    needs_action = [
        row for row in rows
        if row["progress"]["status"] in HOST_ACTION_STATUSES
        # Past the deadline even "waiting for the guest" is the host's problem.
        or (row["urgency"] == "overdue" and row["progress"]["status"] not in FINISHED_STATUSES)
    ]
    claimed = {row["reservation"]["id"] for row in needs_action}
    waiting = [
        row for row in rows
        if row["progress"]["status"] == "awaiting_guest"
        and row["reservation"]["id"] not in claimed
    ]
    claimed |= {row["reservation"]["id"] for row in waiting}
    upcoming = [
        row for row in rows
        if row["reservation"]["id"] not in claimed
        and row["progress"]["status"] not in FINISHED_STATUSES
    ]
    claimed |= {row["reservation"]["id"] for row in upcoming}
    completed = [
        row for row in rows
        if row["reservation"]["id"] not in claimed
        and row["progress"]["status"] in FINISHED_STATUSES
    ]
    return {
        "needs_action": needs_action,
        "waiting": waiting,
        "upcoming": upcoming,
        "completed": completed,
    }


def queue_counts(
    rows: List[Dict[str, Any]], groups: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, int]:
    """Numbers for the Overview stat strip, derived from the same buckets."""
    return {
        "attention": len(groups["needs_action"]),
        "awaiting": len(groups["waiting"]),
        "ready": sum(1 for row in rows if row["progress"]["status"] == "ready"),
        "overdue": sum(
            1 for row in rows
            if row["urgency"] == "overdue"
            and row["progress"]["status"] not in FINISHED_STATUSES
        ),
    }


def pending_reportable(guests: List[Any]) -> List[Any]:
    """Reportable guests that have not yet been accepted by UbyPort."""
    return [
        guest
        for guest in guests
        if validation.guest_is_reportable(guest["nationality"])
        and guest_has_signature(guest)
        and guest["submit_state"] not in (SENT, BLOCKED)
    ]


def rejected_edited_since(reservation_id: int) -> bool:
    """True when a refused guest was edited after the refusal came back.

    A refusal stamps the guest's ``updated_at`` and its submission's
    ``finished_at`` with the same instant, so a later ``updated_at`` means the
    host has changed something. Only then is re-sending worth offering as the
    main action instead of fixing first.
    """
    return bool(
        db.query(
            "SELECT 1 FROM guest g JOIN submission s ON s.id = g.submission_id "
            "WHERE g.reservation_id = ? AND g.submit_state IN (?, ?) "
            "  AND g.updated_at > s.finished_at LIMIT 1",
            (reservation_id, ERROR, BLOCKED),
        )
    )


def send_controls(reservation, apartment, progress: Dict[str, Any]) -> Dict[str, Any]:
    """Whether Send actions should appear on a stay row."""
    from . import demo

    mode = apartment["automation_mode"]
    pending = pending_reportable(progress["reportable"])
    has_pending = bool(pending)
    sendable_statuses = ("ready", "failed", "awaiting_verification")
    can_send = progress["status"] in sendable_statuses and has_pending
    auto_immediate = mode == "immediate"

    send_enabled = can_send and not auto_immediate

    if apartment and demo.is_demo_apartment(apartment):
        return {
            "send_enabled": False,
            "send_visible": False,
            "send_hint_key": "hint.demo_preview",
            "auto_immediate": auto_immediate,
            "pending_count": len(pending),
            "rejected_edited": False,
            "is_demo": True,
        }

    if progress["status"] == "failed":
        # A refusal is not "ready to send": the record has to be corrected
        # first, and the copy has to say so even though resending is allowed.
        send_hint_key = "hint.failed"
    elif auto_immediate:
        send_hint_key = "hint.auto_immediate"
    elif not has_pending and progress["status"] == "reported":
        # "Nothing is subject to the duty" contradicted the stay's own metric
        # ("2 reported · 2 subject to the duty") on every reported stay.
        send_hint_key = "hint.all_reported"
    elif not has_pending and progress["status"] == "not_required":
        send_hint_key = "hint.nothing_duty"
    elif not progress.get("guests"):
        send_hint_key = "hint.awaiting_guest"
    elif progress["status"] == "incomplete" and progress.get("not_registered"):
        # A stay short of the people it expects is not the same problem as a
        # guest who has not signed: the fix is a number, not the guest. This
        # outranks the branches below because it names the unregistered people.
        send_hint_key = "hint.missing_guests"
    elif not has_pending:
        unsigned_foreign = [
            guest
            for guest in progress.get("guests", [])
            if validation.guest_is_reportable(guest["nationality"])
            and not guest_has_signature(guest)
        ]
        if unsigned_foreign:
            send_hint_key = "hint.need_signature"
        else:
            send_hint_key = "hint.nothing_left"
    elif not can_send:
        send_hint_key = "hint.not_ready"
    elif progress["status"] == "awaiting_verification":
        send_hint_key = "hint.ready_id_optional"
    else:
        send_hint_key = "hint.ready_to_send"

    send_visible = has_pending and progress["status"] in sendable_statuses

    return {
        "send_enabled": send_enabled,
        "send_visible": send_visible or (auto_immediate and has_pending),
        "send_hint_key": send_hint_key,
        "auto_immediate": auto_immediate,
        "pending_count": len(pending),
        "rejected_edited": (
            progress["status"] == "failed"
            and rejected_edited_since(reservation["id"])
        ),
    }


def dashboard_rows(
    days_ahead: int = 21, days_back: int = 45, owner_user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Every stay worth looking at, ordered by how urgent it is."""
    start = (date.today() - timedelta(days=days_back)).isoformat()
    end = (date.today() + timedelta(days=days_ahead)).isoformat()
    rows = db.query(
        "SELECT r.*, a.internal_name, a.permalink_token, a.automation_mode "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.status = 'active' AND a.active = 1 AND a.archived_at IS NULL "
        "AND r.archived_at IS NULL AND (? IS NULL OR a.owner_user_id = ?) "
        "AND r.date_from BETWEEN ? AND ? "
        "ORDER BY r.date_from",
        (owner_user_id, owner_user_id, start, end),
    )
    out: List[Dict[str, Any]] = []
    for reservation in rows:
        check_in = reservation_deadline_anchor(reservation)
        try:
            progress = reservation_progress(reservation)
        except db.DecryptionError:
            log.exception("dashboard skipped reservation_id=%s", reservation["id"])
            continue
        level = deadlines.urgency(check_in) if check_in else "future"
        # A finished stay with nothing outstanding is noise on a dashboard.
        if progress["status"] in ("reported", "not_required") and level in ("overdue", "ok", "urgent", "soon"):
            if check_in and check_in < date.today() - timedelta(days=3):
                continue
        apartment = access.apartment_for_reservation(reservation, owner_user_id)
        controls = send_controls(reservation, apartment, progress) if apartment else {}
        out.append(
            {
                "reservation": reservation,
                "progress": progress,
                "controls": controls,
                "urgency": level,
                "check_in": check_in,
                "deadline": deadlines.reporting_deadline(check_in) if check_in else None,
            }
        )
    out.sort(
        key=lambda row: (
            0 if row["progress"]["status"] in ("failed",) else 1,
            deadlines.URGENCY_ORDER.get(row["urgency"], 9),
            row["reservation"]["date_from"],
        )
    )
    return out


def _as_utc(value) -> Optional[datetime]:
    """Parse a stored timestamp and read a naive one as UTC (see module docstring)."""
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _forms_quiet_for(progress: Dict[str, Any], hours: int) -> bool:
    """True when no guest form on the stay has been touched for ``hours``."""
    stamps = [
        guest["updated_at"] or guest["created_at"]
        for guest in progress["guests"]
        if guest["updated_at"] or guest["created_at"]
    ]
    if not stamps:
        return False
    newest = _as_utc(max(stamps))
    if newest is None:
        return False
    return datetime.now(timezone.utc) - newest >= timedelta(hours=hours)


def refresh_registration_completed_at(
    reservation_id: int, completed_at: Optional[str] = None
) -> Optional[str]:
    """Persist the first instant all declared guest forms became complete."""
    reservation = db.query_one(
        "SELECT * FROM reservation WHERE id = ?", (reservation_id,)
    )
    if not reservation:
        return None
    progress = reservation_progress(reservation)
    # The ordinary path: everyone the host declared has signed.
    declared_filled = (
        progress["expected"] is not None
        and progress["filled"] >= progress["expected"]
        and not progress["incomplete"]
    )
    # The decoupled path: the declared headcount is not a gate the guest link
    # can hold open. Every form on file is complete and the party has stopped
    # growing, so the stay is as final as it will ever get.
    forms_settled = (
        bool(progress["guests"])
        and not progress["incomplete"]
        and _forms_quiet_for(progress, HEADCOUNT_QUIET_HOURS)
    )
    complete = declared_filled or forms_settled
    existing = reservation["registration_completed_at"]
    if complete and not existing:
        candidate = completed_at or db.utcnow()
        db.execute(
            "UPDATE reservation SET registration_completed_at = ?, updated_at = ? "
            "WHERE id = ? AND registration_completed_at IS NULL",
            (candidate, db.utcnow(), reservation_id),
        )
        existing = db.query_one(
            "SELECT registration_completed_at FROM reservation WHERE id = ?",
            (reservation_id,),
        )["registration_completed_at"]
    elif not complete and existing and progress["incomplete"]:
        # Only a form that is actually missing un-completes a stay. Touching a
        # guest row restarts the quiet clock, and clearing the completion
        # because of that meant any edit - a corrected surname, an archived
        # duplicate, a re-saved form - could hold a stay open for ever.
        db.update(
            "reservation",
            reservation_id,
            {"registration_completed_at": None, "updated_at": db.utcnow()},
        )
        existing = None
    return existing


def signature_dates_stale(guest, reservation) -> bool:
    """Whether a signed form names dates the calendar has since moved away.

    The sync deliberately leaves an already-signed guest on the dates they
    signed - that window is what the police were given, so it is evidence - and
    raises ``dates_changed_resign`` for the host. Nothing stopped the *filing*
    though, so the stay went out with dates that contradict the booking.

    Only a window that has fallen outside the booking counts. A guest who
    signed a shorter period inside it - a late arrival, an early departure - is
    a normal record and must still be filed.
    """
    stay_from, stay_to = guest["stay_from"], guest["stay_to"]
    date_from, date_to = reservation["date_from"], reservation["date_to"]
    if not stay_from and not stay_to:
        return False
    if stay_from and date_from and stay_from < date_from:
        return True
    return bool(stay_to and date_to and stay_to > date_to)


def submit_stay_if_complete(apartment_id: int, reservation_id: int) -> None:
    """Send a stay the moment its declared forms are all complete.

    Only ``immediate`` apartments send on completion; every other mode waits for
    the scheduler or for the host. Called from wherever a form can become the
    last one missing, so the trigger is the save rather than the state.
    """
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment:
        return
    completed_at = refresh_registration_completed_at(reservation_id)
    if not completed_at or apartment["automation_mode"] != "immediate":
        return
    reservation = db.query_one(
        "SELECT * FROM reservation WHERE id = ?", (reservation_id,)
    )
    if not reservation or reservation["status"] != "active":
        return
    guest_ids = [
        row["id"]
        for row in db.query(
            "SELECT id FROM guest WHERE reservation_id = ? AND archived_at IS NULL",
            (reservation_id,),
        )
    ]
    try:
        submit_for_apartment(
            apartment_id,
            only_guest_ids=guest_ids,
            mode="completion_immediate",
            ignore_schedule=True,
        )
    except Exception as exc:
        alerts.raise_alert(
            "warning",
            "submission_immediate",
            f"{apartment['internal_name']}: automatic send failed after registration completed.",
            str(exc),
            dedupe_key=f"submission_immediate:{apartment_id}",
            apartment_id=apartment_id,
            params={"property": apartment["internal_name"], "error": str(exc)},
        )


def due_for_automatic_send(apartment, reservation, now: Optional[datetime] = None) -> bool:
    """Whether completion-based automation says to send this stay now."""
    mode = apartment["automation_mode"]
    if mode == "manual":
        return False
    # No completion, no send. The sweep refreshes the quiet-window completion
    # before it asks, so a stay that has gone quiet is not held open for ever;
    # eligibility still comes from the guests' own forms, never from the fact
    # that this code was deployed.
    completed_at = reservation["registration_completed_at"]
    if not completed_at:
        return False
    completed = _as_utc(completed_at)
    if completed is None:
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    delay = timedelta(
        hours=0 if mode == "immediate" else (apartment["submit_after_hours"] or 24)
    )
    send_at = completed.astimezone(timezone.utc) + delay
    anchor = reservation_deadline_anchor(reservation)
    if anchor is not None:
        deadline_local = deadlines.reporting_deadline(anchor) - timedelta(
            hours=AUTOMATIC_SEND_DEADLINE_MARGIN_HOURS
        )
        latest = deadline_local.replace(tzinfo=ZoneInfo(config.TIMEZONE)).astimezone(timezone.utc)
        send_at = min(send_at, latest)
    return current.astimezone(timezone.utc) >= send_at


# --- client construction -------------------------------------------------

def client_for(apartment, env: Optional[str] = None) -> UbyportClient:
    env = env or config.UBYPORT_ENV
    endpoint = config.endpoint_for(env)
    password = db.decrypt_secret(apartment["uby_ws_password_enc"])
    return UbyportClient(
        endpoint=endpoint,
        username=(apartment["uby_ws_user"] or "").strip(),
        password=password,
        domain=config.UBYPORT_DOMAIN,
        timeout=config.UBYPORT_TIMEOUT,
        # The mock server exists for local testing and speaks plain HTTP.
        use_ntlm=(env != "mock"),
    )


# --- host identity confirmation ------------------------------------------

def record_host_identity_confirmation(
    guest_id: int,
    verified_by_user_id: Optional[int],
) -> None:
    """Host confirms guest details against a travel document.

    Optional before sending, and recorded only here, from the explicit Verify
    route: this is a human attestation, so nothing unattended may make it.
    """
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    if not guest or not validation.guest_is_reportable(guest["nationality"]):
        return
    if guest["identity_verified_at"]:
        return
    now = db.utcnow()
    # Verification is the whole reason the photo exists, so it goes here rather
    # than waiting for the retention sweep to get round to it.
    passport_photos.delete_photo(guest_id)
    db.update(
        "guest",
        guest_id,
        {
            "identity_verified_at": now,
            "identity_verified_by": verified_by_user_id,
            "passport_photo_at": None,
            "updated_at": now,
        },
    )
    db.audit(
        "guest_identity_verified",
        f"id={guest_id}",
        owner_user_id=verified_by_user_id,
    )


# --- submission ----------------------------------------------------------

def blocked_as_duplicate(guest) -> bool:
    """True when UbyPort refused this record because it already holds it."""
    try:
        stored = guest["last_errors"] or ""
    except (IndexError, KeyError):
        return False
    return any(uby_errors.is_duplicate(part) for part in stored.split(" | "))


def receipt_submission_id(previous_submission_id: Optional[int]) -> Optional[int]:
    """Where this guest's Dorucenka lives, given the submission that carried it.

    A duplicate answer carries no confirmation, because the register already
    held the record: the receipt, if we ever received one, belongs to the
    submission that filed the guest for the first time. Returns None when that
    submission is unknown or holds no receipt, which is what the UI needs in
    order to say so instead of inventing a link.
    """
    if not previous_submission_id:
        return None
    row = db.query_one(
        "SELECT receipt_pdf FROM submission WHERE id = ?", (previous_submission_id,)
    )
    if row and row["receipt_pdf"]:
        return previous_submission_id
    return None


def guest_correction_resets_attempts(existing) -> bool:
    """Whether this save is a correction that restarts the automatic retry budget.

    Rule 10.4(5): a correction makes the record sendable again, and a guest
    fixing their own form is a correction like any other. Without the reset the
    sweep kept skipping the row at SUBMISSION_MAX_AUTO_ATTEMPTS for ever while
    the stranded-records card resolved itself, so the guest was never filed and
    nothing said so.
    """
    return bool(existing) and existing["submit_state"] in (ERROR, BLOCKED, NOT_REQUIRED)


def auto_attempts(guest) -> int:
    """Consecutive failed automatic submissions for one guest row.

    Tolerates a row selected before the column existed, so a caller that builds
    its own dict (or an old cached row) reads as "no attempts yet" rather than
    raising.
    """
    try:
        return max(0, int(guest["submit_attempts"] or 0))
    except (KeyError, IndexError, TypeError, ValueError):
        return 0


def clear_stuck_alert_if_recovered(reservation_id: int) -> None:
    """Drop the stranded-records card once nothing on the stay is stranded.

    The card is raised per stay, so it is cleared per stay: recovering one guest
    must not silently clear the warning while another guest on the same stay is
    still stranded, or the record would stop being sent with no card left to
    say so.
    """
    remaining = db.query_one(
        "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ? "
        "AND archived_at IS NULL AND submit_state = ? AND submit_attempts >= ?",
        (reservation_id, ERROR, SUBMISSION_MAX_AUTO_ATTEMPTS),
    )
    if not remaining or not remaining["n"]:
        alerts.resolve(f"submission_stuck:{reservation_id}")


def collect_sendable(apartment_id: int, only_guest_ids: Optional[List[int]] = None,
                     ignore_automation: bool = False, allow_resend: bool = False,
                     ignore_schedule: Optional[bool] = None
                     ) -> List[Tuple[Any, Any]]:
    """Guest rows that may legitimately be sent right now, with reservations.

    ``ignore_automation`` is the host sending by hand: it lifts both the
    completion delay and the retry cap, because taking a record back after
    fixing it is exactly what the host is for. ``ignore_schedule`` lifts only
    the delay, so a stay can be filed the moment it completes while still
    stopping at ``SUBMISSION_MAX_AUTO_ATTEMPTS``. Automation uses the narrow
    one; anything that is not a human pressing send does.
    """
    if ignore_schedule is None:
        ignore_schedule = ignore_automation
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment:
        return []

    sql = (
        "SELECT g.*, r.id AS res_id FROM guest g "
        "JOIN reservation r ON r.id = g.reservation_id "
        "WHERE r.apartment_id = ? AND r.status = 'active' "
        "AND r.archived_at IS NULL AND g.archived_at IS NULL"
    )
    params: List[Any] = [apartment_id]
    if only_guest_ids:
        marks = ", ".join("?" for _ in only_guest_ids)
        sql += f" AND g.id IN ({marks})"
        params.extend(only_guest_ids)
    sql += " ORDER BY r.date_from, g.id"

    # The stay rows, fetched once for the whole apartment instead of once per
    # guest. ``g.*, r.*`` in the query above cannot stand in for this: both
    # tables have id, created_at and archived_at, and a duplicated column name
    # resolves to the first (the guest's) value, so callers reading
    # ``reservation["id"]`` would silently be handed the guest id.
    reservations = {
        row["id"]: row
        for row in db.query(
            "SELECT * FROM reservation WHERE apartment_id = ? AND status = 'active' "
            "AND archived_at IS NULL",
            (apartment_id,),
        )
    }

    # Batches whose outcome is unknown (the register may hold them). Their
    # guests wait for a person; see UbyportOutcomeUnknownError.
    in_doubt_submissions = {
        row["id"]
        for row in db.query(
            "SELECT id FROM submission WHERE apartment_id = ? AND state = 'outcome_unknown'",
            (apartment_id,),
        )
    }

    out: List[Tuple[Any, Any]] = []
    for guest in db.query(sql, params):
        reservation = reservations.get(guest["reservation_id"])
        if not reservation:
            continue
        # BE-9: a restricted record may be withheld from filing, but only once
        # counsel confirms the statutory duty permits it. Off by default.
        if config.RESTRICTED_BLOCKS_FILING and guest["restricted_at"]:
            continue
        if not validation.guest_is_reportable(guest["nationality"]):
            # A filed record stays filed: its state is the proof pointer.
            if guest["submit_state"] not in (NOT_REQUIRED, SENT):
                db.update("guest", guest["id"], {"submit_state": NOT_REQUIRED, "updated_at": db.utcnow()})
            continue
        if guest["submit_state"] == SENT and not allow_resend:
            continue
        if guest["submit_state"] == BLOCKED and not allow_resend:
            continue
        # allow_resend is the host overriding caution, not overriding the law.
        # A record blocked because the register already holds it cannot be
        # accepted on a second try, so sending it again buys nothing and adds
        # another unjustified duplicate against the host.
        if guest["submit_state"] == BLOCKED and blocked_as_duplicate(guest):
            continue
        # The unattended sweep stops offering a record the register keeps
        # refusing, so a bad value cannot be resubmitted every ten minutes for
        # ever. This bounds only the sweep: a host-initiated send is how the
        # host takes the record back after fixing it, so it is never bound.
        if not ignore_automation and auto_attempts(guest) >= SUBMISSION_MAX_AUTO_ATTEMPTS:
            continue
        if not ignore_automation and guest["submission_id"] in in_doubt_submissions:
            continue
        if not guest_is_complete(guest, reservation):
            continue
        # A form signed before the calendar moved names the old dates. Filing
        # it would put a window in the register that the booking no longer
        # contains, so the record waits for the re-sign the sync asked for.
        if signature_dates_stale(guest, reservation):
            log.warning(
                "guest_signature_dates_stale guest=%s reservation=%s signed=%s..%s booking=%s..%s",
                guest["id"],
                reservation["id"],
                guest["stay_from"],
                guest["stay_to"],
                reservation["date_from"],
                reservation["date_to"],
            )
            continue
        # A calendar move left this stay's signatures naming dates the booking
        # no longer has, and the sync asked the host to have them re-signed.
        # Filing anyway is how the old window reached the register. A host
        # pressing send is the override, exactly as it is for the retry cap.
        if not ignore_automation and alerts.open_alert(
            f"dates_changed_resign:{reservation['id']}"
        ):
            log.warning(
                "guest_signature_awaiting_resign guest=%s reservation=%s",
                guest["id"],
                reservation["id"],
            )
            continue
        if not ignore_schedule:
            if not due_for_automatic_send(apartment, reservation):
                continue
        out.append((guest, reservation))
    return out


def claim_sendable(
    pairs: List[Tuple[Any, Any]],
) -> Tuple[str, List[Tuple[Any, Any]]]:
    """Atomically lease guests so concurrent workers cannot submit duplicates.

    The lease alone is not enough: a worker that read its list before another
    worker filed the record would still hold a lease on a guest the register
    already has, and filing it again is a duplicate against the host. So the
    claim re-reads the row inside the same transaction and drops any pair whose
    record has moved on since the list was built.
    """
    token = secrets.token_urlsafe(18)
    claimed_ids = set()
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM submission_claim WHERE claimed_at < ?",
            (time.time() - SUBMISSION_CLAIM_TTL_SECONDS,),
        )
        for guest, _reservation in pairs:
            cur.execute(
                "SELECT submit_state, archived_at FROM guest WHERE id = ?", (guest["id"],)
            )
            row = cur.fetchone()
            # Only a row that *moved on* since the list was built is dropped.
            # A guest already sent when the list was built is the host's
            # deliberate resend, which the collection allowed on purpose, and
            # that decision has to survive the claim or the resend button
            # would answer "not sendable" instead of filing the duplicate.
            if (
                row is None
                or row["archived_at"]
                or row["submit_state"] != guest["submit_state"]
            ):
                continue
            cur.execute(
                "INSERT OR IGNORE INTO submission_claim (guest_id, claim_token, claimed_at) "
                "VALUES (?, ?, ?)",
                (guest["id"], token, time.time()),
            )
            if cur.rowcount == 1:
                claimed_ids.add(guest["id"])
    return token, [pair for pair in pairs if pair[0]["id"] in claimed_ids]


def release_sendable_claim(token: str) -> None:
    db.execute("DELETE FROM submission_claim WHERE claim_token = ?", (token,))


def apartment_in_doubt(apartment_id: int) -> bool:
    """Whether any live guest still points at a batch whose outcome is unknown.

    An ``ok`` batch may resolve the apartment-level card for its own guests, but
    not for guests that still point at an earlier in-doubt batch: those stay
    excluded from the sweep, and resolving the card would hide it.
    """
    return bool(
        db.query_one(
            "SELECT 1 FROM guest g JOIN reservation r ON r.id = g.reservation_id "
            "WHERE r.apartment_id = ? AND r.status = 'active' AND r.archived_at IS NULL "
            "AND g.archived_at IS NULL AND g.submission_id IN "
            "(SELECT id FROM submission WHERE apartment_id = ? AND state = 'outcome_unknown') "
            "LIMIT 1",
            (apartment_id, apartment_id),
        )
    )


def submit_batch(
    apartment,
    pairs: List[Tuple[Any, Any]],
    mode: str = "auto",
    env: Optional[str] = None,
) -> Dict[str, Any]:
    """Send up to one batch of guests and record the outcome.

    Returns a summary dict; never raises for transport problems, because losing
    the queue on a network blip is exactly what 10.2(e) forbids.
    """
    if not pairs:
        return {"submitted": 0, "submission_id": None, "state": "noop"}

    header = header_from_apartment(apartment)
    guests = [guest_payload(g, r) for g, r in pairs]
    guest_ids = [g["id"] for g, _ in pairs]
    endpoint = config.endpoint_for(env)

    # The batch's membership, recorded once and never rewritten. It is the only
    # record of who was in this submission: guest.submission_id is a single
    # current pointer that a later resend moves elsewhere, so the submission
    # detail page reads this column, not that one.
    submission_id = db.insert(
        "submission",
        {
            "apartment_id": apartment["id"],
            "created_at": db.utcnow(),
            "mode": mode,
            "state": "running",
            "guest_ids": json.dumps(guest_ids),
            "endpoint": endpoint,
        },
    )

    client = client_for(apartment, env)
    try:
        result: SubmissionResult = client.submit(header, guests)
    except UbyportOutcomeUnknownError as exc:
        # The register may already hold this batch. Resending it on a timer
        # is how duplicates pile up against the host, so it waits for a
        # person (owner decision OD-1). The envelope is kept as evidence.
        log.error(
            "ubyport_submission_outcome_unknown apartment_id=%s submission_id=%s guest_ids=%s",
            apartment["id"], submission_id, guest_ids, exc_info=True,
        )
        finished = db.utcnow()
        # The batch record and every guest pointer are one fact: if a pointer
        # write fails or the process dies, the unmarked guests look sendable
        # again and the sweep refiles a batch the register may already hold.
        # The in-doubt filter reads guest.submission_id, so both have to land
        # together or neither may.
        with db.immediate() as cur:
            db.update_in(
                cur,
                "submission",
                submission_id,
                {
                    "state": "outcome_unknown",
                    "finished_at": finished,
                    "error_text": str(exc),
                    "request_xml": getattr(exc, "request_xml", "") or None,
                },
            )
            for in_doubt_id in guest_ids:
                db.update_in(cur, "guest", in_doubt_id, {"submission_id": submission_id})
        alerts.raise_alert(
            "critical",
            "submission_outcome_unknown",
            f"{apartment['internal_name']}: UbyPort may or may not have received the report.",
            str(exc),
            dedupe_key=f"submission_outcome_unknown:{apartment['id']}",
            apartment_id=apartment["id"],
            params={"property": apartment["internal_name"], "error": str(exc)},
        )
        mail_notify.submission_problem(
            apartment, submission_id, state="transport_error", reason=str(exc), transport=True,
        )
        return {"submitted": 0, "submission_id": submission_id, "state": "outcome_unknown",
                "error": str(exc)}
    except (UbyportTransportError, UbyportError) as exc:
        log.error(
            "ubyport_submission_failed apartment_id=%s owner_user_id=%s "
            "submission_id=%s env=%s endpoint=%s guest_ids=%s error_type=%s",
            apartment["id"],
            apartment["owner_user_id"],
            submission_id,
            env or config.UBYPORT_ENV,
            endpoint,
            guest_ids,
            type(exc).__name__,
            exc_info=True,
        )
        db.update(
            "submission",
            submission_id,
            {
                "state": "transport_error",
                "finished_at": db.utcnow(),
                "error_text": str(exc),
            },
        )
        alerts.raise_alert(
            "critical",
            "submission_transport",
            f"{apartment['internal_name']}: could not deliver data to UbyPort.",
            str(exc),
            dedupe_key=f"submission_transport:{apartment['id']}",
            apartment_id=apartment["id"],
            params={"property": apartment["internal_name"], "error": str(exc)},
        )
        if isinstance(exc, UbyportAuthError):
            alerts.raise_alert(
                "critical",
                "ubyport_auth_failed",
                f"{apartment['internal_name']}: UbyPort refused the web-service login.",
                str(exc),
                dedupe_key=f"ubyport_auth_failed:{apartment['id']}",
                apartment_id=apartment["id"],
                params={"property": apartment["internal_name"]},
            )
        # The host is not watching the screen when this fires -- the whole point
        # of the automatic send is that nobody is. Mail the same event to the
        # address on the legal entity so a batch that never left is not only
        # discoverable by logging in. Best-effort: it cannot fail the filing.
        mail_notify.submission_problem(
            apartment,
            submission_id,
            state="transport_error",
            reason=str(exc),
            transport=True,
        )
        # Guests stay pending so the next sweep retries them.
        return {"submitted": 0, "submission_id": submission_id, "state": "transport_error",
                "error": str(exc)}

    alerts.resolve(f"submission_transport:{apartment['id']}")

    codebook = codelists.error_codebook()
    now = db.utcnow()
    per_record = result.record_errors
    accepted_count = 0
    failed_count = 0
    blocked_count = 0
    # Records the register refused because it already held them. This is the
    # causal fact behind "ok_duplicate", so the state is keyed on it rather than
    # on the absence of a receipt, which is only a proxy and would misfire on a
    # first-time accept that came back without a confirmation document.
    duplicate_accepts = 0
    # Records the service accepted outright, with no error codes at all. This is
    # what separates a real filing from a batch that only confirmed records the
    # register already had: accepted_count also counts the latter, because a
    # duplicate does move a guest to sent for the first time.
    first_accepts = 0
    # (guest, reservation) pairs that just crossed the automatic retry bound on
    # this attempt. Each one has stopped being offered to the sweep, which the
    # host has to be told or the stop is silent.
    exhausted: List[Any] = []
    guest_writes: List[Tuple[int, Dict[str, Any]]] = []

    for index, (guest, _reservation) in enumerate(pairs):
        record_error = per_record[index] if index < len(per_record) else ""
        state, messages = uby_errors.classify(result.header_errors, record_error, codebook)
        if state == "accepted":
            guest_writes.append(
                (
                    guest["id"],
                    {
                        "submit_state": SENT,
                        "submitted_at": now,
                        # The current pointer, moved on every send - it is not the
                        # batch record, which lives in submission.guest_ids.
                        "submission_id": submission_id,
                        # Keep pointing at the last submission that actually holds
                        # a Dorucenka when this attempt returned none, so a resend
                        # without a receipt request does not lose the link.
                        "receipt_submission_id": (
                            submission_id if result.receipt_pdf else guest["receipt_submission_id"]
                        ),
                        "last_errors": None,
                        # The register took it, so the count of refusals restarts.
                        "submit_attempts": 0,
                        "updated_at": now,
                    },
                )
            )
            accepted_count += 1
            first_accepts += 1
        else:
            new_state = BLOCKED if state == "not_correctable" else ERROR
            # A duplicate response proves the register already has this guest.
            # This also covers an earlier accept whose HTTP response was lost.
            # Only this record's own code 150 proves the register holds it.
            # Prose and header-level messages must not: a false "sent" is a
            # guest who was never filed.
            duplicate = "150" in uby_errors.split_codes(record_error)
            if duplicate:
                new_state = SENT
                duplicate_accepts += 1
            # A refusal counts against the automatic retry budget, a duplicate
            # does not: the register holding the record is an answer, not a
            # failure, so it restarts the count the same way an accept does.
            attempts = 0 if new_state == SENT else auto_attempts(guest) + 1
            if new_state == ERROR and attempts >= SUBMISSION_MAX_AUTO_ATTEMPTS:
                exhausted.append((guest, _reservation))
            update_values = {
                "submit_state": new_state,
                "submission_id": submission_id,
                "last_errors": " | ".join(messages),
                "submit_attempts": attempts,
                "updated_at": now,
            }
            if new_state == SENT:
                update_values["submitted_at"] = guest["submitted_at"] or now
                # The confirmation for this record, if there is one, is on the
                # submission that carried it before this one. A pointer already
                # on file wins: it names the submission that first filed the
                # guest, and deriving again from submission_id - which moves on
                # every send - would drop the link as soon as one duplicate
                # without a confirmation came back.
                update_values["receipt_submission_id"] = (
                    guest["receipt_submission_id"]
                    or receipt_submission_id(guest["submission_id"])
                )
            guest_writes.append((guest["id"], update_values))
            if new_state == SENT:
                # A duplicate for a guest we already had as sent means the
                # register confirms it holds the record. Nothing was refused and
                # nothing is left to do, so it counts as neither accepted nor
                # blocked: duplicate_accepts already records it, and counting it
                # as blocked would raise a critical rejection - and tell the
                # host "were rejected" - for a filing that succeeded.
                if guest["submit_state"] != SENT:
                    accepted_count += 1
            elif new_state == ERROR:
                failed_count += 1
            else:
                blocked_count += 1

    if failed_count or blocked_count:
        state = "partial" if accepted_count else "error"
    elif first_accepts:
        # Something was filed for the first time, so this is a plain success even
        # if other records in the same batch came back as duplicates.
        state = "ok"
    elif duplicate_accepts:
        # Nothing new was filed: the register already held every record, so no
        # Dorucenka came back for this attempt. That is a success, but not the
        # same thing as a first-time accept with a confirmation behind it.
        state = "ok_duplicate"
    else:
        state = "ok"

    # The answer and the Dorucenka are written together with every guest's
    # new state, or not at all. Anything that can fail afterwards (alerts,
    # mail) must not be able to lose the receipt or leave guests pending.
    with db.immediate() as cur:
        for write_id, write_values in guest_writes:
            db.update_in(cur, "guest", write_id, write_values)
        db.update_in(
            cur,
            "submission",
            submission_id,
            {
                "state": state,
                "finished_at": now,
                "header_errors": result.header_errors,
                "record_errors": json.dumps(result.record_errors),
                "pseudo_stamp": result.pseudo_stamp,
                "receipt_pdf": result.receipt_pdf or None,
                "error_pdf": result.error_pdf or None,
                "request_xml": result.request_xml,
                "response_xml": result.response_xml,
            },
        )

    if exhausted:
        # The stop has to be visible. Without this the sweep simply stops
        # offering the record and the only trace is a red guest row nobody was
        # told to look at. One card per stay, so the host can click straight to
        # the guests that need looking at.
        by_reservation: Dict[int, List[Any]] = {}
        for guest, _reservation in exhausted:
            by_reservation.setdefault(_reservation["id"], []).append(guest)
        for reservation_id, guests in by_reservation.items():
            names = [
                (f"{g['surname'] or ''} {g['first_name'] or ''}".strip() or f"#{g['id']}")
                for g in guests
            ]
            alerts.raise_alert(
                "warning",
                "submission_stuck",
                f"{len(guests)} guest record(s) are no longer being sent automatically.",
                f"UbyPort refused these records on {SUBMISSION_MAX_AUTO_ATTEMPTS} consecutive "
                "attempts, so the automatic send has stopped offering them. Check the guest "
                "data, then send the stay again by hand: " + ", ".join(names),
                dedupe_key=f"submission_stuck:{reservation_id}",
                apartment_id=apartment["id"],
                reservation_id=reservation_id,
            )

    for _reservation_id in {_reservation["id"] for _guest, _reservation in pairs}:
        clear_stuck_alert_if_recovered(_reservation_id)

    if state in ("ok", "ok_duplicate"):
        alerts.resolve(f"submission_rejected:{apartment['id']}")
        # The in-doubt card is apartment-wide. This batch only answered for its
        # own guests; if another guest still points at an unknown batch, the
        # card has to stay up or the warning disappears while the sweep keeps
        # silently excluding them.
        if not apartment_in_doubt(apartment["id"]):
            alerts.resolve(f"submission_outcome_unknown:{apartment['id']}")
    else:
        log.error(
            "ubyport_submission_rejected apartment_id=%s owner_user_id=%s "
            "submission_id=%s env=%s endpoint=%s state=%s accepted=%s failed=%s blocked=%s",
            apartment["id"],
            apartment["owner_user_id"],
            submission_id,
            env or config.UBYPORT_ENV,
            endpoint,
            state,
            accepted_count,
            failed_count,
            blocked_count,
        )
        detail_bits = []
        header_errors = ""
        if result.header_errors:
            header_errors = ", ".join(
                uby_errors.describe(c, codebook)
                for c in uby_errors.split_codes(result.header_errors)
            )
            detail_bits.append(f"Report header rejected: {header_errors}")
        detail_bits.append(f"{failed_count} record(s) to fix, {blocked_count} that resending will not fix.")
        alerts.raise_alert(
            "critical",
            "submission_rejected",
            f"{apartment['internal_name']}: UbyPort did not accept {failed_count + blocked_count} "
            f"guest record(s).",
            " ".join(detail_bits),
            dedupe_key=f"submission_rejected:{apartment['id']}",
            apartment_id=apartment["id"],
            params={
                "property": apartment["internal_name"],
                "count": failed_count + blocked_count,
                "failed": failed_count,
                "blocked": blocked_count,
                "header": header_errors,
            },
        )
        # Same event, same reasoning as the transport branch: an alert only
        # reaches someone who is looking at the app, and the automatic send
        # exists precisely so nobody has to. The mail carries the UbyPort reason
        # text and a link back to the affected stays. It is sent for a manual
        # send too -- the host asked for that one, but the record of what the
        # register said is still worth having in the inbox.
        mail_notify.submission_problem(
            apartment,
            submission_id,
            state=state,
            reason=" ".join(detail_bits),
        )

    # The third product promise: the Dorucenka is kept. A first-time accept that
    # came back with neither a stamp nor a confirmation document means the
    # register has the record and we hold no proof of it. A duplicate accept is
    # not evidence of that either way, so it neither raises nor resolves this.
    if result.pseudo_stamp or result.receipt_pdf:
        alerts.resolve(f"receipt_missing:{apartment['id']}")
    elif state == "ok" and first_accepts:
        alerts.raise_alert(
            "warning",
            "receipt_missing",
            f"{apartment['internal_name']}: UbyPort accepted the report but returned no confirmation.",
            f"Submission {submission_id} recorded {first_accepts} accepted guest record(s) "
            "with no Dorucenka and no stamp behind them. The register has them; ask the "
            "police for a copy if you need written proof.",
            dedupe_key=f"receipt_missing:{apartment['id']}",
            apartment_id=apartment["id"],
            params={
                "property": apartment["internal_name"],
                "submission": submission_id,
                "count": first_accepts,
            },
        )

    db.audit(
        "ubyport_submit",
        f"apartment={apartment['id']} submission={submission_id} state={state} "
        f"accepted={accepted_count} failed={failed_count} blocked={blocked_count}",
        owner_user_id=apartment["owner_user_id"],
    )
    return {
        "submitted": accepted_count,
        "failed": failed_count,
        "blocked": blocked_count,
        "submission_id": submission_id,
        "state": state,
        "stamp": result.pseudo_stamp,
    }


def submit_for_apartment(
    apartment_id: int,
    only_guest_ids: Optional[List[int]] = None,
    mode: str = "auto",
    ignore_automation: bool = False,
    allow_resend: bool = False,
    env: Optional[str] = None,
    ignore_schedule: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Send everything currently sendable for one apartment, in batches.

    Deliberately takes no actor. Verification of a guest's identity is a host
    attestation against a travel document, recorded by the explicit Verify
    route; this function also runs unattended from the scheduler, where nobody
    has looked at anything and stamping a verification would be a fabrication.
    """
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment:
        return []

    from . import demo

    if demo.is_demo_apartment(apartment):
        return [
            {
                "state": "noop",
                "error": "Demo data is for preview only and is never sent to the police.",
                "error_key": "flash.error.demo_preview_only",
            }
        ]

    ap_dict = dict(apartment)
    ap_dict["uby_ws_password"] = db.decrypt_secret(apartment["uby_ws_password_enc"])
    setup_errors = validation.errors_only(validation.validate_apartment(ap_dict))
    if setup_errors:
        alerts.raise_alert(
            "warning",
            "apartment_setup",
            f"{apartment['internal_name']}: UbyPort settings are incomplete, nothing can be reported.",
            validation.issues_to_text(setup_errors),
            dedupe_key=f"apartment_setup:{apartment_id}",
            apartment_id=apartment_id,
            params={"property": apartment["internal_name"]},
        )
        return [{"state": "not_configured", "error": validation.issues_to_text(setup_errors)}]
    alerts.resolve(f"apartment_setup:{apartment_id}")

    pairs = collect_sendable(
        apartment_id, only_guest_ids, ignore_automation, allow_resend, ignore_schedule
    )
    if not pairs:
        return []

    claim_token, pairs = claim_sendable(pairs)
    if not pairs:
        return []
    try:
        limit = config.UBYPORT_MAX_BATCH
        results = []
        for start in range(0, len(pairs), limit):
            results.append(
                submit_batch(
                    apartment,
                    pairs[start:start + limit],
                    mode=mode,
                    env=env,
                )
            )
        return results
    finally:
        release_sendable_claim(claim_token)


def sweep(owner_user_id: Optional[int] = None) -> Dict[str, Any]:
    """Scheduled pass over active apartments, optionally for one workspace."""
    summary = {"apartments": 0, "submitted": 0, "failed": 0}
    for apartment in db.query(
        "SELECT * FROM apartment WHERE active = 1 AND automation_mode != 'manual' "
        "AND (? IS NULL OR owner_user_id = ?)",
        (owner_user_id, owner_user_id),
    ):
        if alerts.open_alert(f"ubyport_auth_failed:{apartment['id']}"):
            # Retrying a refused login every ten minutes risks locking the
            # police account. Wait until the host saves new credentials.
            continue
        summary["apartments"] += 1
        try:
            # The quiet-window completion is the one decision nobody makes: the
            # common case is a guest who simply stops filling the form in, and
            # only a pass that runs when nobody is looking can notice it. It
            # used to be evaluated only when a form was saved, so a stay whose
            # party had gone quiet was never completed and never filed.
            for pending in db.query(
                "SELECT id FROM reservation WHERE apartment_id = ? AND status = 'active' "
                "AND archived_at IS NULL AND registration_completed_at IS NULL",
                (apartment["id"],),
            ):
                refresh_registration_completed_at(pending["id"])
            results = submit_for_apartment(apartment["id"], mode="auto")
            alerts.resolve(f"sweep_failed:{apartment['id']}")
        except db.DecryptionError:
            # One guest row that will not decrypt used to abort the whole sweep,
            # so no host anywhere was filed or alerted. Contain it to the one
            # property it belongs to and name it.
            log.exception("sweep stopped for apartment_id=%s", apartment["id"])
            summary["failed"] += 1
            alerts.raise_alert(
                "critical",
                "guest_record_unreadable",
                f"{apartment['internal_name']}: a guest record cannot be read, so "
                "nothing is being reported for this property.",
                "A stored guest document field could not be decrypted. Restore the "
                "encryption key, or have the guest's document entered again.",
                dedupe_key=f"guest_record_unreadable:{apartment['id']}",
                apartment_id=apartment["id"],
                params={"property": apartment["internal_name"]},
            )
            continue
        except Exception:
            # Any other failure is contained to this property too: one bad
            # row or a locked database must not leave every later property
            # unfiled on every sweep.
            log.exception("sweep failed for apartment_id=%s", apartment["id"])
            summary["failed"] += 1
            alerts.raise_alert(
                "critical",
                "sweep_failed",
                f"{apartment['internal_name']}: automatic reporting stopped because of an internal error.",
                "Nothing was sent for this property on the last run.",
                dedupe_key=f"sweep_failed:{apartment['id']}",
                apartment_id=apartment["id"],
                params={"property": apartment["internal_name"]},
            )
            continue
        for result in results:
            summary["submitted"] += result.get("submitted", 0)
            summary["failed"] += result.get("failed", 0) + result.get("blocked", 0)
    return summary


# --- deadline monitoring -------------------------------------------------

def reservation_deadline_anchor(reservation: Dict[str, Any]) -> Optional[date]:
    """The date the statutory clock starts from.

    The record filed with the police carries each guest's own ``stay_from``, so
    the deadline has to run from the earliest of those. Earliest, because the
    clock starts at the first arrival. Falls back to the reservation's own
    ``date_from`` when no guest has given a date.
    """
    rows = db.query(
        "SELECT stay_from FROM guest WHERE reservation_id = ? AND archived_at IS NULL "
        "AND stay_from IS NOT NULL AND stay_from != ''",
        (reservation["id"],),
    )
    starts = [validation.parse_iso_date(row["stay_from"]) for row in rows]
    starts = [start for start in starts if start]
    if starts:
        return min(starts)
    return validation.parse_iso_date(reservation["date_from"])


def check_deadlines(
    now: Optional[datetime] = None, owner_user_id: Optional[int] = None
) -> int:
    """Alert on stays that are running out of legal time with data missing.

    This is the part the host asked for: not "here is a list of bookings" but
    "these ones will make you non-compliant unless you chase the guest today".
    """
    now = deadlines.local_now(now)
    raised = 0
    # A cancelled, ignored or archived stay has nothing left to chase. One
    # statement, not one connection per card. When the caller is a single
    # host's request (/sync_now carries the owner) only that workspace's cards
    # may be cleared; the scheduled run passes no owner and clears them all.
    db.execute(
        "UPDATE alert SET resolved_at = ?, user_dismissed = 0 WHERE id IN ("
        "SELECT al.id FROM alert al "
        "JOIN reservation r ON r.id = al.reservation_id "
        "JOIN apartment a ON a.id = r.apartment_id "
        "WHERE al.resolved_at IS NULL "
        "AND al.kind IN ('deadline', 'headcount_mismatch', 'guest_incomplete_checkin') "
        "AND (r.status != 'active' OR r.archived_at IS NOT NULL) "
        "AND (? IS NULL OR a.owner_user_id = ?)"
        ")",
        (db.utcnow(), owner_user_id, owner_user_id),
    )
    rows = db.query(
        "SELECT r.*, a.internal_name FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 "
        "AND (? IS NULL OR a.owner_user_id = ?)",
        (owner_user_id, owner_user_id),
    )
    for reservation in rows:
        try:
            # The clock runs from the earliest guest arrival, which can be
            # earlier than the reservation's own start. Selecting rows by
            # r.date_from therefore skipped exactly the stays that arrived early
            # and were already late; the anchor decides, not the SQL filter.
            start = reservation_deadline_anchor(reservation)
            if not start:
                continue
            progress = reservation_progress(reservation)
        except db.DecryptionError:
            # A guest row that will not decrypt used to abort the whole watch,
            # so no host anywhere was told about a deadline. Contain it to the
            # stay that owns the row.
            log.exception("deadline watch stopped for reservation_id=%s", reservation["id"])
            alerts.raise_alert(
                "critical",
                "guest_record_unreadable",
                f"{reservation['internal_name']}: a guest record cannot be read, so "
                "this stay is not being watched.",
                "A stored guest document field could not be decrypted. Restore the "
                "encryption key, or have the guest's document entered again.",
                dedupe_key=f"guest_record_unreadable:reservation:{reservation['id']}",
                apartment_id=reservation["apartment_id"],
                reservation_id=reservation["id"],
                params={"property": reservation["internal_name"]},
            )
            continue
        key = f"deadline:{reservation['id']}"
        mismatch_key = f"headcount_mismatch:{reservation['id']}"
        settled = progress["status"] in ("reported", "not_required")
        expected_count = progress["expected"]
        check_in = validation.parse_iso_date(reservation["date_from"])
        stay_end = validation.parse_iso_date(reservation["date_to"])
        dates = check_in.strftime("%d.%m.%Y") if check_in else ""
        if stay_end:
            dates = f"{dates} – {stay_end.strftime('%d.%m.%Y')}"
        title = f"{reservation['internal_name']} · {dates}"
        # "Waiting for guest" and "the guest link held the filing open" look
        # identical on the dashboard. Once the stay has started, say which one
        # it is, so a shortfall is chased instead of quietly waited on.
        if (
            not settled
            and expected_count is not None
            and progress["filled"] < expected_count
            and start < now.date()
        ):
            alerts.raise_alert(
                "warning",
                "headcount_mismatch",
                title,
                f"Waiting for guest forms · {progress['filled']}/{expected_count}",
                dedupe_key=mismatch_key,
                apartment_id=reservation["apartment_id"],
                reservation_id=reservation["id"],
            )
        else:
            alerts.resolve(mismatch_key)
        if settled:
            alerts.resolve(key)
            continue
        level = deadlines.urgency(start, now)
        if level in ("overdue", "urgent"):
            filled = progress["filled"]
            expected = progress["expected"] if progress["expected"] is not None else "?"
            if level == "overdue":
                countdown = deadlines.describe_time_left(start, now)
                if countdown.startswith("overdue"):
                    countdown = countdown[0].upper() + countdown[1:]
                detail = f"{countdown} · {filled}/{expected}"
            else:
                detail = f"Due now · {filled}/{expected}"
            alerts.raise_alert(
                "critical" if level == "overdue" else "warning",
                "deadline",
                title,
                detail,
                dedupe_key=key,
                apartment_id=reservation["apartment_id"],
                reservation_id=reservation["id"],
            )
            raised += 1
        else:
            alerts.resolve(key)
    return raised


MAX_RECEIPT_DOWNLOADS = 100


def receipt_zip_name(row: Any) -> str:
    stamp = re.sub(r"[^\w.\-]+", "_", (row["pseudo_stamp"] or str(row["id"]))[:36])
    date_part = (row["created_at"] or "")[:10] or "report"
    return f"dorucenka-{date_part}-{row['id']}-{stamp}.pdf"


def build_receipts_zip(rows: List[Any], dest_path: str) -> int:
    """Write Doručenka PDFs to a zip on disk, one file at a time."""
    count = 0
    with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for row in rows:
            raw_b64 = row["receipt_pdf"]
            if not raw_b64:
                continue
            try:
                raw = base64.b64decode(raw_b64)
            except Exception:
                continue
            archive.writestr(receipt_zip_name(row), raw)
            count += 1
    return count


# --- retention -----------------------------------------------------------

# Every state a submission row can settle in. A row is only 'running' while
# the submit call is in flight, and the envelope is stored at the moment the
# row moves to one of these, so a 'running' row has no envelope to purge.
TERMINAL_SUBMISSION_STATES = ("ok", "ok_duplicate", "partial", "error", "transport_error", "outcome_unknown")

# The envelope is the only thing in the row that carries guest data, and the
# row outlives the six-year purge of the guests it describes, so it goes far
# sooner than they do.
SUBMISSION_PAYLOAD_DAYS = 90


def purge_submission_payloads(
    owner_user_id: Optional[int] = None, days: int = SUBMISSION_PAYLOAD_DAYS
) -> int:
    """Blank the request and response envelopes on settled submissions.

    ``request_xml`` carries every reported guest's passport number, and nothing
    else in the codebase ever deleted it: the guest rows age out after six
    years, the submission row does not. The Dorucenka and the pseudo stamp stay,
    because those are the evidence the host has to be able to produce, and
    neither of them contains guest data.

    Returns the number of rows that were carrying an envelope and lost it.
    """
    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).replace(microsecond=0).isoformat()
    marks = ", ".join("?" for _ in TERMINAL_SUBMISSION_STATES)
    rows = db.query(
        f"SELECT s.id AS id FROM submission s "
        f"JOIN apartment a ON a.id = s.apartment_id "
        f"WHERE s.created_at < ? AND s.state IN ({marks}) "
        f"AND (? IS NULL OR a.owner_user_id = ?) "
        f"AND (s.request_xml IS NOT NULL OR s.response_xml IS NOT NULL)",
        (cutoff, *TERMINAL_SUBMISSION_STATES, owner_user_id, owner_user_id),
    )
    if not rows:
        return 0
    ids = [row["id"] for row in rows]
    id_marks = ", ".join("?" for _ in ids)
    db.execute(
        f"UPDATE submission SET request_xml = NULL, response_xml = NULL "
        f"WHERE id IN ({id_marks})",
        ids,
    )
    db.audit(
        "submission_payload_purge",
        f"blanked the request and response envelope on {len(ids)} submission(s) "
        f"older than {days} days",
    )
    return len(ids)
