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


def _stay_forms_complete(reservation) -> bool:
    """True when every declared guest has a finished form [E-25].

    A link resent for such a stay opens the stay page; it does not lead back
    into a form, so the mail must not promise one. Any doubt falls back to the
    ordinary copy: the guest losing the link is the failure that matters.
    """
    try:
        progress = reporting.reservation_progress(reservation)
    except Exception:
        log.exception(
            "claim_progress_failed reservation_id=%s",
            (reservation["id"] if reservation is not None else None),
        )
        return False
    return (
        progress["expected"] is not None
        and progress["filled"] >= progress["expected"]
        and not progress["incomplete"]
    )


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
    content = _guest_mail_content(
        kind,
        apartment,
        reservation,
        lang=lang,
        link=link,
        resend=kind == "claim_resend",
        stay_complete=_stay_forms_complete(reservation),
    )
    # The body is stored with the marker standing in for the secret and the
    # secret beside it, encrypted, so the queued message holds a link the guest
    # can use once sent and nothing usable while it waits. The marker sits in
    # both the text and the HTML part, and mail.py substitutes it in each.
    payload = mail_notify.guest_payload(apartment, content, lang)
    payload[mail.CLAIM_SECRET_KEY] = db.encrypt_field(secret)
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
    link: Optional[str] = None,
    resend: bool = False,
    stay_url: Optional[str] = None,
    filled: int = 0,
    expected: Optional[int] = None,
    stay_complete: bool = False,
) -> Dict[str, str]:
    """Compose a guest message, falling back to plain text on any failure.

    A guest is mid-flow when this runs: in the claim path they are waiting on a
    response that carries their link. So the plain-text body is the contract,
    and the branded HTML is an enhancement -- a composer bug costs the guest the
    nicer message, never the link.

    The plain-text body is built here from the same catalogue the branded one
    reads, rather than handed in by each caller. Three callers used to write it
    out by hand, which is how the Czech claim body came to say "your host" in
    English and how the dates stayed in raw ISO on the one surface that mattered
    most.
    """
    # The subject names the property, so the label has to resolve before the
    # fallback subject is built. It is also the one value here that must never
    # cost the guest their mail: a label that cannot be read falls back to an
    # empty name, not to the plain-text body.
    try:
        property_name = mail_notify.property_label(apartment, lang)
    except Exception:
        property_name = ""
    # The dates are read before the composer runs because the fallback body
    # prints them too, and the fallback is what ships when the composer throws.
    try:
        dates = validation.fmt_date_range(
            reservation["date_from"], reservation["date_to"]
        )
    except Exception:
        dates = f"{reservation['date_from']} \u2013 {reservation['date_to']}"
    fallback = {
        "subject": _guest_mail_subject(
            kind, lang, property_name, filled=filled, expected=expected
        ),
        "text": _guest_fallback_text(
            kind,
            lang,
            property_name=property_name,
            dates=dates,
            link=link or stay_url or "",
            resend=resend,
            filled=filled,
            expected=expected,
        ),
    }
    try:
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
                stay_complete=stay_complete,
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
                stay_url=stay_url or "",
                host=host,
                filled=filled,
                expected=expected,
            )
    except Exception:
        log.exception(
            "guest_mail_compose_failed kind=%s reservation_id=%s",
            kind,
            (reservation["id"] if reservation is not None else None),
        )
    return fallback


def _guest_mail_subject(
    kind: str,
    lang: str,
    property_name: str = "",
    *,
    filled: int = 0,
    expected: Optional[int] = None,
) -> str:
    """The subject, rebuilt from the catalogue so a composer failure still
    sends one that names the stay."""
    if kind == "reminder_guest":
        key = (
            "mail_reminder_guest_subject"
            if expected is not None
            else "mail_reminder_guest_subject_no_count"
        )
        return i18n.translator(lang)(
            key, property=property_name, filled=filled, expected=expected
        )
    key = {
        "claim": "mail_claim_subject",
        "claim_resend": "mail_claim_resend_subject",
        "completion": "mail_completion_subject",
    }.get(kind, "mail_claim_subject")
    return i18n.translator(lang)(key, property=property_name)


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


