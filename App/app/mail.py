"""Transactional mail: SQLite outbox plus console and SES backends.

Staging uses the console backend so hosts can open claim links from Settings
without AWS. Production may set ``UBYHOST_MAIL_BACKEND=ses`` after domain
verification and a signed-off deploy — see ``docs/SES.md``. Keep production on
``disabled`` until that flip.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from typing import Any, Dict, List, Optional

from . import alerts, config, db, deadlines

log = logging.getLogger("ubyhost.mail")

QUEUED = "queued"
SENDING = "sending"
SENT = "sent"
FAILED = "failed"
BOUNCED = "bounced"
COMPLAINED = "complained"

KINDS = (
    "claim",
    "claim_resend",
    "reminder_guest",
    "reminder_host",
    "completion",
    "submission_problem",
    "invoice_issued",
    "workspace_deletion",
    "cancelled_with_guests",
    "deadline_at_risk",
    "deadline_digest",
    "lifecycle_no_property",
    "lifecycle_no_calendar",
    "lifecycle_no_guest",
    # WP20 self sign-up: the verification link, the "you already have an
    # account" answer to a repeated sign-up, and the operator's notice.
    "signup_verify",
    "signup_exists",
    "signup_admin",
)

# The kinds addressed to a guest rather than to the host. A guest has no
# account and no way back into the app, so the one route they have is answering
# the mail — Reply-To has to reach the host who owns the stay, never UbyHost
# support. Everything here goes through ``mail_notify.guest_payload``, which
# sets it. A new kind added to ``KINDS`` has to be placed in exactly one of
# these two groups; ``test_mail.py`` fails until it is, so the next kind cannot
# quietly ship without Reply-To.
GUEST_KINDS = (
    "claim",
    "claim_resend",
    "reminder_guest",
    "completion",
    "invoice_issued",
)
HOST_KINDS = (
    "reminder_host",
    "submission_problem",
    "workspace_deletion",
    "cancelled_with_guests",
    # WP23 filing watchdog: the host's one warning per stay, and the operator's
    # digest. Neither goes to a guest.
    "deadline_at_risk",
    "deadline_digest",
    "lifecycle_no_property",
    "lifecycle_no_calendar",
    "lifecycle_no_guest",
    "signup_verify",
    "signup_exists",
    "signup_admin",
)
# The only kinds a host can unsubscribe from (WP12). Everything else is service
# mail about filings, stays or the account and ignores the opt-out flag.
LIFECYCLE_KINDS = (
    "lifecycle_no_property",
    "lifecycle_no_calendar",
    "lifecycle_no_guest",
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# A claim link's secret is the one thing a stored mail body must not contain.
# The body carries this marker where the secret belongs and the secret itself
# sits beside it in the payload, encrypted, so a send that has to be retried
# still has a working link to retry with while the 14 days the outbox and the
# console log live hold nothing anyone could use. The marker is deliberately
# not shaped like a secret, so a body that still has it in is obviously not a
# link rather than a subtly broken one.
CLAIM_SECRET_MARKER = "{{claim_secret}}"
CLAIM_SECRET_KEY = "claim_secret_enc"


class MailConfigError(RuntimeError):
    """Mail environment is unsafe to start."""


def normalise_email(raw: str) -> str:
    _name, addr = parseaddr((raw or "").strip())
    addr = addr.strip().lower()
    if not addr or not _EMAIL_RE.match(addr) or len(addr) > 254:
        return ""
    return addr


def mask_email(addr: str) -> str:
    addr = (addr or "").strip().lower()
    if "@" not in addr:
        return ""
    local, domain = addr.split("@", 1)
    if not local or not domain:
        return ""
    shown = local[0]
    stars = "*" * max(3, min(8, len(local) - 1))
    parts = domain.split(".")
    host = parts[0]
    rest = ".".join(parts[1:]) if len(parts) > 1 else ""
    host_mask = host[0] + ("*" * max(3, len(host) - 1))
    return f"{shown}{stars}@{host_mask}" + (f".{rest}" if rest else "")


def backend_name() -> str:
    return (config.MAIL_BACKEND or "disabled").strip().lower()


def mail_enabled() -> bool:
    return backend_name() in {"console", "ses"}


def validate_mail_env(
    *,
    backend: Optional[str] = None,
    deployment: Optional[str] = None,
) -> List[str]:
    """Refuse SES on non-production and incomplete production SES config."""
    name = (backend if backend is not None else backend_name()).lower()
    deploy = (deployment if deployment is not None else config.DEPLOYMENT).lower()
    warnings: List[str] = []
    if name not in {"disabled", "console", "ses"}:
        raise MailConfigError(
            f"UBYHOST_MAIL_BACKEND={name!r} is invalid (use disabled, console, or ses)."
        )
    if name == "ses" and deploy != "production":
        raise MailConfigError(
            "UBYHOST_MAIL_BACKEND=ses is only allowed on production Lightsail. "
            "Use console on staging so mock guests are never mailed through SES."
        )
    if name == "ses":
        missing = [
            key
            for key, value in (
                ("UBYHOST_SES_REGION", config.SES_REGION),
                ("UBYHOST_MAIL_FROM", config.MAIL_FROM),
                ("UBYHOST_AWS_ACCESS_KEY_ID", config.AWS_ACCESS_KEY_ID),
                ("UBYHOST_AWS_SECRET_ACCESS_KEY", config.AWS_SECRET_ACCESS_KEY),
            )
            if not value
        ]
        if missing:
            raise MailConfigError(
                "Production SES is selected but incomplete: " + ", ".join(missing)
            )
    if deploy == "production" and name == "console":
        warnings.append(
            "UBYHOST_MAIL_BACKEND=console on production — mail is logged, not delivered"
        )
    if deploy == "production" and name == "disabled":
        warnings.append("guest e-mail is disabled on production")
    return warnings


def enqueue(
    *,
    kind: str,
    idempotency_key: str,
    to_email: str,
    subject: str,
    payload: Dict[str, Any],
    reservation_id: Optional[int] = None,
    apartment_id: Optional[int] = None,
    owner_user_id: Optional[int] = None,
    cc_email: Optional[str] = None,
) -> Optional[int]:
    if kind not in KINDS:
        raise ValueError(f"unknown mail kind {kind}")
    if not mail_enabled():
        log.info("mail disabled; skip enqueue kind=%s key=%s", kind, idempotency_key)
        return None
    to_email = normalise_email(to_email)
    if not to_email:
        return None
    if kind in GUEST_KINDS and not normalise_email(str(payload.get("reply_to") or "")):
        # Not fatal: an entity with no contact address still has a guest waiting
        # for a link, and the mail is worth more than the rule. Loud enough that
        # a kind which forgot to route its answer anywhere shows up in the log.
        log.warning("guest mail has no reply_to kind=%s key=%s", kind, idempotency_key)
    now = db.utcnow()
    existing = db.query_one(
        "SELECT id, state FROM email_outbox WHERE idempotency_key = ?",
        (idempotency_key,),
    )
    if existing:
        return int(existing["id"])
    try:
        return db.insert(
            "email_outbox",
            {
                "idempotency_key": idempotency_key,
                "kind": kind,
                "reservation_id": reservation_id,
                "apartment_id": apartment_id,
                "owner_user_id": owner_user_id,
                "to_email": to_email,
                "cc_email": normalise_email(cc_email or "") or None,
                "subject": subject[:200],
                "payload": json.dumps(payload),
                "state": QUEUED,
                "attempts": 0,
                "next_attempt_at": now,
                "created_at": now,
                "updated_at": now,
            },
        )
    except Exception:
        log.exception("mail enqueue failed kind=%s key=%s", kind, idempotency_key)
        row = db.query_one(
            "SELECT id FROM email_outbox WHERE idempotency_key = ?",
            (idempotency_key,),
        )
        return int(row["id"]) if row else None


def _with_secret(value: str, payload: Dict[str, Any]) -> str:
    """Put the real claim secret back into one body part.

    Raises when the marker is present and the secret cannot be produced. A body
    still carrying the marker reads like a working link and is not one, and the
    guest is the one who finds that out.
    """
    if CLAIM_SECRET_MARKER not in value:
        return value
    token = payload.get(CLAIM_SECRET_KEY)
    if not token:
        raise db.DecryptionError("outbox payload has a claim link with no secret")
    return value.replace(CLAIM_SECRET_MARKER, db.decrypt_field(token))


def stored_body(payload: Dict[str, Any]) -> str:
    """The text part as it is stored: a claim link with its secret left out."""
    return payload.get("text") or ""


def stored_html(payload: Dict[str, Any]) -> str:
    """The HTML part as it is stored, subject to the same rule as the text."""
    return payload.get("html") or ""


def delivery_body(payload: Dict[str, Any]) -> str:
    """The text part as it goes out, with the real claim secret put back in.

    A body with no marker either never had a secret or was queued by the
    release before this one, and is passed through untouched.
    """
    return _with_secret(stored_body(payload), payload)


def delivery_html(payload: Dict[str, Any]) -> str:
    """The HTML part as it goes out. Empty when the mail has no HTML part.

    The secret is substituted here too, so a future HTML mail that carries a
    claim link cannot leak the marker into a delivered message.
    """
    return _with_secret(stored_html(payload), payload)


def _reveal_claim_secret(body: str, payload_json: Optional[str]) -> str:
    """Put the claim secret back for the owner reading the console log.

    Copying the link out of Settings is what the console backend is for on
    staging, so the secret has to come back. This is best-effort on purpose:
    Settings renders whatever the key situation is, so a secret that cannot be
    read leaves the marker standing instead of failing the page.
    """
    if CLAIM_SECRET_MARKER not in body:
        return body
    try:
        payload = json.loads(payload_json or "{}")
        token = payload.get(CLAIM_SECRET_KEY)
        if not token:
            return body
        return body.replace(CLAIM_SECRET_MARKER, db.decrypt_field(token))
    except (db.DecryptionError, ValueError):
        return body


def _send_console(row) -> str:
    payload = json.loads(row["payload"] or "{}")
    # Build the delivered form first: if the claim secret cannot be produced
    # this raises, and the row retries with an alert rather than leaving a log
    # entry that claims a link went out. What is written to the log is the
    # stored form, so the copy that lives for 14 days holds no working link.
    delivery_body(payload)
    delivery_html(payload)
    db.insert(
        "console_mail_log",
        {
            "outbox_id": row["id"],
            "to_email": row["to_email"],
            "cc_email": row["cc_email"],
            "subject": row["subject"],
            "body_text": stored_body(payload),
            "body_html": stored_html(payload) or None,
            "created_at": db.utcnow(),
        },
    )
    log.info(
        "console mail id=%s kind=%s to=%s subject=%s",
        row["id"],
        row["kind"],
        mask_email(row["to_email"]),
        row["subject"],
    )
    return f"console:{row['id']}"


def _ses_client():
    import boto3

    kwargs: Dict[str, Any] = {"region_name": config.SES_REGION or "eu-central-1"}
    if config.AWS_ACCESS_KEY_ID and config.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = config.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = config.AWS_SECRET_ACCESS_KEY
    return boto3.client("ses", **kwargs)


def _sesv2_client():
    """SES API v2. Only its SendEmail takes extra headers on a Simple message.

    The v1 SendEmail above has no header field, so the lifecycle tips, which
    need List-Unsubscribe, go through this one. Same IAM action
    (``ses:SendEmail``), same region and credentials.
    """
    import boto3

    kwargs: Dict[str, Any] = {"region_name": config.SES_REGION or "eu-central-1"}
    if config.AWS_ACCESS_KEY_ID and config.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = config.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = config.AWS_SECRET_ACCESS_KEY
    return boto3.client("sesv2", **kwargs)


def list_unsubscribe_headers(row, payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """RFC 2369 and RFC 8058 headers, for the lifecycle kinds only.

    Every other kind is service mail with nothing to unsubscribe from, so it
    never carries them. The URL must be https and printable ASCII (the SES v2
    header rules); anything else is dropped rather than sent broken.
    """
    url = str(payload.get("list_unsubscribe") or "")
    if row["kind"] not in LIFECYCLE_KINDS or not url.startswith("https://"):
        return []
    value = f"<{url}>"
    if len(value) > 995 or not all(32 <= ord(ch) < 127 for ch in value):
        return []
    return [
        {"Name": "List-Unsubscribe", "Value": value},
        {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"},
    ]


def display_from(address: Optional[str] = None) -> str:
    """The envelope From, with a readable name in front of the address.

    A bare address in the From line is one of the cheapest ways to look like
    bulk mail, and it reads badly in a guest's inbox. If the configured value
    already carries a name, it is passed through untouched so an operator who
    set one keeps it.
    """
    value = (address if address is not None else config.MAIL_FROM) or ""
    value = value.strip()
    if not value or "<" in value or "@" not in value:
        return value
    return f"UbyHost <{value}>"


def _send_ses(row) -> str:
    """Deliver one outbox row through Amazon SES SendEmail (v2 for lifecycle tips)."""
    if backend_name() != "ses":
        raise MailConfigError("SES sender invoked while UBYHOST_MAIL_BACKEND is not ses.")
    if not config.MAIL_FROM:
        raise MailConfigError("UBYHOST_MAIL_FROM is required for SES sending.")

    payload = json.loads(row["payload"] or "{}")
    body = delivery_body(payload)
    html = delivery_html(payload)
    reply_to = normalise_email(str(payload.get("reply_to") or ""))

    destination: Dict[str, List[str]] = {"ToAddresses": [row["to_email"]]}
    cc = normalise_email(row["cc_email"] or "")
    if cc:
        destination["CcAddresses"] = [cc]

    ses_body: Dict[str, Dict[str, str]] = {"Text": {"Data": body, "Charset": "UTF-8"}}
    if html:
        # A multipart/alternative message: the client picks the HTML part and
        # falls back to the text part. The text part is never dropped, so a
        # client that refuses HTML still gets the whole message including the
        # link.
        ses_body["Html"] = {"Data": html, "Charset": "UTF-8"}

    kwargs: Dict[str, Any] = {
        "Source": display_from(),
        "Destination": destination,
        "Message": {
            "Subject": {"Data": row["subject"] or "", "Charset": "UTF-8"},
            "Body": ses_body,
        },
    }
    if reply_to:
        kwargs["ReplyToAddresses"] = [reply_to]

    headers = list_unsubscribe_headers(row, payload)
    if headers:
        v2: Dict[str, Any] = {
            "FromEmailAddress": kwargs["Source"],
            "Destination": destination,
            "Content": {
                "Simple": {
                    "Subject": kwargs["Message"]["Subject"],
                    "Body": ses_body,
                    "Headers": headers,
                }
            },
        }
        if reply_to:
            v2["ReplyToAddresses"] = [reply_to]
        response = _sesv2_client().send_email(**v2)
    else:
        response = _ses_client().send_email(**kwargs)
    message_id = (response or {}).get("MessageId") or ""
    if not message_id:
        raise MailConfigError("SES SendEmail returned no MessageId.")
    log.info(
        "ses mail id=%s kind=%s to=%s message_id=%s",
        row["id"],
        row["kind"],
        mask_email(row["to_email"]),
        message_id,
    )
    return message_id


def drain(limit: int = 8) -> Dict[str, int]:
    summary = {"sent": 0, "failed": 0, "skipped": 0}
    if not mail_enabled():
        return summary
    now = db.utcnow()
    stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).replace(microsecond=0).isoformat()
    db.execute(
        "UPDATE email_outbox SET state = ? WHERE state = ? AND updated_at < ?",
        (QUEUED, SENDING, stale),
    )
    rows = db.query(
        "SELECT * FROM email_outbox WHERE state = ? AND next_attempt_at <= ? "
        "ORDER BY id LIMIT ?",
        (QUEUED, now, limit),
    )
    for row in rows:
        if not db.update_if(
            "email_outbox", row["id"], {"state": SENDING, "updated_at": db.utcnow()}, {"state": QUEUED}
        ):
            continue  # another drain took it
        try:
            provider_id = _send_console(row) if backend_name() == "console" else _send_ses(row)
            db.update(
                "email_outbox",
                row["id"],
                {
                    "state": SENT,
                    "provider_id": provider_id,
                    "sent_at": db.utcnow(),
                    "updated_at": db.utcnow(),
                    "last_error": None,
                    "attempts": int(row["attempts"] or 0) + 1,
                },
            )
            summary["sent"] += 1
        except Exception as exc:
            attempts = int(row["attempts"] or 0) + 1
            delay = min(6 * 60 * 60, 60 * (2 ** min(attempts, 8)))
            terminal = attempts >= 8
            db.update(
                "email_outbox",
                row["id"],
                {
                    "state": FAILED if terminal else QUEUED,
                    "attempts": attempts,
                    "last_error": str(exc)[:400],
                    "next_attempt_at": (
                        datetime.utcnow() + timedelta(seconds=delay)
                    ).replace(microsecond=0).isoformat()
                    + "Z",
                    "updated_at": db.utcnow(),
                },
            )
            summary["failed" if terminal else "skipped"] += 1
            if terminal:
                alerts.raise_alert(
                    "warning",
                    "mail_failed",
                    f"E-mail could not be sent ({row['kind']}).",
                    f"To {mask_email(row['to_email'])}: {exc}",
                    dedupe_key=f"mail_failed:{row['id']}",
                    apartment_id=row["apartment_id"],
                    reservation_id=row["reservation_id"],
                    params={
                        "kind": row["kind"],
                        "to": mask_email(row["to_email"]),
                        "error": str(exc),
                    },
                )
    return summary


def purge_old(days: int = 14) -> int:
    cutoff = (deadlines.local_now() - timedelta(days=days)).isoformat()
    rows = db.query(
        "SELECT id FROM email_outbox WHERE state IN (?, ?, ?, ?) AND updated_at < ?",
        (SENT, FAILED, BOUNCED, COMPLAINED, cutoff),
    )
    count = 0
    for row in rows:
        db.execute("DELETE FROM email_outbox WHERE id = ?", (row["id"],))
        count += 1
    db.execute("DELETE FROM console_mail_log WHERE created_at < ?", (cutoff,))
    return count


def recent_console_messages(
    owner_user_id: Optional[int], limit: int = 30
) -> List[Dict[str, Any]]:
    """Recent console messages, with any claim link made usable again.

    The stored body keeps the secret out, so it has to be put back for the
    owner. Rows carry their outbox payload alongside so that needs no second
    query; the LEFT JOIN on the platform-admin branch is there only to fetch
    that payload and filters nothing out. Both body parts are revealed: the
    HTML one is what the host previews, so a marker left standing there would
    be the same broken link in a nicer wrapper.
    """
    columns = "l.*, o.payload AS outbox_payload"
    if owner_user_id is None:
        rows = db.query(
            f"SELECT {columns} FROM console_mail_log l "
            "LEFT JOIN email_outbox o ON o.id = l.outbox_id "
            "ORDER BY l.id DESC LIMIT ?",
            (limit,),
        )
    else:
        rows = db.query(
            f"SELECT {columns} FROM console_mail_log l "
            "JOIN email_outbox o ON o.id = l.outbox_id "
            f"WHERE {db.null_safe_eq('o.owner_user_id')} "
            "ORDER BY l.id DESC LIMIT ?",
            (owner_user_id, limit),
        )
    messages = []
    for row in rows:
        item = dict(row)
        payload_json = item.pop("outbox_payload", None)
        item["body_text"] = _reveal_claim_secret(
            item.get("body_text") or "", payload_json
        )
        item["body_html"] = _reveal_claim_secret(
            item.get("body_html") or "", payload_json
        )
        messages.append(item)
    return messages


def extract_claim_secret(body: str) -> str:
    match = re.search(r"#c=([A-Za-z0-9_-]{16,})", body or "")
    return match.group(1) if match else ""
