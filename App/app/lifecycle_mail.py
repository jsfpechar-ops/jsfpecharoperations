"""Three lifecycle tips to hosts who stalled during setup (WP12, review 5.5).

* ``lifecycle_no_property``: no property 3 days after the first login;
* ``lifecycle_no_calendar``: no calendar 3 days after the first property;
* ``lifecycle_no_guest``: no completed guest 14 days after the first calendar
  connected (status ok).

Each goes through the existing outbox at most once per account. The
``lifecycle_mail_sent`` row is claimed before the mail is queued, so two runs
cannot both send. A tip is only sent while its condition still holds, and not
at all for a stall older than ``MAX_LATE_DAYS`` past the due point, so turning
the switch on does not mail every dormant account at once.

Off unless ``UBYHOST_LIFECYCLE_MAIL=1``. Built to the standard of section 7(3)
of Czech Act 480/2004 (legal position 2): the host can refuse at sign-up, in
Settings and with the link in every tip; every tip names the sender.

Two things stop a tip. ``user_account.onboarding_emails_opt_out`` is the
account's own choice (Settings, sign-up, the unsubscribe link). The
``mail_suppression`` table keeps a keyed hash of every address that used the
unsubscribe link (scope ``onboarding``), so the refusal also holds for that
address on another account or after the workspace is deleted. Both are read
only here: filing problems, reminders, invoices and account notices are
service mail and keep going out.

The unsubscribe link carries a signed token (itsdangerous, the app's secret
key, its own salt) with the account id and the hash of the recipient address.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from itsdangerous import BadSignature, URLSafeSerializer

from . import config, db, mail, mail_notify

log = logging.getLogger("ubyhost.lifecycle_mail")

# (kind, days after the anchor). The anchor SQL is in ``_CANDIDATE_SQL``.
TRIGGERS = (
    ("lifecycle_no_property", 3),
    ("lifecycle_no_calendar", 3),
    ("lifecycle_no_guest", 14),
)
MAX_LATE_DAYS = 30
# The daily check waits for the working day, so a tip never lands at midnight.
SEND_HOUR_LOCAL = 9
LAST_RUN_KEY = "lifecycle_mail_last_day"
SUPPRESSION_SCOPE = "onboarding"

_FIRST_LOGIN = (
    "COALESCE((SELECT MIN(au.at) FROM audit au WHERE au.owner_user_id = u.id "
    "AND au.action IN ('login', 'two_factor_login')), u.last_login_at)"
)
_FIRST_PROPERTY = "(SELECT MIN(a.created_at) FROM apartment a WHERE a.owner_user_id = u.id)"
_FIRST_CALENDAR = (
    "(SELECT MIN(f.created_at) FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id "
    "WHERE a.owner_user_id = u.id AND f.last_status = 'ok')"
)

# Per kind: the anchor timestamp, and the condition that makes the tip moot.
_RULES = {
    "lifecycle_no_property": (
        _FIRST_LOGIN,
        "NOT EXISTS (SELECT 1 FROM apartment a WHERE a.owner_user_id = u.id)",
    ),
    "lifecycle_no_calendar": (
        _FIRST_PROPERTY,
        "NOT EXISTS (SELECT 1 FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id "
        "WHERE a.owner_user_id = u.id AND f.active = 1)",
    ),
    "lifecycle_no_guest": (
        _FIRST_CALENDAR,
        "NOT EXISTS (SELECT 1 FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
        "WHERE a.owner_user_id = u.id AND r.registration_completed_at IS NOT NULL)",
    ),
}


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _serializer() -> URLSafeSerializer:
    # No expiry: an unsubscribe link has to keep working for as long as the
    # mail sits in an inbox. Built on use, like invoice_links, because the key
    # may not exist yet at import time.
    return URLSafeSerializer(config.secret_key(), salt="ubyhost-lifecycle-unsubscribe")


def email_hash(address: str) -> str:
    """Keyed digest of the normalised address, as stored in ``mail_suppression``.

    Keyed with the app secret like ``auth.recovery_code_hash``, so the table
    cannot be matched against a list of known addresses. "" for a non-address.
    """
    normalised = mail.normalise_email(address)
    if not normalised:
        return ""
    return hmac.new(
        config.secret_key().encode(),
        f"mail-suppression\0{normalised}".encode(),
        hashlib.sha256,
    ).hexdigest()


def unsubscribe_token(user_id: int, address: str = "") -> str:
    return _serializer().dumps({"u": int(user_id), "h": email_hash(address)})


def read_unsubscribe_token(token: str) -> Optional[Dict[str, object]]:
    """``{"u": account id, "h": address hash or ""}``, or None when forged."""
    try:
        data = _serializer().loads(token)
    except BadSignature:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("u"), int):
        return None
    digest = data.get("h") or ""
    if not isinstance(digest, str):
        return None
    return {"u": data["u"], "h": digest}


def unsubscribe_url(user_id: int, address: str, lang: str) -> str:
    return f"{config.PUBLIC_BASE_URL}/mail/unsubscribe/{unsubscribe_token(user_id, address)}?lang={lang}"


def set_opt_out(user_id: int, opted_out: bool, *, actor: str) -> bool:
    """Record the account's choice. True when the account exists; idempotent."""
    row = db.query_one(
        "SELECT id, onboarding_emails_opt_out FROM user_account WHERE id = ?", (user_id,)
    )
    if not row:
        return False
    if bool(row["onboarding_emails_opt_out"]) != opted_out:
        db.execute(
            "UPDATE user_account SET onboarding_emails_opt_out = ?, "
            "onboarding_emails_opt_out_at = ? WHERE id = ?",
            (1 if opted_out else 0, db.utcnow(), user_id),
        )
        db.audit(
            "onboarding_emails_opted_out" if opted_out else "onboarding_emails_opted_in",
            actor=actor,
            owner_user_id=user_id,
        )
    return True


