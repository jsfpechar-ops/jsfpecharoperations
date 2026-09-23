"""Reservation claiming: e-mail ownership before guest forms can be filled."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from . import config, db, deadlines, i18n, mail, mail_notify, reporting, validation

log = logging.getLogger("ubyhost.claim")

UNCLAIMED = "unclaimed"
PROVISIONAL = "provisional"
CLAIMED = "claimed"
HOLD_MINUTES = 30
# How long an unconfirmed hold keeps a *different* address out. Long enough to
# stop two people racing the same booking, short enough that a guest who
# mistyped their address is not stuck for the whole hold.
HOLD_TAKEOVER_SECONDS = 60
TOKEN_BYTES = 24


def prague_today():
    return deadlines.local_now().date()


def token_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _parse_provisional_until(value: str) -> datetime:
    """Normalise stored hold deadlines for comparison (UTC-aware)."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(config.TIMEZONE))
    return parsed.astimezone(timezone.utc)


def _hold_still_active(provisional_until: Optional[str], now: Optional[str] = None) -> bool:
    if not provisional_until:
        return False
    now_utc = _parse_provisional_until(now or db.utcnow())
    return _parse_provisional_until(provisional_until) > now_utc


def _hold_age_seconds(
    provisional_until: Optional[str], now: Optional[str] = None
) -> Optional[float]:
    """Seconds since the current hold was created, derived from its deadline."""
    if not provisional_until:
        return None
    started = _parse_provisional_until(provisional_until) - timedelta(
        minutes=HOLD_MINUTES
    )
    now_utc = _parse_provisional_until(now or db.utcnow())
    return (now_utc - started).total_seconds()


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
    now_utc = _parse_provisional_until(now)
    rows = db.query(
        "SELECT reservation_id, provisional_until FROM reservation_claim "
        "WHERE state = ? AND provisional_until IS NOT NULL",
        (PROVISIONAL,),
    )
    expired_ids = [
        row["reservation_id"]
        for row in rows
        if _parse_provisional_until(row["provisional_until"]) <= now_utc
    ]
    for reservation_id in expired_ids:
        db.execute(
            "UPDATE reservation_claim SET state = ?, token_hash = NULL, "
            "provisional_until = NULL, updated_at = ? WHERE reservation_id = ? AND state = ?",
            (UNCLAIMED, now, reservation_id, PROVISIONAL),
        )
    return len(expired_ids)


def guest_access_open(reservation, claim=None, now=None) -> bool:
    """True unless the stay is inactive or the host explicitly locked access.

    Incomplete registrations stay reachable after check-in; only an explicit
    host lock (or cancellation) closes guest access. ``now`` is accepted for
    call-site compatibility and ignored.
    """
    if reservation["status"] != "active":
        return False
    claim = claim if claim is not None else _row(reservation["id"])
    if claim and claim["guest_access_locked_at"]:
        return False
    return True


def is_claimed(claim) -> bool:
    return bool(claim and claim["state"] == CLAIMED)


# Abuse caps for transactional claim mail. These exist to bound bulk misuse, not
# to punish a real guest: someone who mistypes an address, or whose mail never
# arrives, must be able to try again. Keep them generous enough that a single
# booking cannot be locked out by a couple of attempts.
RESEND_COOLDOWN_SECONDS = 60
CLAIM_MAIL_PER_RECIPIENT_MAX = 5
CLAIM_MAIL_PER_RECIPIENT_WINDOW = 60 * 60
CLAIM_MAIL_PER_RESERVATION_MAX = 8
CLAIM_MAIL_PER_RESERVATION_WINDOW = 60 * 60


def _parse_utc(stamp: Optional[str]) -> Optional[datetime]:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def _recipient_rate_key(addr: str) -> str:
    digest = hashlib.sha256(addr.encode("utf-8")).hexdigest()
    return f"claim_to:{digest}"


def _claim_mail_blocked(reservation_id: int, addr: str) -> Optional[str]:
    """Return an error code when recipient or stay caps are exhausted."""
    from . import rate_limit

    if rate_limit.blocked(
        "claim_mail_recipient",
        _recipient_rate_key(addr),
        CLAIM_MAIL_PER_RECIPIENT_MAX,
        CLAIM_MAIL_PER_RECIPIENT_WINDOW,
    ):
        return "recipient_rate"
    if rate_limit.blocked(
        "claim_mail_reservation",
        f"claim_res:{reservation_id}",
        CLAIM_MAIL_PER_RESERVATION_MAX,
        CLAIM_MAIL_PER_RESERVATION_WINDOW,
    ):
        return "rate"
    return None


