"""Door code issuing, delivery and lifecycle (TTLock)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from . import alerts, config, db, deadlines, mail, mail_notify, ttlock

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

BACKOFF_MINUTES = (1, 5, 15, 60, 240)
LEASE_MINUTES = 2
# A guest who has finished registering must not wait longer than this in silence.
DELAY_MINUTES = 10
BATCH = 20

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
        "AND a.checkin_hour IS NOT NULL AND a.checkout_hour IS NOT NULL"
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
    if apartment["lock_provider"] != "ttlock":
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
    first_ms = _iso_to_ms(valid_from) + 24 * 3_600_000 if valid_from else 0
    return {
        "state": "issued",
        "pin": pin,
        "works_from": _fmt_local(valid_from) if valid_from else "",
        "works_until": _fmt_local(valid_to) if valid_to else "",
        "first_use_by": _fmt_local(_ms_to_iso(first_ms)) if valid_from else "",
        "checkin": _stay_checkin_label(reservation["date_from"], apartment["checkin_hour"]),
        "checkout": _stay_checkin_label(reservation["date_to"], apartment["checkout_hour"]),
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
    shown = view(reservation, apartment)
    if not shown or shown.get("state") != "issued":
        return
    lang = claim["lang"] or "en"
    content = mail_notify.build_door_code(
        lang=lang,
        property_name=apartment["internal_name"] or "",
        checkin=shown["checkin"],
        checkout=shown["checkout"],
        first_use_by=shown["first_use_by"],
    )
    payload = mail_notify.guest_payload(apartment, content, lang)
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


def issue(door_code_id: int) -> bool:
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

    try:
        pin: Optional[str] = None
        code_id: Optional[str] = None
        if attempts > 1:
            found = ttlock.find_code_by_name(int(account["id"]), row["lock_id"], name)
            if found:
                pin, code_id = found
        if pin is None:
            pin, code_id = ttlock.create_period_code(
                int(account["id"]),
                row["lock_id"],
                start_ms,
                end_ms,
                name,
                priority,
            )
        with db.cursor():
            db.execute(
                "UPDATE door_code SET state = ?, pin_enc = ?, provider_code_id = ?, "
                "valid_from = ?, valid_to = ?, issued_at = ?, claimed_at = NULL, "
                "last_error = NULL, updated_at = ? WHERE id = ?",
                (
                    ISSUED,
                    db.encrypt_field(pin),
                    code_id,
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
        send_code_mail(door_code_id)
        return True
    except ttlock.TTLockError as exc:
        kind = (exc.kind or "transient")[:40]
        # The TTLock error number goes into last_error so the host alert and the
        # log say what TTLock refused, not only which group the refusal is in.
        reason = f"{kind}:{exc.code}" if exc.code is not None else kind
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
        elif attempts >= len(BACKOFF_MINUTES):
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
        return False
    except Exception:
        log.exception("door_code_issue_failed door_code=%s", door_code_id)
        if attempts >= len(BACKOFF_MINUTES):
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
        return False


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
    account = ttlock.account_for(apartment["owner_user_id"])
    if not account or account["status"] != "ok":
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
            "WHERE id = ?",
            (REVOKE_FAILED, "no_account", now_iso, row_id),
        )
        mail_notify.door_code_notice(row_id, "cancelled_not_deleted")
        return
    attempts = int(row["attempts"])
    try:
        ttlock.delete_code(
            int(account["id"]),
            row["lock_id"],
            row["provider_code_id"] or "",
        )
        db.execute(
            "UPDATE door_code SET state = ?, revoked_at = ?, pin_enc = NULL, claimed_at = NULL, "
            "updated_at = ? WHERE id = ?",
            (REVOKED, now_iso, now_iso, row_id),
        )
        db.audit(
            "door_code_revoked",
            f"door_code={row_id}",
            actor="system",
            owner_user_id=apartment["owner_user_id"],
        )
        mail_notify.door_code_notice(row_id, "cancelled_deleted")
    except ttlock.TTLockError as exc:
        kind = exc.kind or "transient"
        if kind in ("offline", "transient", "network", "rate") and attempts < 3:
            delays = (1, 15, 60)
            next_at = _iso(now + timedelta(minutes=delays[min(attempts - 1, 2)]))
            db.execute(
                "UPDATE door_code SET claimed_at = NULL, next_attempt_at = ?, last_error = ?, "
                "updated_at = ? WHERE id = ?",
                (next_at, kind[:40], now_iso, row_id),
            )
        else:
            db.execute(
                "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
                "WHERE id = ?",
                (REVOKE_FAILED, kind[:40], now_iso, row_id),
            )
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
            db.execute(
                "UPDATE door_code SET state = ?, claimed_at = NULL, updated_at = ? WHERE id = ?",
                (REVOKED, now_iso, row["id"]),
            )
        elif state == ISSUED and row["valid_to"]:
            end_ms = _iso_to_ms(row["valid_to"])
            if end_ms > int(_now().timestamp() * 1000):
                db.execute(
                    "UPDATE door_code SET state = ?, attempts = 0, next_attempt_at = ?, "
                    "claimed_at = NULL, updated_at = ? WHERE id = ?",
                    (REVOKE_PENDING, now_iso, now_iso, row["id"]),
                )

    due = db.query(
        "SELECT id FROM door_code WHERE state = ? AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
        "ORDER BY next_attempt_at LIMIT ?",
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
        db.execute("DELETE FROM door_code WHERE id = ?", (item["id"],))
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
                continue
        account = ttlock.account_for(row["owner_user_id"])
        if not account or account["status"] != "ok":
            continue
        try:
            ttlock.change_code_period(
                int(account["id"]),
                row["lock_id"],
                row["provider_code_id"] or "",
                start_ms,
                end_ms,
                ttlock.NORMAL,
            )
            db.execute(
                "UPDATE door_code SET valid_from = ?, valid_to = ?, notified_at = NULL, "
                "next_attempt_at = NULL, last_error = NULL, updated_at = ? WHERE id = ?",
                (_ms_to_iso(start_ms), _ms_to_iso(end_ms), now_iso, row["id"]),
            )
            db.audit(
                "door_code_moved",
                f"door_code={row['id']}",
                actor="system",
                owner_user_id=row["owner_user_id"],
            )
            send_code_mail(int(row["id"]))
        except ttlock.TTLockError as exc:
            kind = exc.kind or "transient"
            if kind in ("offline", "transient", "network", "rate", "budget"):
                delay = 60 if kind == "budget" else 15
                db.execute(
                    "UPDATE door_code SET next_attempt_at = ?, last_error = ?, updated_at = ? WHERE id = ?",
                    (_iso(_now() + timedelta(minutes=delay)), kind[:40], now_iso, row["id"]),
                )
                continue
            old_code_id = row["provider_code_id"] or ""
            try:
                pin, code_id = ttlock.create_period_code(
                    int(account["id"]),
                    row["lock_id"],
                    start_ms,
                    end_ms,
                    f"UH-{row['id']}",
                    ttlock.NORMAL,
                )
                if old_code_id and old_code_id != code_id:
                    try:
                        ttlock.delete_code(
                            int(account["id"]),
                            row["lock_id"],
                            old_code_id,
                        )
                    except ttlock.TTLockError:
                        log.warning(
                            "door_code_move_orphan lock=%s old_code=%s new_code=%s",
                            row["lock_id"],
                            old_code_id,
                            code_id,
                        )
                db.execute(
                    "UPDATE door_code SET pin_enc = ?, provider_code_id = ?, valid_from = ?, "
                    "valid_to = ?, notified_at = NULL, next_attempt_at = NULL, last_error = NULL, "
                    "updated_at = ? WHERE id = ?",
                    (
                        db.encrypt_field(pin),
                        code_id,
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
            except ttlock.TTLockError:
                db.execute(
                    "UPDATE door_code SET next_attempt_at = ?, updated_at = ? WHERE id = ?",
                    (_iso(_now() + timedelta(minutes=60)), now_iso, row["id"]),
                )


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
        "a.internal_name, dc.last_error "
        "FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "LEFT JOIN door_code dc ON dc.reservation_id = r.id "
        "WHERE a.lock_provider = 'ttlock' AND r.status = 'active' "
        "AND r.archived_at IS NULL AND r.registration_completed_at IS NOT NULL "
        "AND r.registration_completed_at < ? AND r.date_to >= ? "
        "AND (dc.id IS NULL OR dc.state IN (?, ?, ?))"
    )
    if not config.DOOR_CODES_LIVE:
        sql += " AND r.source = 'manual'"
    rows = db.query(sql, (cutoff, today, PENDING, ISSUING, RETRYING))
    for row in rows:
        reason = (row["last_error"] or "").strip() or "waiting"
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
        log.warning(
            "door_code_delayed reservation=%s reason=%s", row["reservation_id"], reason
        )
        # One mail to the host (support in copy), once per stay. Never to the guest.
        mail_notify.door_code_delayed_notice(int(row["reservation_id"]), reason)
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
        if _phase("issue", issue, int(row["id"])):
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