def suppress(digest: str) -> None:
    if not digest:
        return
    db.execute(
        "INSERT INTO mail_suppression (email_hash, scope, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT (email_hash, scope) DO NOTHING",
        (digest, SUPPRESSION_SCOPE, db.utcnow()),
    )


def is_suppressed(address: str) -> bool:
    digest = email_hash(address)
    return bool(
        digest
        and db.query_one(
            "SELECT 1 AS x FROM mail_suppression WHERE email_hash = ? AND scope = ?",
            (digest, SUPPRESSION_SCOPE),
        )
    )


def unsubscribe(user_id: int, digest: str = "") -> bool:
    """The link in a tip: suppress the address and set the account flag."""
    if not db.query_one("SELECT 1 AS x FROM user_account WHERE id = ?", (user_id,)):
        return False
    suppress(digest)
    set_opt_out(user_id, True, actor="unsubscribe_link")
    return True


def resubscribe(user_id: int, *, actor: str) -> bool:
    """The host turned tips back on in Settings.

    That is a fresh choice by the account holder, so the suppression rows for
    the workspace's current contact addresses go too; otherwise the toggle
    would say on while nothing could ever be sent.
    """
    if not set_opt_out(user_id, False, actor=actor):
        return False
    for address in mail_notify.workspace_contact_emails(user_id):
        db.execute(
            "DELETE FROM mail_suppression WHERE email_hash = ? AND scope = ?",
            (email_hash(address), SUPPRESSION_SCOPE),
        )
    return True


def is_opted_out(user_id: int) -> bool:
    row = db.query_one(
        "SELECT onboarding_emails_opt_out FROM user_account WHERE id = ?", (user_id,)
    )
    return bool(row and row["onboarding_emails_opt_out"])


def sender_identified() -> bool:
    """Every tip names the sender (company, IČO, address); no tip without them."""
    return bool(config.OPERATOR_NAME and config.OPERATOR_ICO and config.OPERATOR_ADDRESS)