def _record_claim_mail(reservation_id: int, addr: str) -> None:
    from . import rate_limit

    rate_limit.record("claim_mail_recipient", _recipient_rate_key(addr))
    rate_limit.record("claim_mail_reservation", f"claim_res:{reservation_id}")


def _resend_too_soon(claim) -> bool:
    last = _parse_utc(claim["updated_at"] if claim else None)
    if not last:
        return False
    now = _parse_utc(db.utcnow()) or datetime.now(timezone.utc)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last).total_seconds() < RESEND_COOLDOWN_SECONDS


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
    if not guest_access_open(reservation, claim):
        lock_guest_access(reservation["id"])
        return False, "locked", None
    if claim["state"] == CLAIMED and not resend:
        return False, "already_claimed", None
    if claim["state"] == CLAIMED and resend:
        if mail.normalise_email(claim["email"] or "") != addr:
            return False, "already_claimed", None
    same_email = mail.normalise_email(claim["email"] or "") == addr
    if claim["state"] == PROVISIONAL and not resend:
        if _hold_still_active(claim["provisional_until"]):
            if same_email:
                # Same address already has an active hold — do not rotate/send again.
                return False, "already_sent", None
            age = _hold_age_seconds(claim["provisional_until"])
            if age is None or age < HOLD_TAKEOVER_SECONDS:
                return False, "held", None
            # Past the grace window the corrected address takes over: a mistyped
            # address must stay recoverable. The token rotation below invalidates
            # the link that went to the wrong address.
    if resend or claim["state"] == CLAIMED:
        if _resend_too_soon(claim):
            return False, "cooldown", None

    blocked = _claim_mail_blocked(int(reservation["id"]), addr)
    if blocked:
        return False, blocked, None

    secret = secrets.token_urlsafe(TOKEN_BYTES)
    now = db.utcnow()
    until = (
        datetime.now(timezone.utc) + timedelta(minutes=HOLD_MINUTES)
    ).replace(microsecond=0).isoformat()
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
        f"{reservation['id']}/claim#c={mail.CLAIM_SECRET_MARKER}"
    )
    kind = "claim_resend" if resend or claim["state"] == CLAIMED else "claim"
    text = _claim_text(lang, apartment, reservation, link)
    content = _guest_mail_content(
        kind,
        apartment,
        reservation,
        lang=lang,
        link=link,
        resend=kind == "claim_resend",
        plain_text=text,
    )
    # The body is stored with the marker standing in for the secret and the
    # secret beside it, encrypted, so the queued message holds a link the guest
    # can use once sent and nothing usable while it waits. The marker sits in
    # both the text and the HTML part, and mail.py substitutes it in each.
    payload = {
        "text": content["text"],
        "lang": lang,
        mail.CLAIM_SECRET_KEY: db.encrypt_field(secret),
    }
    if content.get("html"):
        payload["html"] = content["html"]
    reply_to = _reply_to_for_apartment(apartment)
    if reply_to:
        payload["reply_to"] = reply_to
    mail.enqueue(
        kind=kind,
        idempotency_key=f"{kind}:{reservation['id']}:v{version}",
        to_email=addr,
        subject=content["subject"],
        payload=payload,
        reservation_id=reservation["id"],
        apartment_id=apartment["id"],
        owner_user_id=apartment["owner_user_id"],
    )
    _record_claim_mail(int(reservation["id"]), addr)
    mail.drain(limit=4)
    return True, "", secret


def _guest_mail_content(
    kind: str,
    apartment,
    reservation,
    *,
    lang: str,
    plain_text: str,
    link: Optional[str] = None,
    resend: bool = False,
    stay_url: Optional[str] = None,
) -> Dict[str, str]:
    """Compose a guest message, falling back to plain text on any failure.

    A guest is mid-flow when this runs: in the claim path they are waiting on a
    response that carries their link. So the caller's plain-text body is the
    contract, and the branded HTML is an enhancement -- a composer bug costs the
    guest the nicer message, never the link.
    """
    fallback = {
        "subject": _guest_mail_subject(kind, lang),
        "text": plain_text,
    }
    try:
        property_name = mail_notify.property_label(apartment, lang)
        dates = f"{reservation['date_from']} \u2013 {reservation['date_to']}"
        host = mail_notify.host_details(
            apartment["legal_entity_id"] if apartment else None
        )
        if kind in ("claim", "claim_resend"):
            return mail_notify.build_claim_link(
                lang=lang,
                property_name=property_name,
                dates=dates,
                link=link or "",
                resend=resend,
                host=host,
            )
        if kind == "completion":
            return mail_notify.build_completion(
                lang=lang,
                property_name=property_name,
                dates=dates,
                stay_url=stay_url or "",
                host=host,
            )
        if kind == "reminder_guest":
            return mail_notify.build_reminder_guest(
                lang=lang,
                property_name=property_name,
                dates=dates,
                stay_url=stay_url or "",
                host=host,
            )
    except Exception:
        log.exception(
            "guest_mail_compose_failed kind=%s reservation_id=%s",
            kind,
            (reservation["id"] if reservation is not None else None),
        )
    return fallback


