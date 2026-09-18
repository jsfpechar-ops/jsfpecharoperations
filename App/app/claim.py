"""Reservation claiming: e-mail ownership before guest forms can be filled."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from . import db, deadlines, mail, reporting, validation

log = logging.getLogger("ubyhost.claim")

UNCLAIMED = "unclaimed"
PROVISIONAL = "provisional"
CLAIMED = "claimed"
HOLD_MINUTES = 30
TOKEN_BYTES = 24


def prague_today():
    return deadlines.local_now().date()


def token_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _hold_until_iso(now: Optional[datetime] = None) -> str:
    """UTC instant when a provisional claim hold ends (matches ``db.utcnow()``)."""
    moment = now or datetime.now(timezone.utc)
    return (moment + timedelta(minutes=HOLD_MINUTES)).replace(microsecond=0).isoformat()


def _row(reservation_id: int):
    return db.query_one(
        "SELECT * FROM reservation_claim WHERE reservation_id = ?",
        (reservation_id,),
    )


def ensure_row(reservation_id: int):
    row = _row(reservation_id)
    if row:
        return row
    now = db.utcnow()
    db.insert(
        "reservation_claim",
        {
            "reservation_id": reservation_id,
            "state": UNCLAIMED,
            "token_version": 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    return _row(reservation_id)


def expire_holds(now=None) -> int:
    now = now or db.utcnow()
    rows = db.query(
        "SELECT reservation_id FROM reservation_claim "
        "WHERE state = ? AND provisional_until IS NOT NULL AND provisional_until < ?",
        (PROVISIONAL, now),
    )
    for row in rows:
        db.execute(
            "UPDATE reservation_claim SET state = ?, token_hash = NULL, "
            "provisional_until = NULL, updated_at = ? WHERE reservation_id = ? AND state = ?",
            (UNCLAIMED, now, row["reservation_id"], PROVISIONAL),
        )
    return len(rows)


def guest_access_open(reservation, claim=None) -> bool:
    if reservation["status"] != "active":
        return False
    claim = claim if claim is not None else _row(reservation["id"])
    if not claim:
        return True
    return not claim["guest_access_locked_at"]


def is_claimed(claim) -> bool:
    return bool(claim and claim["state"] == CLAIMED)


def start_claim(
    reservation,
    apartment,
    *,
    email: str,
    party_size: int,
    lang: str,
    resend: bool = False,
) -> Tuple[bool, str, Optional[str]]:
    """Return (ok, error_code, secret_if_any). Secret is only for tests/console."""
    expire_holds()
    addr = mail.normalise_email(email)
    if not addr:
        return False, "bad_email", None
    if party_size < 1 or party_size > 60:
        return False, "bad_party", None
    if reservation["status"] != "active":
        return False, "stay_gone", None
    claim = ensure_row(reservation["id"])
    if claim["guest_access_locked_at"]:
        return False, "locked", None
    if claim["state"] == CLAIMED and not resend:
        return False, "already_claimed", None
    if claim["state"] == CLAIMED and resend:
        if mail.normalise_email(claim["email"] or "") != addr:
            return False, "already_claimed", None
    if claim["state"] == PROVISIONAL and not resend:
        if claim["provisional_until"] and claim["provisional_until"] > db.utcnow():
            if mail.normalise_email(claim["email"] or "") != addr:
                return False, "held", None

    secret = secrets.token_urlsafe(TOKEN_BYTES)
    now = db.utcnow()
    until = _hold_until_iso()
    version = int(claim["token_version"] or 0) + 1
    db.execute(
        "UPDATE reservation_claim SET state = ?, email = ?, email_masked = ?, lang = ?, "
        "token_hash = ?, token_version = ?, provisional_until = ?, declared_guests = ?, "
        "updated_at = ? WHERE reservation_id = ?",
        (
            PROVISIONAL if claim["state"] != CLAIMED else CLAIMED,
            addr,
            mail.mask_email(addr),
            lang,
            token_hash(secret),
            version,
            until if claim["state"] != CLAIMED else claim["provisional_until"],
            party_size,
            now,
            reservation["id"],
        ),
    )
    if not reservation["expected_guests_override"]:
        db.update(
            "reservation",
            reservation["id"],
            {"declared_guests": party_size, "updated_at": now},
        )
    link = (
        f"{config_public(apartment)}/l/{apartment['permalink_token']}/"
        f"{reservation['id']}/claim#c={secret}"
    )
    kind = "claim_resend" if resend or claim["state"] == CLAIMED else "claim"
    subject = (
        "Continue your Prague guest registration"
        if lang != "cs"
        else "Pokračujte v registraci hostů"
    )
    text = _claim_text(lang, apartment, reservation, link)
    mail.enqueue(
        kind=kind,
        idempotency_key=f"{kind}:{reservation['id']}:v{version}",
        to_email=addr,
        subject=subject,
        payload={"text": text, "lang": lang},
        reservation_id=reservation["id"],
        apartment_id=apartment["id"],
        owner_user_id=apartment["owner_user_id"],
    )
    mail.drain(limit=4)
    return True, "", secret


def config_public(apartment) -> str:
    from . import config

    return config.PUBLIC_BASE_URL.rstrip("/")


def _claim_text(lang: str, apartment, reservation, link: str) -> str:
    name = (apartment["uby_name"] or apartment["internal_name"] or "your host").strip()
    dates = f"{reservation['date_from']} – {reservation['date_to']}"
    if lang == "cs":
        return (
            f"Dobrý den,\n\n"
            f"potvrďte rezervaci v {name} ({dates}) otevřením tohoto odkazu:\n"
            f"{link}\n\n"
            f"Odkaz platí 30 minut, pokud rezervaci ještě nepotvrdíte.\n"
        )
    return (
        f"Hello,\n\n"
        f"Confirm your stay at {name} ({dates}) by opening this link:\n"
        f"{link}\n\n"
        f"The link expires in 30 minutes until you confirm the reservation.\n"
    )


def confirm(reservation, secret: str) -> bool:
    expire_holds()
    claim = _row(reservation["id"])
    if not claim or not secret or not claim["token_hash"]:
        return False
    if reservation["status"] != "active":
        return False
    if claim["guest_access_locked_at"]:
        return False
    if token_hash(secret) != claim["token_hash"]:
        return False
    if claim["state"] == PROVISIONAL:
        if claim["provisional_until"] and claim["provisional_until"] < db.utcnow():
            return False
    now = db.utcnow()
    db.execute(
        "UPDATE reservation_claim SET state = ?, claimed_at = ?, "
        "provisional_until = NULL, updated_at = ? "
        "WHERE reservation_id = ? AND token_hash = ? AND state IN (?, ?)",
        (CLAIMED, now, now, reservation["id"], claim["token_hash"], PROVISIONAL, CLAIMED),
    )
    row = _row(reservation["id"])
    return bool(row and row["state"] == CLAIMED)


def secret_matches(claim, secret: str) -> bool:
    return bool(claim and secret and claim["token_hash"] == token_hash(secret))


def release(reservation_id: int) -> None:
    now = db.utcnow()
    db.execute(
        "UPDATE reservation_claim SET state = ?, email = NULL, email_masked = NULL, "
        "token_hash = NULL, provisional_until = NULL, claimed_at = NULL, "
        "guest_access_locked_at = NULL, updated_at = ? WHERE reservation_id = ?",
        (UNCLAIMED, now, reservation_id),
    )


def lock_guest_access(reservation_id: int) -> None:
    now = db.utcnow()
    db.execute(
        "UPDATE reservation_claim SET guest_access_locked_at = ?, updated_at = ? "
        "WHERE reservation_id = ? AND (guest_access_locked_at IS NULL)",
        (now, now, reservation_id),
    )


def reopen_guest_access(reservation_id: int) -> None:
    now = db.utcnow()
    db.execute(
        "UPDATE reservation_claim SET guest_access_locked_at = NULL, updated_at = ? "
        "WHERE reservation_id = ?",
        (now, reservation_id),
    )


def expire_on_cancel(reservation) -> None:
    claim = _row(reservation["id"])
    if not claim:
        return
    now = db.utcnow()
    db.execute(
        "UPDATE reservation_claim SET token_hash = NULL, guest_access_locked_at = ?, "
        "updated_at = ? WHERE reservation_id = ?",
        (now, now, reservation["id"]),
    )
    db.execute(
        "UPDATE email_outbox SET state = ?, updated_at = ? "
        "WHERE reservation_id = ? AND state = ?",
        (mail.FAILED, now, reservation["id"], mail.QUEUED),
    )


def maybe_notify_completion(reservation, apartment) -> None:
    claim = _row(reservation["id"])
    if not claim or claim["state"] != CLAIMED or claim["completion_notified_at"]:
        return
    progress = reporting.reservation_progress(reservation)
    expected = progress["expected"]
    if expected is None or progress["filled"] < expected:
        return
    lang = claim["lang"] or "en"
    entity = None
    if apartment["legal_entity_id"]:
        entity = db.query_one(
            "SELECT * FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],)
        )
    cc = (entity["contact_email"] if entity else "") or ""
    subject = (
        "Guest registration received"
        if lang != "cs"
        else "Registrace hostů byla přijata"
    )
    name = (apartment["uby_name"] or apartment["internal_name"] or "").strip()
    text = (
        f"Thank you. Details for your stay at {name} "
        f"({reservation['date_from']} – {reservation['date_to']}) have been received. "
        f"This is not the police report — your host still files that after arrival."
        if lang != "cs"
        else f"Děkujeme. Údaje k pobytu v {name} "
        f"({reservation['date_from']} – {reservation['date_to']}) jsme přijali. "
        f"Toto ještě není oznámení policii — to podává hostitel až po ubytování."
    )
    mail.enqueue(
        kind="completion",
        idempotency_key=f"completion:{reservation['id']}:{progress['filled']}",
        to_email=claim["email"],
        cc_email=cc,
        subject=subject,
        payload={"text": text, "lang": lang},
        reservation_id=reservation["id"],
        apartment_id=apartment["id"],
        owner_user_id=apartment["owner_user_id"],
    )
    db.execute(
        "UPDATE reservation_claim SET completion_notified_at = ?, updated_at = ? "
        "WHERE reservation_id = ?",
        (db.utcnow(), db.utcnow(), reservation["id"]),
    )
    mail.drain(limit=4)


def sweep_reminders() -> Dict[str, int]:
    from . import alerts, config

    today = prague_today()
    summary = {"guest": 0, "host": 0, "locked": 0}
    expire_holds()
    rows = db.query(
        "SELECT r.*, a.permalink_token, a.internal_name, a.uby_name, a.owner_user_id, "
        "a.legal_entity_id, c.state AS claim_state, c.email AS claim_email, "
        "c.lang AS claim_lang, c.email_masked AS email_masked, "
        "c.guest_access_locked_at AS guest_access_locked_at, c.token_version AS token_version "
        "FROM reservation r "
        "JOIN apartment a ON a.id = r.apartment_id "
        "LEFT JOIN reservation_claim c ON c.reservation_id = r.id "
        "WHERE r.status = 'active' AND r.archived_at IS NULL AND a.active = 1 "
        "AND a.archived_at IS NULL"
    )
    now_local = deadlines.local_now()
    for reservation in rows:
        start = validation.parse_iso_date(reservation["date_from"])
        if not start:
            continue
        progress = reporting.reservation_progress(reservation)
        complete = progress["expected"] is not None and progress["filled"] >= progress["expected"]
        if start == today + timedelta(days=1) and now_local.hour >= 9:
            if reservation["claim_state"] == CLAIMED and reservation["claim_email"] and not complete:
                if mail.enqueue(
                    kind="reminder_guest",
                    idempotency_key=f"reminder_guest:{reservation['id']}:{start.isoformat()}",
                    to_email=reservation["claim_email"],
                    subject="Please finish your guest registration",
                    payload={
                        "text": (
                            "Your stay is tomorrow. Please finish the guest registration "
                            f"using the private link already sent to {reservation['email_masked']}."
                        ),
                        "lang": reservation["claim_lang"] or "en",
                    },
                    reservation_id=reservation["id"],
                    apartment_id=reservation["apartment_id"],
                    owner_user_id=reservation["owner_user_id"],
                ):
                    summary["guest"] += 1
        if start == today:
            if not complete:
                if not reservation["guest_access_locked_at"]:
                    lock_guest_access(reservation["id"])
                    summary["locked"] += 1
                if now_local.hour >= 9:
                    entity = None
                    if reservation["legal_entity_id"]:
                        entity = db.query_one(
                            "SELECT * FROM legal_entity WHERE id = ?",
                            (reservation["legal_entity_id"],),
                        )
                    host_email = (entity["contact_email"] if entity else "") or ""
                    masked = reservation["email_masked"] or "not claimed"
                    if host_email:
                        mail.enqueue(
                            kind="reminder_host",
                            idempotency_key=f"reminder_host:{reservation['id']}:{start.isoformat()}",
                            to_email=host_email,
                            subject=f"Incomplete registration: {reservation['internal_name']}",
                            payload={
                                "text": (
                                    f"{reservation['internal_name']} check-in is today "
                                    f"({reservation['date_from']}). Guest forms are incomplete "
                                    f"(assigned to {masked}). "
                                    f"Open {config.PUBLIC_BASE_URL}/reservations/{reservation['id']}"
                                )
                            },
                            reservation_id=reservation["id"],
                            apartment_id=reservation["apartment_id"],
                            owner_user_id=reservation["owner_user_id"],
                        )
                    alerts.raise_alert(
                        "warning",
                        "guest_incomplete_checkin",
                        f"{reservation['internal_name']}: check-in today and forms are incomplete.",
                        f"Claimed as {masked}. Reopen guest access from the stay page if needed.",
                        dedupe_key=f"guest_incomplete_checkin:{reservation['id']}",
                        apartment_id=reservation["apartment_id"],
                        reservation_id=reservation["id"],
                    )
                    summary["host"] += 1
    mail.drain(limit=8)
    return summary
