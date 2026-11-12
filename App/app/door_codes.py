"""Door code issuing, delivery and lifecycle (TTLock)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from . import alerts, config, db, deadlines, mail, mail_notify, push, ttlock

log = logging.getLogger(__name__)

PENDING, ISSUING, RETRYING, ISSUED, FAILED, EXPIRED = (
    "pending",
    "issuing",
    "retrying",
    "issued",
    "failed",
    "expired",
)
REVOKE_PENDING = "revoke_pending"
REVOKED = "revoked"
REVOKE_FAILED = "revoke_failed"
STATES = (
    PENDING,
    ISSUING,
    RETRYING,
    ISSUED,
    FAILED,
    EXPIRED,
    REVOKE_PENDING,
    REVOKED,
    REVOKE_FAILED,
)
# Declared, not enforced: every move the code makes today (brief 1107).
# App/tests/test_sm_door_code_state.py pins each writer against this table.
TRANSITIONS = {
    PENDING: {
        ISSUING,  # issue: claim
        REVOKED,  # _handle_cancellations: stay cancelled before a code exists
    },
    RETRYING: {
        ISSUING,  # issue: claim
        REVOKED,  # _handle_cancellations: stay cancelled before a code exists
    },
    ISSUING: {
        PENDING,  # _release_issue_claim: not eligible, no account, bad window
        EXPIRED,  # issue: the stay window has already ended
        RETRYING,  # issue: gateway error or period taken; reconcile: lease expired
        ISSUED,  # issue: code created on the lock
        FAILED,  # issue: out of attempts or a permanent error
    },
    ISSUED: {
        REVOKE_PENDING,  # _handle_cancellations: stay cancelled before valid_to
        EXPIRED,  # reconcile: valid_to has passed
        PENDING,  # _reissue_lost_pin: a revoke deleted the lock code, the stay is live
    },
    REVOKE_PENDING: {
        ISSUED,  # _keep_issued: the stay is live again
        REVOKED,  # _revoke_one: code deleted from the lock
        REVOKE_FAILED,  # _revoke_one: no account, permanent error, or past valid_to
    },
    REVOKE_FAILED: {
        ISSUED,  # _keep_issued: the stay is live again
    },
    FAILED: set(),
    EXPIRED: set(),
    REVOKED: set(),
}

BACKOFF_MINUTES = (1, 5, 15, 60, 240)
# A failed code is handed to the host after this many tries (1 min apart).
ISSUE_MAX_ATTEMPTS = 2
PERIOD_TAKEN = "period_taken"
# A type-3 ``get`` for a period whose earlier code was never deleted returns
# that same code (TTLock support, 2026-10-12). Such a code is never reused.
PERIOD_SHARED = "period_shared"
PERIOD_TAKEN_RETRY_MINUTES = (1, 5)
PERIOD_TAKEN_MAX_ATTEMPTS = 4
GATEWAY_RETRY_KINDS = (
    "offline", "transient", "network", "rate", "budget", ttlock.CODE_MISSING, ttlock.LOCK_SETUP,
)
LEASE_MINUTES = 2
# 1155: a revived row whose delete may have run is checked on the lock before it is shown.
PIN_PRESENT, PIN_GONE, PIN_UNKNOWN = "present", "gone", "unknown"
LOOKUP_FAILED = "lookup_failed"
LOOKUP_MAX_TRIES = 3
# last_error values that leave a delete's result unknown: none (a crash after the claim),
# a timeout or non-JSON answer (network), a server fault (transient), or a lookup that failed
# (stored as lookup_failed:<n>; _delete_result_unknown reads it), or code_missing (-1007: the
# code is not on the lock, which an earlier delete that timed out may have caused, and the
# confirming lookup could not say).
AMBIGUOUS_DELETE_ERRORS = ("", "network", "transient", LOOKUP_FAILED, ttlock.CODE_MISSING)
# A guest who has finished registering must not wait longer than this in silence.
DELAY_MINUTES = 5
BATCH = 20

KEYPAD_CONFIRM_SUFFIX = "#"


def guest_pin_display(pin: str) -> str:
    """Digits guests type on the TTLock keypad, including the final # confirm."""
    pin = (pin or "").strip()
    if not pin or pin.endswith(KEYPAD_CONFIRM_SUFFIX):
        return pin
    return f"{pin}{KEYPAD_CONFIRM_SUFFIX}"


def _mail_idempotency_key(reservation_id: int, row: dict) -> str:
    code_id = row["provider_code_id"] or "none"
    return (
        f"door_code:{reservation_id}:{row['valid_from']}:{row['valid_to']}:{code_id}"
    )


def _release_issue_claim(
    door_code_id: int, *, decrement_attempt: bool = False, reason: Optional[str] = None
) -> None:
    """Put a row back to pending. ``reason`` is kept so a stuck code says why."""
    if decrement_attempt:
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, attempts = attempts - 1, "
            "last_error = COALESCE(?, last_error), updated_at = ? WHERE id = ? AND attempts > 0",
            (PENDING, reason, db.utcnow(), door_code_id),
        )
    else:
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, "
            "last_error = COALESCE(?, last_error), updated_at = ? WHERE id = ?",
            (PENDING, reason, db.utcnow(), door_code_id),
        )


def _waited_minutes(since_iso: Optional[str]) -> float:
    if not since_iso:
        return 0.0
    try:
        since = datetime.fromisoformat(since_iso)
    except ValueError:
        return 0.0
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - since).total_seconds() / 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _ms_to_iso(ms: int) -> str:
    return _iso(datetime.fromtimestamp(ms / 1000, tz=timezone.utc))


def _iso_to_ms(value: str) -> int:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _eligible_sql() -> Tuple[str, str]:
    today = deadlines.local_now().date().isoformat()
    sql = (
        "r.status = 'active' AND r.archived_at IS NULL "
        "AND r.registration_completed_at IS NOT NULL AND r.date_to >= ? "
        "AND a.lock_provider = 'ttlock' AND a.lock_id IS NOT NULL "
        "AND a.checkin_hour IS NOT NULL AND a.checkout_hour IS NOT NULL "
        # 0100: the setup guide's demo stay never opens a real door.
        "AND COALESCE(r.source, '') != 'demo'"
    )
    if not config.DOOR_CODES_LIVE:
        sql += " AND r.source = 'manual'"
    return sql, today