def _guest_mail_subject(kind: str, lang: str) -> str:
    key = {
        "claim": "mail_claim_subject",
        "claim_resend": "mail_claim_subject",
        "completion": "mail_completion_subject",
        "reminder_guest": "mail_reminder_guest_subject",
    }.get(kind, "mail_claim_subject")
    return i18n.translator(lang)(key)


def _stay_link(apartment, reservation) -> str:
    """The guest's stay address, absolute so it survives an e-mail client."""
    return (
        f"{config_public(apartment)}/l/{apartment['permalink_token']}/{reservation['id']}"
    )


def config_public(apartment) -> str:
    from . import config

    return config.PUBLIC_BASE_URL.rstrip("/")


def _entity_contact_email(legal_entity_id) -> str:
    if not legal_entity_id:
        return ""
    entity = db.query_one(
        "SELECT contact_email FROM legal_entity WHERE id = ?",
        (legal_entity_id,),
    )
    return mail.normalise_email((entity["contact_email"] if entity else "") or "")


def _reply_to_for_apartment(apartment) -> str:
    return _entity_contact_email(apartment["legal_entity_id"] if apartment else None)


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
    if not guest_access_open(reservation, claim):
        lock_guest_access(reservation["id"])
        return False
    if token_hash(secret) != claim["token_hash"]:
        return False
    if claim["state"] == PROVISIONAL:
        if claim["provisional_until"] and claim["provisional_until"] < db.utcnow():
            return False
    now = db.utcnow()
    version = int(claim["token_version"] or 0)
    # Confirming spends the secret: token_hash is cleared, so the link in the
    # e-mail cannot be replayed. From here the stay is reached with the
    # ubyhost_claim cookie, or with a freshly issued secret if the host resends.
    # token_version is part of the condition so a resend that landed between the
    # read above and this write cannot be confirmed with the superseded secret.
    db.execute(
        "UPDATE reservation_claim SET state = ?, claimed_at = ?, token_hash = NULL, "
        "provisional_until = NULL, updated_at = ? "
        "WHERE reservation_id = ? AND token_hash = ? AND token_version = ? "
        "AND state IN (?, ?)",
        (
            CLAIMED,
            now,
            now,
            reservation["id"],
            claim["token_hash"],
            version,
            PROVISIONAL,
            CLAIMED,
        ),
    )
    row = _row(reservation["id"])
    return bool(row and row["state"] == CLAIMED and row["token_hash"] is None)


def release(reservation_id: int) -> None:
    now = db.utcnow()
    db.execute(
        "UPDATE reservation_claim SET state = ?, email = NULL, email_masked = NULL, "
        "token_hash = NULL, provisional_until = NULL, claimed_at = NULL, "
        "guest_access_locked_at = NULL, guest_access_reopened_at = ?, "
        "updated_at = ? WHERE reservation_id = ?",
        (UNCLAIMED, now, now, reservation_id),
    )


def lock_guest_access(reservation_id: int) -> None:
    now = db.utcnow()
    db.execute(
        "UPDATE reservation_claim SET guest_access_locked_at = ?, "
        "guest_access_reopened_at = NULL, updated_at = ? "
        "WHERE reservation_id = ? AND (guest_access_locked_at IS NULL)",
        (now, now, reservation_id),
    )


def reopen_guest_access(reservation_id: int) -> None:
    now = db.utcnow()
    db.execute(
        "UPDATE reservation_claim SET guest_access_locked_at = NULL, "
        "guest_access_reopened_at = ?, updated_at = ? "
        "WHERE reservation_id = ?",
        (now, now, reservation_id),
    )