def candidates(kind: str, now: Optional[datetime] = None) -> List[int]:
    """Host accounts due for ``kind`` right now. One aggregate query."""
    anchor, moot = _RULES[kind]
    days = dict(TRIGGERS)[kind]
    moment = now or datetime.now(timezone.utc)
    due_before = _iso(moment - timedelta(days=days))
    too_late_before = _iso(moment - timedelta(days=days + MAX_LATE_DAYS))
    rows = db.query(
        f"SELECT u.id FROM user_account u WHERE u.role = 'host' AND u.active = 1 "
        "AND u.deletion_due_at IS NULL AND COALESCE(u.onboarding_emails_opt_out, 0) = 0 "
        "AND NOT EXISTS (SELECT 1 FROM lifecycle_mail_sent m "
        "WHERE m.user_account_id = u.id AND m.kind = ?) "
        f"AND {moot} "
        f"AND {anchor} <= ? AND {anchor} >= ? "
        "ORDER BY u.id LIMIT 500",
        (kind, due_before, too_late_before),
    )
    return [int(row["id"]) for row in rows]


def _claim(user_id: int, kind: str) -> bool:
    """Write the sent marker first; False when another run already did."""
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO lifecycle_mail_sent (user_account_id, kind, sent_at) VALUES (?, ?, ?) "
            "ON CONFLICT (user_account_id, kind) DO NOTHING",
            (user_id, kind, db.utcnow()),
        )
        return cur.rowcount == 1


def _release(user_id: int, kind: str) -> None:
    db.execute(
        "DELETE FROM lifecycle_mail_sent WHERE user_account_id = ? AND kind = ?",
        (user_id, kind),
    )


def send_one(user_id: int, kind: str) -> int:
    """Queue ``kind`` to every contact address of the account. Returns how many."""
    if is_opted_out(user_id):
        return 0
    addresses = [
        address
        for address in mail_notify.workspace_contact_emails(user_id)
        if not is_suppressed(address)
    ]
    if not addresses:
        # Nowhere to send yet. No marker, so a later run can still reach them.
        return 0
    if not _claim(user_id, kind):
        return 0
    lang = mail_notify.HOST_MAIL_LANGUAGE
    queued = 0
    for address in addresses:
        link = unsubscribe_url(user_id, address, lang)
        content = mail_notify.build_lifecycle(kind, unsubscribe_url=link, lang=lang)
        payload = {
            "text": content["text"],
            "html": content["html"],
            "lang": lang,
            "reply_to": config.OPERATOR_EMAIL,
            # mail._send_ses turns this into List-Unsubscribe and
            # List-Unsubscribe-Post for the lifecycle kinds only.
            "list_unsubscribe": link,
        }
        if mail.enqueue(
            kind=kind,
            idempotency_key=f"lifecycle:{kind}:{user_id}:{address}",
            to_email=address,
            subject=content["subject"],
            payload=payload,
            owner_user_id=user_id,
        ):
            queued += 1
    if not queued:
        _release(user_id, kind)
    return queued


def run(now: Optional[datetime] = None) -> Dict[str, int]:
    """Evaluate every trigger once. Does nothing while the switch is off."""
    summary = {kind: 0 for kind, _days in TRIGGERS}
    if not config.LIFECYCLE_MAIL or not mail.mail_enabled():
        return {}
    if not sender_identified():
        log.warning("lifecycle mail skipped: UBYHOST_OPERATOR_NAME, _ICO or _ADDRESS is empty")
        return {}
    for kind, _days in TRIGGERS:
        for user_id in candidates(kind, now):
            try:
                if send_one(user_id, kind):
                    summary[kind] += 1
            except Exception:
                log.exception("lifecycle mail failed kind=%s user=%s", kind, user_id)
    return summary


def run_daily(now: Optional[datetime] = None) -> Dict[str, int]:
    """The mail job's step: at most one ``run`` per local day, after 09:00."""
    if not config.LIFECYCLE_MAIL or not mail.mail_enabled():
        return {}
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(config.TIMEZONE))
    today = local.date().isoformat()
    if local.hour < SEND_HOUR_LOCAL or db.get_setting(LAST_RUN_KEY) == today:
        return {}
    db.set_setting(LAST_RUN_KEY, today)
    return run(now)