def _fmt_local(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(ZoneInfo(config.TIMEZONE))
    return local.strftime("%d.%m.%Y %H:%M")


def _stay_checkin_label(date_from: str, hour: int) -> str:
    day = datetime.fromisoformat(date_from).date()
    local = datetime(day.year, day.month, day.day, hour, 0, 0, tzinfo=ZoneInfo(config.TIMEZONE))
    return local.strftime("%d.%m.%Y %H:%M")


def view(reservation: dict, apartment: dict) -> Optional[dict]:
    """What the guest and host pages show. None when the property has no door codes."""
    if apartment["lock_provider"] != "ttlock" or reservation["source"] == "demo":
        return None
    if not config.DOOR_CODES_LIVE and reservation["source"] != "manual":
        return None
    row = db.query_one(
        "SELECT * FROM door_code WHERE reservation_id = ?",
        (reservation["id"],),
    )
    if not row:
        if reservation["registration_completed_at"]:
            if _waited_minutes(reservation["registration_completed_at"]) > DELAY_MINUTES:
                return {"state": "delayed"}
            return {"state": "preparing"}
        return {"state": "waiting"}
    state = row["state"]
    if state in (PENDING, ISSUING, RETRYING):
        if reservation["registration_completed_at"]:
            if _waited_minutes(reservation["registration_completed_at"]) > DELAY_MINUTES:
                return {"state": "delayed"}
            return {"state": "preparing"}
        return {"state": "waiting"}
    if state == FAILED:
        return {"state": "failed"}
    if state == EXPIRED:
        return None
    if state != ISSUED:
        return None
    pin = db.decrypt_field(row["pin_enc"])
    if not pin:
        return {"state": "preparing"}
    valid_from = row["valid_from"] or ""
    valid_to = row["valid_to"] or ""
    custom = (row["code_kind"] or "") == "custom"
    first_use = ""
    if valid_from and not custom:
        first_use = _fmt_local(_ms_to_iso(_iso_to_ms(valid_from) + 24 * 3_600_000))
    return {
        "state": "issued",
        "pin": guest_pin_display(pin),
        "works_from": _fmt_local(valid_from) if valid_from else "",
        "works_until": _fmt_local(valid_to) if valid_to else "",
        "checkin": _stay_checkin_label(reservation["date_from"], apartment["checkin_hour"]),
        "checkout": _stay_checkin_label(reservation["date_to"], apartment["checkout_hour"]),
        "first_use_by": first_use,
    }


def ensure_row(reservation_id: int) -> Optional[int]:
    clause, today = _eligible_sql()
    row = db.query_one(
        f"SELECT r.id, a.id AS apartment_id, a.lock_id, a.owner_user_id "
        f"FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE r.id = ? AND {clause}",
        (reservation_id, today),
    )
    if not row:
        return None
    if not ttlock.allowed_for(row["owner_user_id"]):
        return None
    account = ttlock.account_for(row["owner_user_id"])
    if not account or account["status"] != "ok":
        return None
    now = db.utcnow()
    db.execute(
        "INSERT INTO door_code (reservation_id, apartment_id, lock_id, code_kind, state, "
        "attempts, next_attempt_at, created_at, updated_at) "
        "VALUES (?, ?, ?, 'random', ?, 0, ?, ?, ?) "
        "ON CONFLICT (reservation_id) DO NOTHING",
        (reservation_id, row["apartment_id"], row["lock_id"], PENDING, now, now, now),
    )
    existing = db.query_one(
        "SELECT id FROM door_code WHERE reservation_id = ?",
        (reservation_id,),
    )
    return int(existing["id"]) if existing else None


def send_code_mail(door_code_id: int) -> None:
    try:
        _send_code_mail(door_code_id)
    except Exception:
        log.exception("door_code_mail_failed door_code=%s", door_code_id)


HOLD_CONFIRMATION_MINUTES = 5


def completion_door_code(reservation: dict, apartment: dict) -> Tuple[str, Optional[dict], Optional[dict]]:
    """What the registration confirmation does about the door code.

    ("hold", None, None): a code is still being made, wait for it.
    ("with", row, fields): the code exists and was not sent; put it in.
    ("without", None, None): no code is coming.
    """
    if not config.DOOR_CODES_ENABLED:
        return "without", None, None
    row = db.query_one("SELECT * FROM door_code WHERE reservation_id = ?", (reservation["id"],))
    if not row:
        return "without", None, None
    if row["state"] in (PENDING, ISSUING, RETRYING):
        return "hold", None, None
    if row["state"] == ISSUED and row["pin_enc"] and not row["notified_at"]:
        shown = view(reservation, apartment)
        if shown and shown.get("state") == "issued":
            return "with", row, {
                "checkin": shown["checkin"],
                "checkout": shown["checkout"],
                "first_use_by": shown["first_use_by"],
            }
    return "without", None, None


def _release_confirmation(reservation_id: int, *, force: bool = False) -> None:
    """Send a held registration confirmation (lazy import: claim imports us)."""
    from . import claim

    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    if not reservation:
        return
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (reservation["apartment_id"],))
    if apartment:
        claim.maybe_notify_completion(reservation, apartment, force=force)


def _release_held_confirmations() -> int:
    """Safety net: no confirmation waits longer than HOLD_CONFIRMATION_MINUTES."""
    now = _now()
    cutoff = _iso(now - timedelta(minutes=HOLD_CONFIRMATION_MINUTES))
    # Only stays this brief can have held: they have a door_code row and
    # registered in the last day. Older stays must never get a late confirmation.
    oldest = _iso(now - timedelta(hours=24))
    rows = db.query(
        "SELECT r.id FROM reservation r JOIN reservation_claim c ON c.reservation_id = r.id "
        "JOIN door_code dc ON dc.reservation_id = r.id "
        "WHERE c.state = 'claimed' AND c.email IS NOT NULL AND c.email <> '' "
        "AND c.completion_notified_at IS NULL AND r.status = 'active' "
        "AND r.registration_completed_at < ? AND r.registration_completed_at > ? LIMIT ?",
        (cutoff, oldest, BATCH),
    )
    for row in rows:
        log.error(
            "DOOR_CODE_PROBLEM stage=confirmation_without_code reservation=%s", row["id"]
        )
        _release_confirmation(int(row["id"]), force=True)
    return len(rows)


def _send_code_mail(door_code_id: int) -> None:
    row = db.query_one("SELECT * FROM door_code WHERE id = ?", (door_code_id,))
    if not row or row["state"] != ISSUED or row["notified_at"]:
        return
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (row["reservation_id"],))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (row["apartment_id"],))
    if not reservation or not apartment:
        return
    claim = db.query_one(
        "SELECT * FROM reservation_claim WHERE reservation_id = ?",
        (reservation["id"],),
    )
    if not claim or not (claim["email"] or "").strip():
        return
    if not claim["completion_notified_at"]:
        # The confirmation has not gone yet: the code travels inside it.
        _release_confirmation(int(reservation["id"]))
        again = db.query_one("SELECT notified_at FROM door_code WHERE id = ?", (door_code_id,))
        if again and again["notified_at"]:
            return
    shown = view(reservation, apartment)
    if not shown or shown.get("state") != "issued":
        return
    lang = claim["lang"] or "en"
    build = dict(
        lang=lang,
        property_name=apartment["internal_name"] or "",
        checkin=shown["checkin"],
        checkout=shown["checkout"],
        first_use_by=shown["first_use_by"],
    )
    # The fee block rides along only when the completion mail (the bill) has
    # gone and the group is still whole: a partial group is not billed. Any
    # failure drops the fee block, never the code mail.
    content = None
    try:
        if claim["completion_notified_at"]:
            from . import claim as claim_module  # `claim` is the row here; the modules import each other
            from . import reporting

            progress = reporting.reservation_progress(reservation)
            expected = progress["expected"]
            if expected is not None and progress["filled"] >= expected:
                fee = claim_module._completion_fee(apartment, reservation)
                if fee:
                    content = mail_notify.build_door_code(**build, fee=fee)
    except Exception:
        log.exception("door code %s: fee block dropped from the code mail", door_code_id)
        content = None
    if content is None:
        content = mail_notify.build_door_code(**build)
    payload = mail_notify.guest_payload(apartment, content, lang)
    if content.get("qr_spayd"):
        payload[mail.QR_SPAYD_KEY] = content["qr_spayd"]
    payload[mail.DOOR_CODE_KEY] = row["pin_enc"]
    outbox_id = mail.enqueue(
        kind="door_code",
        idempotency_key=_mail_idempotency_key(int(reservation["id"]), row),
        to_email=claim["email"],
        cc_email=payload.get("reply_to", ""),
        subject=content["subject"],
        payload=payload,
        reservation_id=reservation["id"],
        apartment_id=apartment["id"],
        owner_user_id=apartment["owner_user_id"],
    )
    if outbox_id is None:
        return
    db.execute(
        "UPDATE door_code SET notified_at = ?, updated_at = ? WHERE id = ?",
        (db.utcnow(), db.utcnow(), door_code_id),
    )
    mail.drain(limit=4)


