"""Transactional mail: SQLite outbox plus a staging-safe console backend.

Production SES is intentionally not enabled in this rollout. Staging uses the
console backend so hosts can open claim links from Settings without AWS.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from email.utils import parseaddr
from typing import Any, Dict, List, Optional

from . import alerts, config, db, deadlines

log = logging.getLogger("ubyhost.mail")

QUEUED = "queued"
SENT = "sent"
FAILED = "failed"
BOUNCED = "bounced"
COMPLAINED = "complained"

KINDS = (
    "claim",
    "claim_resend",
    "reminder_host",
    "completion",
    "dates_changed",
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
        row = db.query_one(
            "SELECT id FROM email_outbox WHERE idempotency_key = ?",
            (idempotency_key,),
        )
        return int(row["id"]) if row else None


def _send_console(row) -> str:
    payload = json.loads(row["payload"] or "{}")
    body = payload.get("text") or ""
    db.insert(
        "console_mail_log",
        {
            "outbox_id": row["id"],
            "to_email": row["to_email"],
            "cc_email": row["cc_email"],
            "subject": row["subject"],
            "body_text": body,
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


def _send_ses(_row) -> str:
    raise MailConfigError("SES sending is not enabled in this staging rollout.")


def drain(limit: int = 8) -> Dict[str, int]:
    summary = {"sent": 0, "failed": 0, "skipped": 0}
    if not mail_enabled():
        return summary
    now = db.utcnow()
    rows = db.query(
        "SELECT * FROM email_outbox WHERE state = ? AND next_attempt_at <= ? "
        "ORDER BY id LIMIT ?",
        (QUEUED, now, limit),
    )
    for row in rows:
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
                    f"Guest e-mail could not be sent ({row['kind']}).",
                    f"To {mask_email(row['to_email'])}: {exc}",
                    dedupe_key=f"mail_failed:{row['id']}",
                    apartment_id=row["apartment_id"],
                    reservation_id=row["reservation_id"],
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


def recent_console_messages(owner_user_id: Optional[int], limit: int = 30) -> List[Any]:
    if owner_user_id is None:
        return db.query(
            "SELECT * FROM console_mail_log ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    return db.query(
        "SELECT l.* FROM console_mail_log l "
        "JOIN email_outbox o ON o.id = l.outbox_id "
        "WHERE o.owner_user_id IS ? "
        "ORDER BY l.id DESC LIMIT ?",
        (owner_user_id, limit),
    )


def extract_claim_secret(body: str) -> str:
    match = re.search(r"#c=([A-Za-z0-9_-]{16,})", body or "")
    return match.group(1) if match else ""
