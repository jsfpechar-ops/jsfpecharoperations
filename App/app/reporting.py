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

import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from . import alerts, codelists, config, db, deadlines, validation
from .ubyport import errors as uby_errors
from .ubyport.client import SubmissionResult, UbyportClient, UbyportError, UbyportTransportError

# guest.submit_state values
PENDING = "pending"
SENT = "sent"
ERROR = "error"
BLOCKED = "blocked"  # rejected in a way that resending cannot fix
NOT_REQUIRED = "not_required"  # Czech nationals: house book only

AUTOMATION_MODES = ("immediate", "scheduled", "manual")


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


def guest_issues(guest, reservation) -> List[validation.Issue]:
    start, end = _stay_dates(guest, reservation)
    return validation.validate_guest(guest_dict(guest), start, end)


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
        "SELECT * FROM guest WHERE reservation_id = ? ORDER BY is_lead DESC, id", (reservation["id"],)
    )
    expected = expected_guest_count(reservation)
    complete = [g for g in guests if guest_is_complete(g, reservation)]
    reportable = [g for g in complete if validation.guest_is_reportable(g["nationality"])]
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
        status = "ready"
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
        "sent": sent,
        "failed": failed,
        "status": status,
    }


STATUS_LABELS = {
    "awaiting_guest": "Waiting for guest",
    "incomplete": "Incomplete",
    "ready": "Ready to report",
    "reported": "Reported",
    "not_required": "No reporting duty",
    "failed": "Rejected",
}


def pending_reportable(guests: List[Any]) -> List[Any]:
    """Reportable guests that have not yet been accepted by UbyPort."""
    return [
        guest
        for guest in guests
        if validation.guest_is_reportable(guest["nationality"])
        and guest["submit_state"] not in (SENT, BLOCKED)
    ]


def status_label(status: str, automation_mode: Optional[str] = None) -> str:
    """Human label for a stay's reporting status, with automation context."""
    if status == "ready" and automation_mode == "immediate":
        return "Ready — auto-send"
    if status == "ready" and automation_mode == "manual":
        return "Ready — send manually"
    if status == "ready" and automation_mode == "scheduled":
        return "Ready — scheduled send"
    return STATUS_LABELS.get(status, status)


def send_controls(reservation, apartment, progress: Dict[str, Any]) -> Dict[str, Any]:
    """Whether Send / Review actions should appear on a stay row."""
    mode = apartment["automation_mode"]
    reviewed = bool(reservation["report_reviewed_at"])
    pending = pending_reportable(progress["reportable"])
    has_pending = bool(pending)
    can_send = progress["status"] in ("ready", "failed") and has_pending
    auto_immediate = mode == "immediate"
    requires_review = mode == "manual"

    send_enabled = can_send and not auto_immediate
    if requires_review and not reviewed:
        send_enabled = False

    if auto_immediate:
        send_hint = "Sends automatically when a guest completes their form"
    elif requires_review and not reviewed:
        send_hint = "Review guest details first, then send"
    elif not has_pending:
        send_hint = "Nothing left to send for this stay"
    elif not can_send:
        send_hint = "Complete guest details before sending"
    else:
        send_hint = "Send completed guest records to UbyPort now"

    needs_attention = progress["status"] not in ("reported", "not_required")
    active_stay = reservation["status"] == "active" and not reservation["archived_at"]

    if not active_stay or not needs_attention:
        review_mode = "none"
    elif reviewed:
        review_mode = "done"
    elif progress["status"] in ("ready", "failed") and requires_review:
        review_mode = "mark"
    elif progress["status"] in ("ready", "failed", "incomplete", "awaiting_guest"):
        review_mode = "open"
    else:
        review_mode = "none"

    if review_mode == "mark":
        review_hint = "Confirm you have checked every guest detail, then send"
    elif review_mode == "open":
        review_hint = "Open the stay and complete or check guest details"
    elif review_mode == "done":
        review_hint = "Reviewed — open guest details or send now"
    else:
        review_hint = ""

    send_visible = has_pending and progress["status"] in ("ready", "failed")

    return {
        "send_enabled": send_enabled,
        "send_visible": send_visible or (auto_immediate and has_pending),
        "send_hint": send_hint,
        "review_visible": review_mode != "none",
        "review_mode": review_mode,
        "review_hint": review_hint,
        "reviewed": reviewed,
        "auto_immediate": auto_immediate,
        "requires_review": requires_review,
        "pending_count": len(pending),
    }