def _period_code_held_by_other(
    lock_id: str,
    code_id: str,
    start_ms: int,
    end_ms: int,
    door_code_id: int,
) -> bool:
    """True when another stay already stores this TTLock period code.

    Type-3 ``get`` for a period whose earlier code was never deleted returns
    that same code (TTLock support, 2026-10-12). The new stay must not adopt it.
    """
    return bool(
        db.query_one(
            "SELECT id FROM door_code WHERE lock_id = ? AND provider_code_id = ? "
            "AND valid_from = ? AND valid_to = ? AND id != ?",
            (lock_id, str(code_id), _ms_to_iso(start_ms), _ms_to_iso(end_ms), door_code_id),
        )
    )


def _create_random(
    account_id: int,
    lock_id: str,
    start_ms: int,
    end_ms: int,
    name: str,
    priority: str,
    door_code_id: int,
) -> Tuple[str, str]:
    pin, code_id = ttlock.create_period_code(account_id, lock_id, start_ms, end_ms, name, priority)
    if _period_code_held_by_other(lock_id, code_id, start_ms, end_ms, door_code_id):
        raise ttlock.TTLockError("period already has an undeleted code", kind=PERIOD_SHARED)
    return pin, code_id


def issue(door_code_id: int, *, allow_gateway: bool = False) -> bool:
    now = _now()
    now_iso = _iso(now)
    lease_cutoff = _iso(now - timedelta(minutes=LEASE_MINUTES))
    claimed = db.execute(
        "UPDATE door_code SET state = ?, claimed_at = ?, attempts = attempts + 1, updated_at = ? "
        "WHERE id = ? AND state IN (?, ?) AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
        "AND (claimed_at IS NULL OR claimed_at < ?)",
        (ISSUING, now_iso, now_iso, door_code_id, PENDING, RETRYING, now_iso, lease_cutoff),
    )
    if claimed != 1:
        return False

    row = db.query_one("SELECT * FROM door_code WHERE id = ?", (door_code_id,))
    if not row:
        return False
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (row["reservation_id"],))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (row["apartment_id"],))
    if not reservation or not apartment:
        return False

    clause, today = _eligible_sql()
    still = db.query_one(
        f"SELECT 1 AS ok FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE r.id = ? AND {clause}",
        (reservation["id"], today),
    )
    if not still or not ttlock.allowed_for(apartment["owner_user_id"]):
        _release_issue_claim(door_code_id, decrement_attempt=True, reason="not_eligible")
        return False

    account = ttlock.account_for(apartment["owner_user_id"])
    if not account or account["status"] != "ok":
        _release_issue_claim(door_code_id, decrement_attempt=True, reason="no_account")
        return False

    try:
        start_ms, end_ms = ttlock.stay_window(
            reservation["date_from"],
            reservation["date_to"],
            apartment["checkin_hour"],
            apartment["checkout_hour"],
            config.DOOR_CODE_BUFFER_HOURS,
        )
    except ValueError:
        _release_issue_claim(door_code_id, decrement_attempt=True, reason="bad_window")
        return False

    if end_ms < int(now.timestamp() * 1000):
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, attempts = attempts - 1, "
            "updated_at = ? WHERE id = ? AND attempts > 0",
            (EXPIRED, db.utcnow(), door_code_id),
        )
        return False

    name = f"UH-{door_code_id}"
    priority = (
        ttlock.CRITICAL
        if start_ms < int((now + timedelta(hours=24)).timestamp() * 1000)
        else ttlock.NORMAL
    )
    attempts = int(row["attempts"])
    taken = (row["last_error"] or "").startswith(PERIOD_TAKEN)
    via_add = False
    kind = "random"

    try:
        pin: Optional[str] = None
        code_id: Optional[str] = None
        if attempts > 1:
            found = ttlock.find_code_by_name(
                int(account["id"]), row["lock_id"], name, start_ms, end_ms
            )
            if found:
                found_pin, found_id = found
                if _period_code_held_by_other(
                    row["lock_id"], found_id, start_ms, end_ms, door_code_id
                ):
                    # ``get`` names the returned period code UH-<id>. A retry
                    # then finds it by that name and would hand the cancelled
                    # stay's PIN to the new guest. Skip it; the custom-code
                    # path below issues a code of this stay's own.
                    log.error(
                        "DOOR_CODE_PROBLEM stage=%s reservation=%s door_code=%s",
                        PERIOD_SHARED,
                        reservation["id"],
                        door_code_id,
                    )
                    mail_notify.door_code_notice(door_code_id, PERIOD_SHARED)
                    mail.drain(limit=4)
                    if not taken:
                        taken = True
                        db.execute(
                            "UPDATE door_code SET last_error = ? WHERE id = ?",
                            ("period_taken:shared", door_code_id),
                        )
                else:
                    pin, code_id = found_pin, found_id
                    kind = "custom" if taken else "random"
        if pin is None:
            if taken and allow_gateway:
                via_add = True
                pin, code_id = ttlock.add_custom_code(
                    int(account["id"]),
                    row["lock_id"],
                    start_ms,
                    end_ms,
                    name,
                    priority,
                )
                kind = "custom"
            elif taken:
                _release_issue_claim(door_code_id, decrement_attempt=True)
                return False
            else:
                try:
                    pin, code_id = _create_random(
                        int(account["id"]),
                        row["lock_id"],
                        start_ms,
                        end_ms,
                        name,
                        priority,
                        door_code_id,
                    )
                    kind = "random"
                except ttlock.TTLockError as create_exc:
                    if create_exc.kind not in (PERIOD_TAKEN, PERIOD_SHARED):
                        raise
                    log.error(
                        "DOOR_CODE_PROBLEM stage=%s reservation=%s door_code=%s",
                        create_exc.kind,
                        reservation["id"],
                        door_code_id,
                    )
                    mail_notify.door_code_notice(door_code_id, create_exc.kind)
                    mail.drain(limit=4)
                    if allow_gateway:
                        via_add = True
                        pin, code_id = ttlock.add_custom_code(
                            int(account["id"]),
                            row["lock_id"],
                            start_ms,
                            end_ms,
                            name,
                            priority,
                        )
                        kind = "custom"
                    else:
                        db.execute(
                            "UPDATE door_code SET state = ?, claimed_at = NULL, "
                            "last_error = ?, next_attempt_at = ?, updated_at = ? WHERE id = ?",
                            (
                                RETRYING,
                                "period_taken:-1026"
                                if create_exc.kind == PERIOD_TAKEN
                                else "period_taken:shared",
                                now_iso,
                                now_iso,
                                door_code_id,
                            ),
                        )
                        return False
        with db.cursor():
            db.execute(
                "UPDATE door_code SET state = ?, pin_enc = ?, provider_code_id = ?, "
                "code_kind = ?, valid_from = ?, valid_to = ?, issued_at = ?, claimed_at = NULL, "
                "last_error = NULL, updated_at = ? WHERE id = ?",
                (
                    ISSUED,
                    db.encrypt_field(pin),
                    code_id,
                    kind,
                    _ms_to_iso(start_ms),
                    _ms_to_iso(end_ms),
                    now_iso,
                    now_iso,
                    door_code_id,
                ),
            )
        alerts.resolve(f"door_code_failed:{reservation['id']}")
        alerts.resolve(f"door_code_delayed:{reservation['id']}")
        db.audit(
            "door_code_issued",
            f"door_code={door_code_id} reservation={reservation['id']}",
            actor="system",
            owner_user_id=apartment["owner_user_id"],
        )
        fresh = db.query_one("SELECT status, archived_at FROM reservation WHERE id = ?", (reservation["id"],))
        if fresh and fresh["status"] == "active" and fresh["archived_at"] is None:
            send_code_mail(door_code_id)
        return True
    except ttlock.TTLockError as exc:
        kind_err = (exc.kind or "transient")[:40]
        reason = f"{kind_err}:{exc.code}" if exc.code is not None else kind_err
        if taken or via_add:
            last_err = ("period_taken:" + reason)[:40]
            if exc.code == -2012:
                new_state = FAILED
                next_at = None
            elif kind_err in ("permission", "reauth", "config", "disabled", "storage", "duplicate"):
                new_state = FAILED
                next_at = None
            elif kind_err == "budget":
                new_state = RETRYING
                next_at = _iso(now + timedelta(minutes=60))
                db.execute(
                    "UPDATE door_code SET attempts = attempts - 1 WHERE id = ?",
                    (door_code_id,),
                )
            elif attempts >= PERIOD_TAKEN_MAX_ATTEMPTS:
                new_state = FAILED
                next_at = None
            else:
                new_state = RETRYING
                idx = min(max(attempts - 2, 0), 1)
                next_at = _iso(now + timedelta(minutes=PERIOD_TAKEN_RETRY_MINUTES[idx]))
            db.execute(
                "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, "
                "next_attempt_at = ?, updated_at = ? WHERE id = ?",
                (new_state, last_err, next_at, now_iso, door_code_id),
            )
            log.error(
                "DOOR_CODE_PROBLEM stage=%s reservation=%s door_code=%s attempt=%s reason=%s",
                "handed_over" if new_state == FAILED else "attempt_failed",
                reservation["id"],
                door_code_id,
                attempts,
                last_err,
            )
            if new_state == FAILED:
                alerts.raise_alert(
                    "warning",
                    "door_code_failed",
                    "Door code could not be created",
                    dedupe_key=f"door_code_failed:{reservation['id']}",
                    apartment_id=apartment["id"],
                    reservation_id=reservation["id"],
                    params={"property": apartment["internal_name"], "date": reservation["date_from"]},
                )
                mail_notify.door_code_notice(door_code_id, "failed")
                _release_confirmation(int(reservation["id"]))
                mail.drain(limit=4)
            return False
        kind = kind_err
        if exc.kind in ("reauth", "permission", "config", "disabled"):
            new_state = FAILED
            next_at = None
        elif exc.kind == "budget":
            new_state = RETRYING
            next_at = _iso(now + timedelta(minutes=60))
            db.execute(
                "UPDATE door_code SET attempts = attempts - 1 WHERE id = ?",
                (door_code_id,),
            )
        elif attempts >= ISSUE_MAX_ATTEMPTS:
            new_state = FAILED
            next_at = None
        else:
            new_state = RETRYING
            next_at = _iso(now + timedelta(minutes=BACKOFF_MINUTES[attempts - 1]))
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, "
            "next_attempt_at = ?, updated_at = ? WHERE id = ?",
            (new_state, reason[:40], next_at, now_iso, door_code_id),
        )
        log.error(
            "DOOR_CODE_PROBLEM stage=%s reservation=%s door_code=%s attempt=%s reason=%s",
            "handed_over" if new_state == FAILED else "attempt_failed",
            reservation["id"], door_code_id, attempts, reason,
        )
        if new_state == FAILED:
            alerts.raise_alert(
                "warning",
                "door_code_failed",
                "Door code could not be created",
                dedupe_key=f"door_code_failed:{reservation['id']}",
                apartment_id=apartment["id"],
                reservation_id=reservation["id"],
                params={"property": apartment["internal_name"], "date": reservation["date_from"]},
            )
            mail_notify.door_code_notice(door_code_id, "failed")
            _release_confirmation(int(reservation["id"]))
            mail.drain(limit=4)
        return False
    except Exception:
        log.exception("door_code_issue_failed door_code=%s", door_code_id)
        if attempts >= ISSUE_MAX_ATTEMPTS:
            new_state = FAILED
            next_at = None
        else:
            new_state = RETRYING
            next_at = _iso(now + timedelta(minutes=BACKOFF_MINUTES[attempts - 1]))
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, "
            "next_attempt_at = ?, updated_at = ? WHERE id = ?",
            (new_state, "transient", next_at, now_iso, door_code_id),
        )
        log.error(
            "DOOR_CODE_PROBLEM stage=%s reservation=%s door_code=%s attempt=%s reason=%s",
            "handed_over" if new_state == FAILED else "attempt_failed",
            reservation["id"], door_code_id, attempts, "transient",
        )
        if new_state == FAILED:
            alerts.raise_alert(
                "warning",
                "door_code_failed",
                "Door code could not be created",
                dedupe_key=f"door_code_failed:{reservation['id']}",
                apartment_id=apartment["id"],
                reservation_id=reservation["id"],
                params={"property": apartment["internal_name"], "date": reservation["date_from"]},
            )
            mail_notify.door_code_notice(door_code_id, "failed")
            _release_confirmation(int(reservation["id"]))
            mail.drain(limit=4)
        return False


