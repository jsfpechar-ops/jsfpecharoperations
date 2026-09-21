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

from . import alerts, codelists, config, db, deadlines, passport_photos, validation
from .ubyport import errors as uby_errors
from .ubyport.client import SubmissionResult, UbyportClient, UbyportError, UbyportTransportError

log = logging.getLogger("ubyhost.reporting")

# guest.submit_state values
PENDING = "pending"
SENT = "sent"
ERROR = "error"
BLOCKED = "blocked"  # rejected in a way that resending cannot fix
NOT_REQUIRED = "not_required"  # Czech nationals: house book only

AUTOMATION_MODES = ("immediate", "scheduled", "manual")
SUBMISSION_CLAIM_TTL_SECONDS = 5 * 60


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
    if signature == "imported":
        return True
    return signature.startswith("data:image/")


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


def guest_needs_passport_photo(guest, apartment=None) -> bool:
    """Online foreign guests upload a photo only when the property requires it."""
    if apartment is None:
        reservation = db.query_one(
            "SELECT apartment_id FROM reservation WHERE id = ?", (guest["reservation_id"],)
        )
        if not reservation:
            return False
        apartment = db.query_one(
            "SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],)
        )
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


def guest_issues(guest, reservation) -> List[validation.Issue]:
    start, end = _stay_dates(guest, reservation)
    issues = validation.validate_guest(guest_dict(guest), start, end)
    if not guest_has_signature(guest):
        issues.append(
            validation.Issue(
                "signature",
                "A guest signature is required. Use the guest link or sign on the host form.",
            )
        )
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
    reportable = [g for g in complete if validation.guest_is_reportable(g["nationality"])]
    unverified = [g for g in reportable if not guest_identity_verified(g)]
    sent = [g for g in guests if g["submit_state"] == SENT]
    failed = [g for g in guests if g["submit_state"] in (ERROR, BLOCKED)]
    incomplete = [g for g in guests if not guest_is_complete(g, reservation)]

    missing = None
    if expected is not None:
        missing = max(0, expected - len(complete))

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
        "incomplete": incomplete,
        "reportable": reportable,
        "unverified": unverified,
        "sent": sent,
        "failed": failed,
        "status": status,
    }


STATUS_LABELS = {
    "awaiting_guest": "Waiting for guest",
    "incomplete": "Incomplete",
    "awaiting_verification": "Awaiting passport check",
    "ready": "Ready to report",
    "reported": "Reported",
    "not_required": "No reporting duty",
    "failed": "Rejected",
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


def status_label(status: str, automation_mode: Optional[str] = None) -> str:
    """Human label for a stay's reporting status, with automation context."""
    if status in ("ready", "awaiting_verification") and automation_mode == "immediate":
        return "Complete — sending automatically"
    if status in ("ready", "awaiting_verification") and automation_mode == "scheduled":
        return "Complete — scheduled send"
    if status == "awaiting_verification":
        return "Verify passport before reporting"
    if status in ("awaiting_guest", "incomplete") and automation_mode == "immediate":
        return "Waiting for guest"
    if status == "ready" and automation_mode == "manual":
        return "Ready — send manually"
    return STATUS_LABELS.get(status, status)


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
            "is_demo": True,
        }

    if auto_immediate:
        send_hint_key = "hint.auto_immediate"
    elif not has_pending and progress["status"] in ("not_required", "reported"):
        send_hint_key = "hint.nothing_duty"
    elif not progress.get("guests"):
        send_hint_key = "hint.awaiting_guest"
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
    }


def try_immediate_submit(apartment_id: int, guest_id: int) -> None:
    """Compatibility wrapper for callers that have a guest id."""
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    if guest:
        maybe_submit_after_completion(apartment_id, guest["reservation_id"])


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
    complete = (
        progress["expected"] is not None
        and progress["filled"] >= progress["expected"]
        and not progress["incomplete"]
    )
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
    elif not complete and existing:
        db.update(
            "reservation",
            reservation_id,
            {"registration_completed_at": None, "updated_at": db.utcnow()},
        )
        existing = None
    return existing


def maybe_submit_after_completion(apartment_id: int, reservation_id: int) -> None:
    """Send an immediate-mode stay once every declared form is complete."""
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
            ignore_automation=True,
        )
    except Exception as exc:
        alerts.raise_alert(
            "warning",
            "submission_immediate",
            f"{apartment['internal_name']}: automatic send failed after registration completed.",
            str(exc),
            dedupe_key=f"submission_immediate:{apartment_id}",
            apartment_id=apartment_id,
        )