def maybe_submit_after_host_save(apartment_id: int, guest_id: int) -> None:
    """Immediate automation also applies when the host enters guest details."""
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment or apartment["automation_mode"] != "immediate":
        return
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    if not guest:
        return
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (guest["reservation_id"],))
    if not reservation or reservation["status"] != "active":
        return
    if not guest_is_complete(guest, reservation) or not validation.guest_is_reportable(guest["nationality"]):
        return
    if guest["submit_state"] == SENT:
        return
    try:
        submit_for_apartment(apartment_id, only_guest_ids=[guest_id], mode="immediate", ignore_automation=True)
    except Exception:
        pass


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
    """Whether the apartment's automation setting says to send this now."""
    now = now or datetime.now()
    mode = apartment["automation_mode"]
    if mode == "manual":
        return False
    if mode == "immediate":
        return True
    start = validation.parse_iso_date(reservation["date_from"])
    if not start:
        return False
    delay = timedelta(hours=apartment["submit_after_hours"] or 24)
    return now >= datetime.combine(start, datetime.min.time()) + delay


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


# --- submission ----------------------------------------------------------

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
        "WHERE r.apartment_id = ? AND r.status = 'active'"
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
        if not guest_is_complete(guest, reservation):
            continue
        if not ignore_automation and not due_for_automatic_send(apartment, reservation):
            continue
        out.append((guest, reservation))
    return out


def submit_batch(
    apartment,
    pairs: List[Tuple[Any, Any]],
    mode: str = "auto",
    want_pdf: bool = True,
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
            # "Duplicate" means the register already holds this record. If we
            # are the ones who put it there, the guest is still reported and
            # the stay must not start showing up as a failure.
            if guest["submit_state"] == SENT and any(
                uby_errors.is_duplicate(message) for message in messages
            ):
                new_state = SENT
            db.update(
                "guest",
                guest["id"],
                {
                    "submit_state": new_state,
                    "submission_id": submission_id,
                    "last_errors": " | ".join(messages),
                    "updated_at": now,
                },
            )
            if new_state == ERROR:
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
) -> List[Dict[str, Any]]:
    """Send everything currently sendable for one apartment, in batches."""
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    if not apartment:
        return []

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

    limit = config.UBYPORT_MAX_BATCH
    results = []
    for start in range(0, len(pairs), limit):
        results.append(submit_batch(apartment, pairs[start:start + limit], mode=mode, env=env))
    return results


def sweep() -> Dict[str, Any]:
    """Scheduled pass over every active apartment."""
    summary = {"apartments": 0, "submitted": 0, "failed": 0}
    for apartment in db.query("SELECT * FROM apartment WHERE active = 1 AND automation_mode != 'manual'"):
        summary["apartments"] += 1
        for result in submit_for_apartment(apartment["id"], mode="auto"):
            summary["submitted"] += result.get("submitted", 0)
            summary["failed"] += result.get("failed", 0) + result.get("blocked", 0)
    return summary


# --- deadline monitoring -------------------------------------------------

def check_deadlines(now: Optional[datetime] = None) -> int:
    """Alert on stays that are running out of legal time with data missing.

    This is the part the host asked for: not "here is a list of bookings" but
    "these ones will make you non-compliant unless you chase the guest today".
    """
    now = now or datetime.now()
    raised = 0
    horizon = (now.date() - timedelta(days=30)).isoformat()
    rows = db.query(
        "SELECT r.*, a.internal_name FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE r.status = 'active' AND a.active = 1 AND r.date_from >= ? AND r.date_from <= ?",
        (horizon, now.date().isoformat()),
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
            alerts.raise_alert(
                "critical" if level == "overdue" else "warning",
                "deadline",
                f"{reservation['internal_name']}: stay from {reservation['date_from']} is "
                f"{deadlines.describe_time_left(start, now)} and is not fully reported.",
                f"Status: {STATUS_LABELS.get(progress['status'], progress['status'])}. "
                f"{progress['filled']} of {progress['expected'] or '?'} guest form(s) complete.",
                dedupe_key=key,
                apartment_id=reservation["apartment_id"],
                reservation_id=reservation["id"],
            )
            raised += 1
        else:
            alerts.resolve(key)
    return raised