def _stay_is_live(reservation) -> bool:
    return bool(
        reservation
        and reservation["status"] == "active"
        and reservation["archived_at"] is None
    )


def _keep_issued(row_id: int, now_iso: str, held_claim: str | None = None) -> bool:
    """The stay is back; leave the PIN on the lock and show it again. True if a row changed."""
    # Guarded: _revoke_one may have deleted the lock code and set revoked since the caller read
    # the row, and it may hold the revoke lease right now (claimed_at inside LEASE_MINUTES).
    # _revoke_one passes its own claim stamp as held_claim; the revived loop passes none and
    # so skips a leased row. Zero rows updated leaves the row as it is.
    cutoff = _iso(_now() - timedelta(minutes=LEASE_MINUTES))
    return db.execute(
        "UPDATE door_code SET state = ?, claimed_at = NULL, attempts = 0, "
        "next_attempt_at = NULL, last_error = NULL, updated_at = ? "
        "WHERE id = ? AND state IN (?, ?) "
        "AND (claimed_at IS NULL OR claimed_at < ? OR claimed_at = ?)",
        (ISSUED, now_iso, row_id, REVOKE_FAILED, REVOKE_PENDING, cutoff, held_claim),
    ) == 1


def _lock_code_state(row, owner_user_id: int) -> str:
    """Ask the lock whether the row's PIN still exists (1 to LIST_MAX_PAGES list calls).

    PIN_GONE only when the lock's whole answer was read and the row's code id is not in it.
    PIN_UNKNOWN when the answer cannot be had or is incomplete (no account, no code id,
    TTLock error, more pages than the page limit): nothing is assumed either way. The code
    id decides, not the name or the window: UH-7 also matches UH-70 on the lock.
    """
    account = ttlock.account_for(owner_user_id)
    if not account or account["status"] != "ok" or not row["provider_code_id"]:
        return PIN_UNKNOWN
    try:
        listed = ttlock.code_is_listed(
            int(account["id"]),
            row["lock_id"],
            f"UH-{row['id']}",
            row["provider_code_id"],
        )
    except ttlock.TTLockError:
        return PIN_UNKNOWN
    if listed is None:
        return PIN_UNKNOWN
    return PIN_PRESENT if listed else PIN_GONE


def _delete_result_unknown(last_error) -> bool:
    """True when last_error leaves a delete's result open (see AMBIGUOUS_DELETE_ERRORS)."""
    text = last_error or ""
    return text in AMBIGUOUS_DELETE_ERRORS or text.startswith(LOOKUP_FAILED)