def expire_on_cancel(reservation) -> None:
    claim = _row(reservation["id"])
    if not claim:
        return
    now = db.utcnow()
    db.execute(
        "UPDATE reservation_claim SET token_hash = NULL, guest_access_locked_at = ?, "
        "guest_access_reopened_at = NULL, "
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
    reply_to = _reply_to_for_apartment(apartment)
    cc = reply_to
    name = (apartment["uby_name"] or apartment["internal_name"] or "").strip()
    text = (
        f"Thank you. Details for your stay at {name} "
        f"({reservation['date_from']} – {reservation['date_to']}) have been received. "
        f"This receipt is not proof of police reporting. Depending on your host's settings, "
        f"complete foreign-guest records may be sent to UbyPort automatically."
        if lang != "cs"
        else f"Děkujeme. Údaje k pobytu v {name} "
        f"({reservation['date_from']} – {reservation['date_to']}) jsme přijali. "
        f"Toto potvrzení není důkazem hlášení policii. Podle nastavení ubytovatele mohou být "
        f"kompletní záznamy cizinců odeslány do UbyPortu automaticky."
    )
    content = _guest_mail_content(
        "completion",
        apartment,
        reservation,
        lang=lang,
        plain_text=text,
        stay_url=_stay_link(apartment, reservation),
    )
    payload = {"text": content["text"], "lang": lang}
    if content.get("html"):
        payload["html"] = content["html"]
    if reply_to:
        payload["reply_to"] = reply_to
    mail.enqueue(
        kind="completion",
        idempotency_key=f"completion:{reservation['id']}:{progress['filled']}",
        to_email=claim["email"],
        cc_email=cc,
        subject=content["subject"],
        payload=payload,
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
        "c.guest_access_locked_at AS guest_access_locked_at, "
        "c.guest_access_reopened_at AS guest_access_reopened_at, "
        "c.token_version AS token_version "
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
        complete = (
            progress["expected"] is not None
            and progress["filled"] >= progress["expected"]
            and not progress["incomplete"]
        )
        if (
            start == today + timedelta(days=1)
            and now_local.hour >= 9
            and reservation["claim_state"] == CLAIMED
            and reservation["claim_email"]
            and not complete
        ):
            lang = reservation["claim_lang"] or "en"
            text = (
                "Your stay starts tomorrow. Please finish the guest registration "
                "using the private link we already sent you. This is the only "
                "incomplete-registration reminder we will send."
                if lang != "cs"
                else "Váš pobyt začíná zítra. Dokončete prosím registraci hostů "
                "pomocí soukromého odkazu, který jsme vám již poslali. Toto je jediné "
                "upozornění na nedokončenou registraci, které vám pošleme."
            )
            stay_url = (
                f"{config.PUBLIC_BASE_URL.rstrip('/')}/l/{reservation['permalink_token']}"
                f"/{reservation['id']}"
            )
            content = _guest_mail_content(
                "reminder_guest",
                reservation,
                reservation,
                lang=lang,
                plain_text=text,
                stay_url=stay_url,
            )
            guest_payload = {"text": content["text"], "lang": lang}
            if content.get("html"):
                guest_payload["html"] = content["html"]
            reply_to = _entity_contact_email(reservation["legal_entity_id"])
            if reply_to:
                guest_payload["reply_to"] = reply_to
            if mail.enqueue(
                kind="reminder_guest",
                idempotency_key=(
                    f"reminder_guest:{reservation['id']}:{start.isoformat()}"
                ),
                to_email=reservation["claim_email"],
                subject=content["subject"],
                payload=guest_payload,
                reservation_id=reservation["id"],
                apartment_id=reservation["apartment_id"],
                owner_user_id=reservation["owner_user_id"],
            ):
                summary["guest"] += 1
        if start == today and not complete and now_local.hour >= 9:
            host_email = _entity_contact_email(reservation["legal_entity_id"])
            masked = reservation["email_masked"] or ""
            if host_email:
                host_content = mail_notify.build_reminder_host(
                    property_name=reservation["internal_name"] or "",
                    date=reservation["date_from"],
                    assigned=masked,
                    stay_url=(
                        f"{config.PUBLIC_BASE_URL.rstrip('/')}"
                        f"/reservations/{reservation['id']}"
                    ),
                )
                host_payload = {"text": host_content["text"], "lang": "en"}
                if host_content.get("html"):
                    host_payload["html"] = host_content["html"]
                mail.enqueue(
                    kind="reminder_host",
                    idempotency_key=f"reminder_host:{reservation['id']}:{start.isoformat()}",
                    to_email=host_email,
                    subject=host_content["subject"],
                    payload=host_payload,
                    reservation_id=reservation["id"],
                    apartment_id=reservation["apartment_id"],
                    owner_user_id=reservation["owner_user_id"],
                )
            alerts.raise_alert(
                "warning",
                "guest_incomplete_checkin",
                f"{reservation['internal_name']} · check-in today",
                "Forms incomplete",
                dedupe_key=f"guest_incomplete_checkin:{reservation['id']}",
                apartment_id=reservation["apartment_id"],
                reservation_id=reservation["id"],
            )
            summary["host"] += 1
    mail.drain(limit=8)
    return summary