def _guest_fallback_text(
    kind: str,
    lang: str,
    *,
    property_name: str,
    dates: str,
    link: str = "",
    resend: bool = False,
    filled: int = 0,
    expected: Optional[int] = None,
) -> str:
    """The plain-text body, built from the same catalogue the branded one reads.

    This ships only when the branded composer throws, so it must not be able to
    throw itself: every string comes from ``i18n`` and the only work done here
    is joining. It used to be written out by hand in this module, which is how
    the Czech claim body came to say "your host" in English, how the dates
    stayed in raw ISO, and how the reminder told the guest to open a link
    without ever printing one.
    """
    t = i18n.translator(lang)
    if kind in ("claim", "claim_resend"):
        return "\n".join(
            [
                t("mail_claim_intro", property=property_name, dates=dates),
                "",
                f"{t('mail_claim_action')}: {link}",
                "",
                t("mail_claim_expiry_resend" if resend else "mail_claim_expiry"),
            ]
        )
    if kind == "completion":
        return "\n".join(
            [
                t("mail_completion_intro", property=property_name, dates=dates),
                "",
                f"{t('mail_completion_action')}: {link}",
                "",
                t("mail_completion_note"),
            ]
        )
    missing = max(0, expected - filled) if expected is not None else None
    intro = (
        t("mail_reminder_guest_intro", missing=missing)
        if missing is not None
        else t("mail_reminder_guest_intro_no_count", property=property_name)
    )
    return "\n".join(
        [
            t("mail_reminder_guest_heading"),
            "",
            intro,
            "",
            f"{t('mail_reminder_guest_action')}: {link}",
            "",
            t("mail_reminder_guest_device"),
            "",
            f"{t('mail_reminder_guest_note_label')} \u2014 "
            f"{t('mail_reminder_guest_note')}",
        ]
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
    #
    # The result is the UPDATE's own row count, not the state read back after it:
    # two confirms racing on the same secret both used to see the winner's CLAIMED
    # row and both returned True, even though only one of them spent the link.
    with db.cursor() as cur:
        cur.execute(
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
        return cur.rowcount == 1


def release(reservation_id: int) -> None:
    now = db.utcnow()
    # Bumping the generation is what actually cuts the released device off:
    # its ubyhost_claim cookie names the generation it confirmed, and this one
    # no longer exists, so the next claimant's browser cannot restore access to
    # the browser that was just released.
    db.execute(
        "UPDATE reservation_claim SET state = ?, email = NULL, email_masked = NULL, "
        "token_hash = NULL, token_version = token_version + 1, "
        "provisional_until = NULL, claimed_at = NULL, "
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
    if not claim["email"]:
        # BE-3: the address was minimised away after the retention window, so
        # there is nobody to send the completion receipt to.
        return
    lang = claim["lang"] or "en"
    content = _guest_mail_content(
        "completion",
        apartment,
        reservation,
        lang=lang,
        stay_url=_stay_link(apartment, reservation),
    )
    payload = mail_notify.guest_payload(apartment, content, lang)
    mail.enqueue(
        kind="completion",
        idempotency_key=f"completion:{reservation['id']}:{progress['filled']}",
        to_email=claim["email"],
        # The host is copied on the receipt as well as being the reply address,
        # so the guest's own record of the stay reaches them either way.
        cc_email=payload.get("reply_to", ""),
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
        try:
            progress = reporting.reservation_progress(reservation)
        except db.DecryptionError:
            log.exception("reminder sweep skipped reservation_id=%s", reservation["id"])
            continue
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
            filled = progress["filled"]
            expected = progress["expected"]
            stay_url = (
                f"{config.PUBLIC_BASE_URL.rstrip('/')}/l/{reservation['permalink_token']}"
                f"/{reservation['id']}"
            )
            content = _guest_mail_content(
                "reminder_guest",
                reservation,
                reservation,
                lang=lang,
                stay_url=stay_url,
                filled=filled,
                expected=expected,
            )
            guest_payload = mail_notify.guest_payload(reservation, content, lang)
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
                    date=validation.fmt_date(reservation["date_from"]),
                    assigned=masked,
                    stay_url=(
                        f"{config.PUBLIC_BASE_URL.rstrip('/')}"
                        f"/reservations/{reservation['id']}"
                    ),
                    claimed=reservation["claim_state"] == CLAIMED,
                    filled=progress["filled"],
                    expected=progress["expected"],
                )
                host_payload = {
                    "text": host_content["text"],
                    "lang": mail_notify.HOST_MAIL_LANGUAGE,
                }
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