def _note_failed_lookup(row_id: int, claim: str, claimed: bool) -> int:
    """Count a failed lookup in last_error ("lookup_failed:<n>"); return n.

    attempts is the delete counter and is not a lookup counter: it is not raised here, and
    the add of 1 that _revoke_one made when it claimed the row (claimed=True) is taken back,
    so lookups never move the delete retry delays or the attempts == 3 mail.
    """
    row = db.query_one("SELECT last_error FROM door_code WHERE id = ?", (row_id,))
    previous = (row["last_error"] or "") if row else ""
    count = 1
    if previous.startswith(LOOKUP_FAILED + ":"):
        try:
            count = int(previous.split(":", 1)[1]) + 1
        except ValueError:
            count = 1
    db.execute(
        "UPDATE door_code SET attempts = attempts - ?, last_error = ?, updated_at = ? "
        "WHERE id = ? AND claimed_at = ?",
        (1 if claimed else 0, f"{LOOKUP_FAILED}:{count}", claim, row_id, claim),
    )
    return count


def _revive_one(item, now_iso: str, held_claim: str | None = None) -> bool:
    """The stay is back: show the PIN again, but first confirm it still exists.

    Only a row whose delete may have run (attempts above the claim made by _revoke_one,
    and last_error in AMBIGUOUS_DELETE_ERRORS: a refusal by the lock or API is definite)
    costs one lock call.
    Gone: the row is kept, then _reissue_lost_pin makes a new code. Unknown: the row stays
    revoke_pending (the guest page shows no PIN) and its lease claimed_at delays the next
    try by LEASE_MINUTES; after LOOKUP_MAX_TRIES failures it is kept as before 1155 and
    audited door_code_pin_unverified, so a lasting TTLock error cannot hide the PIN.
    True if the row is issued again.
    """
    row_id = int(item["id"])
    attempted = (
        int(item["attempts"] or 0) > (1 if held_claim else 0)
        and _delete_result_unknown(item["last_error"])
    )
    if not attempted:
        return _keep_issued(row_id, now_iso, held_claim=held_claim)
    claim = held_claim
    if claim is None:
        claim = _iso(_now())
        cutoff = _iso(_now() - timedelta(minutes=LEASE_MINUTES))
        if db.execute(
            "UPDATE door_code SET claimed_at = ?, updated_at = ? WHERE id = ? AND state IN (?, ?) "
            "AND (claimed_at IS NULL OR claimed_at < ?)",
            (claim, now_iso, row_id, REVOKE_PENDING, REVOKE_FAILED, cutoff),
        ) != 1:
            return False
    apartment = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (item["apartment_id"],))
    owner_id = int(apartment["owner_user_id"]) if apartment else 0
    verdict = _lock_code_state(item, owner_id)
    unverified = False
    if verdict == PIN_UNKNOWN:
        if _note_failed_lookup(row_id, claim, held_claim is not None) < LOOKUP_MAX_TRIES:
            return False
        unverified = True
    if not _keep_issued(row_id, now_iso, held_claim=claim):
        return False
    if unverified:
        db.audit("door_code_pin_unverified", f"door_code={row_id}", actor="system", owner_user_id=owner_id)
        _tell_host_unverified(row_id, owner_id)
    elif verdict == PIN_GONE:
        _reissue_lost_pin(row_id, str(item["provider_code_id"] or ""), owner_id)
    return True


def _already_gone(exc: "ttlock.TTLockError", row, owner_user_id: int) -> bool:
    """A refused delete that may only mean "that code no longer exists".

    TTLock answers a delete of a missing code with -1007 (kind code_missing) or with an
    errcode this repo does not map. Only those two, never a network error or any other
    mapped errcode (offline, permission, config, ...), cost one list call; the code counts
    as deleted only when the lock confirms it is gone.
    """
    mapped = ttlock.ERROR_KINDS.get(exc.code)
    if exc.code is None or mapped not in (None, ttlock.CODE_MISSING):
        return False
    return _lock_code_state(row, owner_user_id) == PIN_GONE


def _tell_host_reissued(row_id: int, owner_user_id: int) -> None:
    """Tell the host once that a lost door code was replaced: one info card, one mail.

    Called only after issue() made the new code. The wording says how the guest gets it:
    by e-mail when the stay has a guest address, else on the stay page (kind and variant
    end in _no_email). The card key is per stay and wording, so a second re-issue refreshes
    the open card; the mail key is per row and variant, so it goes out once. Neither
    carries the PIN. A failure here is logged and never stops the re-issue.
    """
    try:
        info = db.query_one(
            "SELECT a.id AS apartment_id, a.internal_name, r.id AS reservation_id, r.date_from, "
            "c.email AS guest_email FROM door_code dc JOIN apartment a ON a.id = dc.apartment_id "
            "JOIN reservation r ON r.id = dc.reservation_id "
            "LEFT JOIN reservation_claim c ON c.reservation_id = r.id WHERE dc.id = ?",
            (row_id,),
        )
        if not info:
            return
        suffix = "" if (info["guest_email"] or "").strip() else "_no_email"
        alerts.raise_alert(
            "info",
            f"door_code_reissued{suffix}",
            "Door code was replaced",
            dedupe_key=f"door_code_reissued{suffix}:{info['reservation_id']}",
            apartment_id=info["apartment_id"],
            reservation_id=info["reservation_id"],
            owner_user_id=owner_user_id,
            params={"property": info["internal_name"], "date": info["date_from"]},
        )
        mail_notify.door_code_notice(row_id, f"reissued{suffix}")
    except Exception:
        log.exception("door code %s: host notice after a re-issue failed", row_id)


def _tell_host_unverified(row_id: int, owner_user_id: int) -> None:
    """Tell the host once that a revived code could not be confirmed on the lock.

    Called when the lookup stayed unknown for LOOKUP_MAX_TRIES and the row is kept issued: the
    guest may be shown a PIN the lock no longer has. One warning card per stay (dedupe key) and
    one mail per row (idempotency key in the mail queue); neither carries the PIN. A failure
    here is logged and never stops the revival.
    """
    try:
        info = db.query_one(
            "SELECT a.id AS apartment_id, a.internal_name, r.id AS reservation_id, r.date_from "
            "FROM door_code dc JOIN apartment a ON a.id = dc.apartment_id "
            "JOIN reservation r ON r.id = dc.reservation_id WHERE dc.id = ?",
            (row_id,),
        )
        if not info:
            return
        alerts.raise_alert(
            "warning",
            "door_code_pin_unverified",
            "Door code could not be confirmed on the lock",
            dedupe_key=f"door_code_pin_unverified:{info['reservation_id']}",
            apartment_id=info["apartment_id"],
            reservation_id=info["reservation_id"],
            owner_user_id=owner_user_id,
            params={"property": info["internal_name"], "date": info["date_from"]},
        )
        mail_notify.door_code_notice(row_id, "pin_unverified")
    except Exception:
        log.exception("door code %s: host notice about an unverified code failed", row_id)


