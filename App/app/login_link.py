"""Log in with a link sent by e-mail (task 0003).

The flow:

1. ``POST /login`` takes an e-mail address. If an active account logs in with
   it, a link is minted here and mailed at once. The page shown afterwards is
   the same whether or not the address has an account.
2. The link opens ``GET /login/link``, a page with one "Log in" button. Opening
   the link changes nothing, so a mail scanner that fetches every link in a
   message cannot spend it.
3. The button posts the secret back. ``consume`` spends it exactly once, and
   the route starts the session (or asks for the authenticator code first, for
   a host who switched that on).

The secret is 32 random bytes. Only its SHA-256 is stored; the mail body in
the outbox carries ``mail.CLAIM_SECRET_MARKER`` in its place. Sending a new
link for the same account and purpose retires the older ones.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from . import db, rate_limit

LOGIN = "login"
INVITE = "invite"
EMAIL_CHANGE = "email_change"
PURPOSES = (LOGIN, INVITE, EMAIL_CHANGE)

# How long a link works. A login link is short: it is used within minutes or
# not at all. An invitation waits for a host who may read mail once a day.
TTL_SECONDS = {
    LOGIN: 15 * 60,
    INVITE: 72 * 60 * 60,
    EMAIL_CHANGE: 60 * 60,
}

# Budgets. Per address: at most 3 links in 15 minutes and 10 a day, whoever
# asks, so the form cannot be used to flood someone's inbox. Per connection:
# 10 requests in 15 minutes, which still lets a shared office try a few times.
_WINDOW = 15 * 60
_DAY = 24 * 60 * 60
EMAIL_MAX_WINDOW = 3
EMAIL_MAX_DAY = 10
IP_MAX_WINDOW = 10
# Wrong or spent links posted from one connection before it is refused.
CONSUME_FAIL_MAX = 20

# Rows are deleted this long after they expire (retention.py).
PURGE_AFTER = timedelta(days=1)


def _hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue(
    account: Any,
    *,
    purpose: str = LOGIN,
    email: Optional[str] = None,
    remember: bool = False,
    next_path: str = "/",
) -> str:
    """Mint a link secret for ``account`` and return it. Never stored in clear."""
    if purpose not in PURPOSES:
        raise ValueError(f"unknown purpose {purpose}")
    address = (email or account["email"] or "").strip().lower()
    if not address:
        raise ValueError("account has no login e-mail")
    token = secrets.token_urlsafe(32)
    now = _now()
    # Only the newest link per account and purpose works.
    db.execute(
        "UPDATE login_token SET used_at = ? WHERE user_account_id = ? AND purpose = ? "
        "AND used_at IS NULL",
        (_iso(now), int(account["id"]), purpose),
    )
    db.insert(
        "login_token",
        {
            "token_hash": _hash(token),
            "user_account_id": int(account["id"]),
            "purpose": purpose,
            "email": address,
            "remember": 1 if remember else 0,
            "next_path": next_path or "/",
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(seconds=TTL_SECONDS[purpose])),
        },
    )
    return token


def peek(token: str, purposes: tuple = (LOGIN, INVITE)):
    """The live row behind ``token``, or None. Changes nothing (the GET page)."""
    if not token or len(token) > 200:
        return None
    row = db.query_one(
        "SELECT * FROM login_token WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
        (_hash(token), _iso(_now())),
    )
    if not row or row["purpose"] not in purposes:
        return None
    return row


def consume(token: str, purposes: tuple = (LOGIN, INVITE)):
    """Spend ``token`` once. The row it was, or None if it was not live.

    Two tabs posting the same link at the same moment cannot both win: the
    UPDATE only succeeds while ``used_at`` is still empty.
    """
    row = peek(token, purposes)
    if not row:
        return None
    now = _iso(_now())
    if not db.update_if(
        "login_token",
        row["id"],
        {"used_at": now},
        {"used_at": None},
        extra_where="expires_at > ?",
        extra_params=(now,),
    ):
        return None
    return row


def account_for(row):
    """The active account a spent row logs into, if its address still matches."""
    if not row:
        return None
    account = db.query_one(
        "SELECT * FROM user_account WHERE id = ? AND active = 1", (int(row["user_account_id"]),)
    )
    if not account:
        return None
    if row["purpose"] != EMAIL_CHANGE and (account["email"] or "").strip().lower() != row["email"]:
        return None
    return account


def request_blocked(ip_key: str, email: str) -> bool:
    if rate_limit.blocked("login_link_ip", ip_key, IP_MAX_WINDOW, _WINDOW):
        return True
    if not email:
        return False
    return rate_limit.blocked(
        "login_link_email", email, EMAIL_MAX_WINDOW, _WINDOW
    ) or rate_limit.blocked("login_link_email_day", email, EMAIL_MAX_DAY, _DAY)


def record_request(ip_key: str, email: str) -> None:
    rate_limit.record("login_link_ip", ip_key)
    if email:
        rate_limit.record("login_link_email", email)
        rate_limit.record("login_link_email_day", email)


def consume_blocked(ip_key: str) -> bool:
    return rate_limit.blocked("login_link_bad", ip_key, CONSUME_FAIL_MAX, _WINDOW)


def record_consume_failure(ip_key: str) -> None:
    rate_limit.record("login_link_bad", ip_key)


def purge(now: Optional[datetime] = None, dry_run: bool = False) -> int:
    """Delete rows that expired more than a day ago. Returns how many."""
    cutoff = _iso((now or _now()) - PURGE_AFTER)
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM login_token WHERE expires_at < ?", (cutoff,)
    )
    count = int(row["n"]) if row else 0
    if count and not dry_run:
        db.execute("DELETE FROM login_token WHERE expires_at < ?", (cutoff,))
    return count