def maybe_submit_after_host_save(apartment_id: int, guest_id: int) -> None:
    """Re-evaluate completion after a host saves a guest."""
    try_immediate_submit(apartment_id, guest_id)


def maybe_submit_after_verify(apartment_id: int, guest_id: int) -> None:
    """Verification no longer gates automatic submission."""
    return None


def count_sendable_stays(reservations: List[Any]) -> int:
    """How many stays can be sent right now with the bulk action."""
    count = 0
    for reservation in reservations:
        apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],))
        if not apartment or not apartment["active"]:
            continue
        progress = reservation_progress(reservation)
        if send_controls(reservation, apartment, progress)["send_enabled"]:
            count += 1
    return count


def due_for_automatic_send(apartment, reservation, now: Optional[datetime] = None) -> bool:
    """Whether completion-based automation says to send this stay now."""
    mode = apartment["automation_mode"]
    if mode == "manual":
        return False
    # Do not backfill this during a scheduler sweep. Existing production
    # reservations predate completion-based automation and must not suddenly
    # become eligible merely because the new code was deployed.
    completed_at = reservation["registration_completed_at"]
    if not completed_at:
        return False
    try:
        completed = datetime.fromisoformat(completed_at)
    except (TypeError, ValueError):
        return False
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    delay = timedelta(
        hours=0 if mode == "immediate" else (apartment["submit_after_hours"] or 24)
    )
    return current.astimezone(timezone.utc) >= completed.astimezone(timezone.utc) + delay


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
    *,
    on_send: bool = False,
) -> None:
    """Host confirms guest details against a travel document (optional before send)."""
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    if not guest or not validation.guest_is_reportable(guest["nationality"]):
        return
    if guest["identity_verified_at"]:
        return
    now = db.utcnow()
    # Verification is the whole reason the photo exists, so it goes here rather
    # than only on the explicit Verify route. Most hosts verify by sending, and
    # that path used to leave the scan on disk until the retention sweep.
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
    flag = "on_send=1" if on_send else "on_send=0"
    db.audit(
        "guest_identity_verified",
        f"id={guest_id} {flag}",
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


def collect_sendable(apartment_id: int, only_guest_ids: Optional[List[int]] = None,
                     ignore_automation: bool = False, allow_resend: bool = False
                     ) -> List[Tuple[Any, Any]]:
    """Guest rows that may legitimately be sent right now, with reservations."""
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

    out: List[Tuple[Any, Any]] = []
    for guest in db.query(sql, params):
        reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (guest["reservation_id"],))
        if not reservation:
            continue
        if not validation.guest_is_reportable(guest["nationality"]):
            if guest["submit_state"] != NOT_REQUIRED:
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
        if not guest_is_complete(guest, reservation):
            continue
        if not ignore_automation:
            if not due_for_automatic_send(apartment, reservation):
                continue
        out.append((guest, reservation))
    return out


def claim_sendable(
    pairs: List[Tuple[Any, Any]],
) -> Tuple[str, List[Tuple[Any, Any]]]:
    """Atomically lease guests so concurrent workers cannot submit duplicates."""
    token = secrets.token_urlsafe(18)
    claimed_ids = set()
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM submission_claim WHERE claimed_at < ?",
            (time.time() - SUBMISSION_CLAIM_TTL_SECONDS,),
        )
        for guest, _reservation in pairs:
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