def _reissue_lost_pin(row_id: int, deleted_code_id: str, owner_user_id: int) -> None:
    """A revoke deleted the lock code but lost the row to a revival: make a new code.

    One guarded UPDATE decides, so nothing is re-issued unless the row is still issued
    with the code id that was just deleted (a date move already made a new code: the id
    differs) and the stay is live (a cancelled stay is left to the next revoke). The
    row goes issued -> pending and issue() runs at once, so a success leaves no pending
    row for _alert_delayed; only then is the host told (_tell_host_reissued). A failure is
    handled by issue() and the retry loop: their host alerts and mails are reused, and a
    code that a later retry makes sends no re-issue notice.
    """
    now_iso = _iso(_now())
    if db.execute(
        "UPDATE door_code SET state = ?, pin_enc = NULL, provider_code_id = NULL, "
        "issued_at = NULL, notified_at = NULL, claimed_at = NULL, attempts = 0, "
        "next_attempt_at = NULL, last_error = ?, updated_at = ? "
        "WHERE id = ? AND state = ? AND provider_code_id = ? "
        "AND EXISTS (SELECT 1 FROM reservation r WHERE r.id = door_code.reservation_id "
        "AND r.status = 'active' AND r.archived_at IS NULL)",
        (PENDING, "pin_lost", now_iso, row_id, ISSUED, deleted_code_id),
    ) != 1:
        return
    db.audit(
        "door_code_pin_reissued",
        f"door_code={row_id}",
        actor="system",
        owner_user_id=owner_user_id,
    )
    try:
        issued = issue(row_id, allow_gateway=True)
    except Exception:
        log.exception("door code %s: re-issue after a lost revoke failed", row_id)
        return
    if issued:
        _tell_host_reissued(row_id, owner_user_id)


def _revoke_one(row_id: int) -> None:
    now = _now()
    now_iso = _iso(now)
    lease_cutoff = _iso(now - timedelta(minutes=LEASE_MINUTES))
    claimed = db.execute(
        "UPDATE door_code SET claimed_at = ?, attempts = attempts + 1, updated_at = ? "
        "WHERE id = ? AND state = ? AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
        "AND (claimed_at IS NULL OR claimed_at < ?)",
        (now_iso, now_iso, row_id, REVOKE_PENDING, now_iso, lease_cutoff),
    )
    if claimed != 1:
        return
    row = db.query_one("SELECT * FROM door_code WHERE id = ?", (row_id,))
    if not row:
        return
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (row["apartment_id"],))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (row["reservation_id"],))
    if not apartment or not reservation:
        return
    if _stay_is_live(reservation):
        _revive_one(row, now_iso, held_claim=now_iso)
        return
    account = ttlock.account_for(apartment["owner_user_id"])
    if not account or account["status"] != "ok":
        if db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
            "WHERE id = ? AND state = ?",
            (REVOKE_FAILED, "no_account", now_iso, row_id, REVOKE_PENDING),
        ) == 1:
            mail_notify.door_code_notice(row_id, "cancelled_not_deleted")
        return
    attempts = int(row["attempts"])
    via = ""
    try:
        try:
            ttlock.delete_code(
                int(account["id"]),
                row["lock_id"],
                row["provider_code_id"] or "",
            )
        except ttlock.TTLockError as exc:
            if not _already_gone(exc, row, apartment["owner_user_id"]):
                raise
            via = f" via=gone:{exc.code}"
            log.warning("DOOR_CODE_PROBLEM stage=delete_gone door_code=%s errcode=%s", row_id, exc.code)
        if db.execute(
            "UPDATE door_code SET state = ?, revoked_at = ?, pin_enc = NULL, claimed_at = NULL, "
            "updated_at = ? WHERE id = ? AND state = ?",
            (REVOKED, now_iso, now_iso, row_id, REVOKE_PENDING),
        ) != 1:
            # The lock code is gone but the row moved on (the stay came back during the
            # delete). No audit "revoked", no mail; leave the state and flag it.
            db.audit(
                "door_code_revoke_lost_race",
                f"door_code={row_id}",
                actor="system",
                owner_user_id=apartment["owner_user_id"],
            )
            _reissue_lost_pin(row_id, str(row["provider_code_id"] or ""), apartment["owner_user_id"])
            return
        db.audit(
            "door_code_revoked",
            f"door_code={row_id}{via}",
            actor="system",
            owner_user_id=apartment["owner_user_id"],
        )
        mail_notify.door_code_notice(row_id, "cancelled_deleted")
    except ttlock.TTLockError as exc:
        kind = exc.kind or "transient"
        # Every code, random or custom, is retried until its end: an undeleted
        # code is handed again to the next stay with the same hours.
        if kind in GATEWAY_RETRY_KINDS:
            past_end = bool(
                row["valid_to"]
                and _iso_to_ms(row["valid_to"]) <= int(now.timestamp() * 1000)
            )
            if past_end:
                if db.execute(
                    "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
                    "WHERE id = ? AND state = ?",
                    (REVOKE_FAILED, kind[:40], now_iso, row_id, REVOKE_PENDING),
                ) == 1:
                    db.audit(
                        "door_code_revoke_failed",
                        f"door_code={row_id}",
                        actor="system",
                        owner_user_id=apartment["owner_user_id"],
                    )
            else:
                delays = (1, 15, 60)
                next_at = _iso(now + timedelta(minutes=delays[min(attempts - 1, 2)]))
                if db.execute(
                    "UPDATE door_code SET claimed_at = NULL, next_attempt_at = ?, last_error = ?, "
                    "updated_at = ? WHERE id = ? AND state = ?",
                    (next_at, kind[:40], now_iso, row_id, REVOKE_PENDING),
                ) == 1 and attempts == 3:
                    mail_notify.door_code_notice(row_id, "cancelled_not_deleted")
        else:
            if db.execute(
                "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
                "WHERE id = ? AND state = ?",
                (REVOKE_FAILED, kind[:40], now_iso, row_id, REVOKE_PENDING),
            ) == 1:
                db.audit(
                    "door_code_revoke_failed",
                    f"door_code={row_id}",
                    actor="system",
                    owner_user_id=apartment["owner_user_id"],
                )
                mail_notify.door_code_notice(row_id, "cancelled_not_deleted")


def _handle_cancellations(now_iso: str) -> None:
    rows = db.query(
        "SELECT dc.* FROM door_code dc "
        "JOIN reservation r ON r.id = dc.reservation_id "
        "WHERE (r.status != 'active' OR r.archived_at IS NOT NULL)"
    )
    for row in rows:
        state = row["state"]
        if state in (PENDING, RETRYING):
            # Guarded: issue() may have claimed the row since the SELECT. Zero
            # rows updated leaves it to issue(); the next run sees its new state.
            db.execute(
                "UPDATE door_code SET state = ?, claimed_at = NULL, updated_at = ? "
                "WHERE id = ? AND state IN (?, ?)",
                (REVOKED, now_iso, row["id"], PENDING, RETRYING),
            )
        elif state == ISSUED and row["valid_to"]:
            end_ms = _iso_to_ms(row["valid_to"])
            if end_ms > int(_now().timestamp() * 1000):
                db.execute(
                    "UPDATE door_code SET state = ?, attempts = 0, next_attempt_at = ?, "
                    "claimed_at = NULL, last_error = NULL, updated_at = ? WHERE id = ? AND state = ?",
                    (REVOKE_PENDING, now_iso, now_iso, row["id"], ISSUED),
                )

    # A calendar revival or archive undo can bring the stay back while a
    # delete is still queued. 0038 keeps retrying custom-code deletes until
    # valid_to, so without this abort the guest's working PIN is removed
    # hours later. Restore before the due query so the stay page shows it.
    revived = db.query(
        "SELECT dc.* FROM door_code dc "
        "JOIN reservation r ON r.id = dc.reservation_id "
        "WHERE dc.state IN (?, ?) AND r.status = 'active' AND r.archived_at IS NULL "
        "AND dc.pin_enc IS NOT NULL",
        (REVOKE_PENDING, REVOKE_FAILED),
    )
    for item in revived:
        if _revive_one(item, now_iso):
            db.audit("door_code_revoke_aborted", f"door_code={item['id']}", actor="system")

    due = db.query(
        "SELECT dc.id FROM door_code dc "
        "JOIN reservation r ON r.id = dc.reservation_id "
        "WHERE dc.state = ? AND (r.status != 'active' OR r.archived_at IS NOT NULL) "
        "AND (dc.next_attempt_at IS NULL OR dc.next_attempt_at <= ?) "
        "ORDER BY dc.next_attempt_at LIMIT ?",
        (REVOKE_PENDING, now_iso, BATCH),
    )
    for item in due:
        _revoke_one(int(item["id"]))

    reactivated = db.query(
        "SELECT dc.id FROM door_code dc "
        "JOIN reservation r ON r.id = dc.reservation_id "
        "WHERE dc.state = ? AND r.status = 'active' AND r.archived_at IS NULL",
        (REVOKED,),
    )
    for item in reactivated:
        # Guarded: only a row that is still revoked is reset; one that moved on is left.
        removed = db.execute(
            "DELETE FROM door_code WHERE id = ? AND state = ?", (item["id"], REVOKED)
        )
        if removed:
            db.audit("door_code_reset", f"door_code={item['id']}", actor="system")


def _handle_moves(now_iso: str) -> None:
    rows = db.query(
        "SELECT dc.*, r.date_from, r.date_to, a.checkin_hour, a.checkout_hour, a.owner_user_id "
        "FROM door_code dc "
        "JOIN reservation r ON r.id = dc.reservation_id "
        "JOIN apartment a ON a.id = dc.apartment_id "
        "WHERE dc.state = ? AND r.status = 'active' AND r.archived_at IS NULL",
        (ISSUED,),
    )
    now_ms = int(_now().timestamp() * 1000)
    for row in rows:
        if row["next_attempt_at"] and row["next_attempt_at"] > now_iso:
            continue
        try:
            start_ms, end_ms = ttlock.stay_window(
                row["date_from"],
                row["date_to"],
                row["checkin_hour"],
                row["checkout_hour"],
                config.DOOR_CODE_BUFFER_HOURS,
            )
        except ValueError:
            continue
        if end_ms < now_ms:
            continue
        if row["valid_from"] and row["valid_to"]:
            if _iso_to_ms(row["valid_from"]) == start_ms and _iso_to_ms(row["valid_to"]) == end_ms:
                if (row["last_error"] or "").startswith(("lock_setup", "config")):
                    # The stay is back on the code's own window: an old move failure is stale.
                    db.execute(
                        "UPDATE door_code SET last_error = NULL, next_attempt_at = NULL, "
                        "updated_at = ? WHERE id = ? AND state = ?",
                        (now_iso, row["id"], ISSUED),
                    )
                continue
        if (row["valid_from"] and _iso_to_ms(row["valid_from"]) <= now_ms) or start_ms <= now_ms:
            mail_notify.door_code_notice(int(row["id"]), "moved_during_stay")
            continue
        # Brief 0037: a move that failed with permission (etc.) is not retried after
        # the host fixes TTLock access; the guest keeps the old code until then.
        last_err = (row["last_error"] or "")
        if last_err.startswith(("permission", "reauth", "config", "disabled")):
            continue
        account = ttlock.account_for(row["owner_user_id"])
        if not account or account["status"] != "ok":
            continue
        name = f"UH-{row['id']}"
        move_now = _now()
        priority = (
            ttlock.CRITICAL
            if start_ms < int((move_now + timedelta(hours=24)).timestamp() * 1000)
            else ttlock.NORMAL
        )
        old_code_id = row["provider_code_id"] or ""
        via_add = False
        try:
            try:
                pin, code_id = _create_random(
                    int(account["id"]),
                    row["lock_id"],
                    start_ms,
                    end_ms,
                    name,
                    priority,
                    int(row["id"]),
                )
                code_kind = "random"
            except ttlock.TTLockError as create_exc:
                if create_exc.kind not in (PERIOD_TAKEN, PERIOD_SHARED):
                    raise
                mail_notify.door_code_notice(int(row["id"]), create_exc.kind)
                mail.drain(limit=4)
                via_add = True
                pin, code_id = ttlock.add_custom_code(
                    int(account["id"]),
                    row["lock_id"],
                    start_ms,
                    end_ms,
                    name,
                    priority,
                )
                code_kind = "custom"
            db.execute(
                "UPDATE door_code SET pin_enc = ?, provider_code_id = ?, code_kind = ?, "
                "valid_from = ?, valid_to = ?, notified_at = NULL, next_attempt_at = NULL, "
                "last_error = NULL, updated_at = ? WHERE id = ?",
                (
                    db.encrypt_field(pin),
                    code_id,
                    code_kind,
                    _ms_to_iso(start_ms),
                    _ms_to_iso(end_ms),
                    now_iso,
                    row["id"],
                ),
            )
            db.audit(
                "door_code_replaced",
                f"door_code={row['id']}",
                actor="system",
                owner_user_id=row["owner_user_id"],
            )
            send_code_mail(int(row["id"]))
            if old_code_id and old_code_id != code_id:
                try:
                    ttlock.delete_code(
                        int(account["id"]),
                        row["lock_id"],
                        old_code_id,
                    )
                except ttlock.TTLockError:
                    db.audit(
                        "door_code_move_old_not_deleted",
                        f"door_code={row['id']}",
                        actor="system",
                        owner_user_id=row["owner_user_id"],
                    )
                    mail_notify.door_code_notice(int(row["id"]), "moved_not_deleted")
                    mail.drain(limit=4)
        except ttlock.TTLockError as exc:
            kind = exc.kind or "transient"
            reason = f"{kind}:{exc.code}" if exc.code is not None else kind
            if via_add:
                last_error = ("period_taken:" + reason)[:40]
            else:
                last_error = reason[:40]
            if kind in ("permission", "reauth", "config", "disabled"):
                db.execute(
                    "UPDATE door_code SET last_error = ?, updated_at = ? WHERE id = ?",
                    (reason[:40], now_iso, row["id"]),
                )
                mail_notify.door_code_notice(int(row["id"]), "failed")
                mail.drain(limit=4)
            else:
                # No attempt cap on move replace: the guest still has the old PIN.
                delay = 60 if kind in ("budget", ttlock.LOCK_SETUP) else 15
                db.execute(
                    "UPDATE door_code SET next_attempt_at = ?, last_error = ?, updated_at = ? WHERE id = ?",
                    (_iso(_now() + timedelta(minutes=delay)), last_error, now_iso, row["id"]),
                )
                if kind == ttlock.LOCK_SETUP:
                    # The guest keeps the old code while the hourly retry runs: tell the host
                    # once (the mail queue's idempotency key per row and variant).
                    mail_notify.door_code_notice(int(row["id"]), "moved_failed")
                    mail.drain(limit=4)