def submit_batch(
    apartment,
    pairs: List[Tuple[Any, Any]],
    mode: str = "auto",
    want_pdf: bool = True,
    env: Optional[str] = None,
    verified_by_user_id: Optional[int] = None,
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
        result: SubmissionResult = client.submit(header, guests, want_pdf=want_pdf)
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

    for index, (guest, _reservation) in enumerate(pairs):
        record_error = per_record[index] if index < len(per_record) else ""
        state, messages = uby_errors.classify(result.header_errors, record_error, codebook)
        if state == "accepted":
            db.update(
                "guest",
                guest["id"],
                {
                    "submit_state": SENT,
                    "submitted_at": now,
                    "submission_id": submission_id,
                    "last_errors": None,
                    "updated_at": now,
                },
            )
            accepted_count += 1
        else:
            new_state = BLOCKED if state == "not_correctable" else ERROR
            # A duplicate response proves the register already has this guest.
            # This also covers an earlier accept whose HTTP response was lost.
            duplicate = "150" in uby_errors.split_codes(record_error) or any(
                uby_errors.is_duplicate(message) for message in messages
            )
            if duplicate:
                new_state = SENT
            update_values = {
                "submit_state": new_state,
                "submission_id": submission_id,
                "last_errors": " | ".join(messages),
                "updated_at": now,
            }
            if new_state == SENT:
                update_values["submitted_at"] = guest["submitted_at"] or now
            db.update("guest", guest["id"], update_values)
            if new_state == SENT:
                if guest["submit_state"] == SENT:
                    blocked_count += 1
                else:
                    accepted_count += 1
            elif new_state == ERROR:
                failed_count += 1
            else:
                blocked_count += 1

    if failed_count or blocked_count:
        state = "partial" if accepted_count else "error"
    else:
        state = "ok"

    db.update(
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

    if state == "ok":
        alerts.resolve(f"submission_rejected:{apartment['id']}")
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
        if result.header_errors:
            detail_bits.append(
                "Report header rejected: "
                + ", ".join(
                    uby_errors.describe(c, codebook)
                    for c in uby_errors.split_codes(result.header_errors)
                )
            )
        detail_bits.append(f"{failed_count} record(s) to fix, {blocked_count} that resending will not fix.")
        alerts.raise_alert(
            "critical",
            "submission_rejected",
            f"{apartment['internal_name']}: UbyPort did not accept {failed_count + blocked_count} "
            f"guest record(s).",
            " ".join(detail_bits),
            dedupe_key=f"submission_rejected:{apartment['id']}",
            apartment_id=apartment["id"],
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
    verified_by_user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Send everything currently sendable for one apartment, in batches."""
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment:
        return []

    from . import demo

    if demo.is_demo_apartment(apartment):
        return [{"state": "noop", "error": "Demo data is for preview only and is never sent to the police."}]

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
        )
        return [{"state": "not_configured", "error": validation.issues_to_text(setup_errors)}]
    alerts.resolve(f"apartment_setup:{apartment_id}")

    pairs = collect_sendable(apartment_id, only_guest_ids, ignore_automation, allow_resend)
    if not pairs:
        return []

    claim_token, pairs = claim_sendable(pairs)
    if not pairs:
        return []
    try:
        actor = verified_by_user_id if verified_by_user_id is not None else apartment["owner_user_id"]
        limit = config.UBYPORT_MAX_BATCH
        results = []
        for start in range(0, len(pairs), limit):
            results.append(
                submit_batch(
                    apartment,
                    pairs[start:start + limit],
                    mode=mode,
                    env=env,
                    verified_by_user_id=actor,
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
        summary["apartments"] += 1
        for result in submit_for_apartment(apartment["id"], mode="auto"):
            summary["submitted"] += result.get("submitted", 0)
            summary["failed"] += result.get("failed", 0) + result.get("blocked", 0)
    return summary


# --- deadline monitoring -------------------------------------------------

def check_deadlines(
    now: Optional[datetime] = None, owner_user_id: Optional[int] = None
) -> int:
    """Alert on stays that are running out of legal time with data missing.

    This is the part the host asked for: not "here is a list of bookings" but
    "these ones will make you non-compliant unless you chase the guest today".
    """
    now = deadlines.local_now(now)
    raised = 0
    rows = db.query(
        "SELECT r.*, a.internal_name FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 "
        "AND (? IS NULL OR a.owner_user_id = ?) AND r.date_from <= ?",
        (owner_user_id, owner_user_id, now.date().isoformat()),
    )
    for reservation in rows:
        start = validation.parse_iso_date(reservation["date_from"])
        if not start:
            continue
        progress = reservation_progress(reservation)
        key = f"deadline:{reservation['id']}"
        if progress["status"] in ("reported", "not_required"):
            alerts.resolve(key)
            continue
        level = deadlines.urgency(start, now)
        if level in ("overdue", "urgent"):
            filled = progress["filled"]
            expected = progress["expected"] if progress["expected"] is not None else "?"
            start_label = start.strftime("%d.%m.%Y")
            end = validation.parse_iso_date(reservation["date_to"])
            end_label = end.strftime("%d.%m.%Y") if end else ""
            dates = f"{start_label} – {end_label}" if end_label else start_label
            title = f"{reservation['internal_name']} · {dates}"
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