def check_lock_clocks() -> Dict[str, int]:
    checked = 0
    adjusted = 0
    now = _now()
    now_iso = _iso(now)
    now_ms = int(now.timestamp() * 1000)
    locks = db.query(
        "SELECT DISTINCT a.owner_user_id, a.lock_id "
        "FROM apartment a WHERE a.lock_provider = 'ttlock' AND a.lock_id IS NOT NULL"
    )
    for lock in locks:
        owner_id = lock["owner_user_id"]
        lock_id = lock["lock_id"]
        if not ttlock.allowed_for(owner_id):
            continue
        account = ttlock.account_for(owner_id)
        if not account or account["status"] != "ok":
            continue
        key = f"ttlock_clock_checked:{lock_id}"
        last = db.get_setting(key)
        if last:
            try:
                seen = datetime.fromisoformat(last)
                if seen.tzinfo is None:
                    seen = seen.replace(tzinfo=timezone.utc)
                if (now - seen).days < 7:
                    continue
            except ValueError:
                pass
        if checked >= 1:
            break
        checked += 1
        sample = db.query_one(
            "SELECT id, internal_name FROM apartment WHERE lock_provider = 'ttlock' "
            "AND lock_id = ? LIMIT 1",
            (lock_id,),
        )
        try:
            drift_ms = ttlock.query_lock_time(int(account["id"]), lock_id) - now_ms
            if abs(drift_ms) > 120_000:
                ttlock.adjust_lock_time(int(account["id"]), lock_id)
                adjusted += 1
                db.audit(
                    "lock_clock_adjusted",
                    f"lock={lock_id} drift_s={drift_ms // 1000}",
                    actor="system",
                    owner_user_id=owner_id,
                )
            db.set_setting(key, now_iso)
        except ttlock.TTLockError as exc:
            kind = exc.kind or "transient"
            if kind in ("offline", "transient", "network", "rate", "budget"):
                db.set_setting(key, _iso(now - timedelta(days=6)))
            else:
                if sample:
                    alerts.raise_alert(
                        "warning",
                        "door_code_clock",
                        "Lock clock could not be checked",
                        dedupe_key=f"door_code_clock:{lock_id}",
                        apartment_id=sample["id"],
                        params={"property": sample["internal_name"]},
                    )
                db.set_setting(key, now_iso)
    return {"clock_checked": checked, "clock_adjusted": adjusted}


def _budget_alerts() -> None:
    used = ttlock.calls_this_month()
    limit = config.TTLOCK_MONTHLY_CALLS
    if limit <= 0:
        return
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    if used >= 0.95 * limit:
        alerts.raise_alert(
            "critical",
            "ttlock_budget",
            "TTLock calls 95 %",
            dedupe_key=f"ttlock_budget:{month}:95",
            params={"percent": 95, "used": used, "limit": limit},
        )
    elif used >= 0.8 * limit:
        alerts.raise_alert(
            "warning",
            "ttlock_budget",
            "TTLock calls 80 %",
            dedupe_key=f"ttlock_budget:{month}:80",
            params={"percent": 80, "used": used, "limit": limit},
        )


def _alert_delayed() -> int:
    """Tell the host about every registered stay still without a code.

    Failure is only declared after the last retry, hours later. A guest who
    finished registering must not wait that long without the host knowing.
    """
    cutoff = _iso(_now() - timedelta(minutes=DELAY_MINUTES))
    today = deadlines.local_now().date().isoformat()
    sql = (
        "SELECT r.id AS reservation_id, r.date_from, a.id AS apartment_id, "
        "a.internal_name, a.owner_user_id, dc.last_error, (dc.id IS NOT NULL) AS has_row "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "LEFT JOIN door_code dc ON dc.reservation_id = r.id "
        "WHERE a.lock_provider = 'ttlock' AND r.status = 'active' "
        "AND r.archived_at IS NULL AND r.registration_completed_at IS NOT NULL "
        "AND r.registration_completed_at < ? AND r.date_to >= ? "
        "AND COALESCE(r.source, '') != 'demo' "
        "AND (dc.id IS NULL OR dc.state IN (?, ?, ?))"
    )
    if not config.DOOR_CODES_LIVE:
        sql += " AND r.source = 'manual'"
    rows = db.query(sql, (cutoff, today, PENDING, ISSUING, RETRYING))
    for row in rows:
        if not ttlock.allowed_for(row["owner_user_id"]):
            continue
        reason = (row["last_error"] or "").strip() or ("waiting" if row["has_row"] else "not_set_up")
        alerts.raise_alert(
            "warning",
            "door_code_delayed",
            "Door code is taking too long",
            detail=f"reason={reason}",
            dedupe_key=f"door_code_delayed:{row['reservation_id']}",
            apartment_id=row["apartment_id"],
            reservation_id=row["reservation_id"],
            params={"property": row["internal_name"], "date": row["date_from"]},
        )
        log.error(
            "DOOR_CODE_PROBLEM stage=delayed reservation=%s reason=%s", row["reservation_id"], reason
        )
        # One mail to the host (support in copy), once per stay. Never to the guest.
        mail_notify.door_code_delayed_notice(int(row["reservation_id"]), reason)
        push.door_code_missing(int(row["reservation_id"]))
        mail.drain(limit=4)
    return len(rows)


def _phase(name: str, func, *args):
    """Run one reconcile phase so a failure in it cannot starve the others."""
    try:
        return func(*args)
    except Exception:
        log.exception("door_codes reconcile phase failed: %s", name)
        return None


def _issue_due(now_iso: str) -> Dict[str, int]:
    out = {"created": 0, "issued": 0}
    clause, today = _eligible_sql()
    missing = db.query(
        f"SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        f"WHERE {clause} AND NOT EXISTS (SELECT 1 FROM door_code dc WHERE dc.reservation_id = r.id)",
        (today,),
    )
    for row in missing:
        if ensure_row(int(row["id"])) is not None:
            out["created"] += 1

    due = db.query(
        "SELECT id FROM door_code WHERE state IN (?, ?) "
        "AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
        "ORDER BY next_attempt_at LIMIT ?",
        (PENDING, RETRYING, now_iso, BATCH),
    )
    for row in due:
        row_id = int(row["id"])
        if _phase("issue", lambda rid: issue(rid, allow_gateway=True), row_id):
            out["issued"] += 1
    return out


def reconcile() -> Dict[str, int]:
    counts = {"created": 0, "issued": 0, "failed": 0, "expired": 0, "delayed": 0}
    if not config.DOOR_CODES_ENABLED:
        return counts
    now_iso = db.utcnow()

    # Issuing comes first: a guest is waiting on it, and cancellations or moves
    # (which call the gateway, up to 35 s each) must never hold it up.
    issued = _phase("issue_due", _issue_due, now_iso)
    if issued:
        counts.update(issued)

    unsent = db.query(
        "SELECT id FROM door_code WHERE state = ? AND notified_at IS NULL "
        "AND issued_at IS NOT NULL ORDER BY issued_at LIMIT ?",
        (ISSUED, BATCH),
    )
    for row in unsent:
        send_code_mail(int(row["id"]))

    _phase("cancellations", _handle_cancellations, now_iso)
    _phase("moves", _handle_moves, now_iso)

    lease_cutoff = _iso(_now() - timedelta(minutes=LEASE_MINUTES))
    db.execute(
        "UPDATE door_code SET state = ?, claimed_at = NULL, next_attempt_at = ?, updated_at = ? "
        "WHERE state = ? AND claimed_at IS NOT NULL AND claimed_at < ?",
        (RETRYING, now_iso, now_iso, ISSUING, lease_cutoff),
    )

    expired = db.execute(
        "UPDATE door_code SET state = ?, updated_at = ? "
        "WHERE state = ? AND valid_to IS NOT NULL AND valid_to < ?",
        (EXPIRED, now_iso, ISSUED, now_iso),
    )
    counts["expired"] = int(expired or 0)

    failed = db.query_one(
        "SELECT COUNT(*) AS n FROM door_code WHERE state = ?",
        (FAILED,),
    )
    counts["failed"] = int(failed["n"] or 0) if failed else 0

    delayed = _phase("delayed_alerts", _alert_delayed)
    counts["delayed"] = int(delayed or 0)

    clock = _phase("lock_clocks", check_lock_clocks)
    if clock:
        counts.update(clock)
    _phase("budget_alerts", _budget_alerts)
    _phase("held_confirmations", _release_held_confirmations)
    return counts


def on_registration_complete(reservation_id: int) -> None:
    try:
        if not config.DOOR_CODES_ENABLED:
            return
        row_id = ensure_row(reservation_id)
        if row_id is not None:
            issue(row_id)
    except Exception:
        log.exception("door code hook failed reservation=%s", reservation_id)
