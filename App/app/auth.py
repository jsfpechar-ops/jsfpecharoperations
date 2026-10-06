"""Host accounts, sessions, and workspace impersonation.

Hosts log in with a link sent to their login e-mail (``login_link``), or with
a passkey (task 0004). There are no passwords. An authenticator app (TOTP) is
an optional second step after the e-mail link. Guest links remain
account-free: their random apartment token and PIN are the boundary for the
legal registration flow.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
import pyotp

from . import acceptance, config, db, host_i18n

SESSION_COOKIE = "ubyhost_session"
SESSION_MAX_AGE = 60 * 60 * 12
SESSION_REMEMBER_MAX_AGE = 60 * 60 * 24 * 30
TWO_FACTOR_PENDING_MAX_AGE = 10 * 60
# An admin inside a host's workspace is sent back to their own view after this
# long. The start time travels in the signed session payload ("ast"). Set
# UBYHOST_IMPERSONATION_MAX_HOURS=0 for no limit (operator policy).
def _impersonation_max_age() -> int:
    raw = os.environ.get("UBYHOST_IMPERSONATION_MAX_HOURS", "24").strip()
    if raw in ("0", ""):
        return 0
    try:
        hours = int(raw)
    except ValueError:
        hours = 24
    return max(0, hours) * 3600


IMPERSONATION_MAX_AGE = _impersonation_max_age()
# Guests whose identity the admin revealed in this impersonation ("rv"). The
# cap keeps the cookie small; a reveal past it drops the oldest entry.
MAX_REVEALED_GUESTS = 50
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.secret_key(), salt="ubyhost-session")


def _two_factor_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.secret_key(), salt="ubyhost-2fa-pending")


def issue_two_factor_pending(user_id: int, remember: bool = False, next_path: str = "/") -> str:
    return _two_factor_serializer().dumps(
        {"uid": int(user_id), "rm": bool(remember), "next": next_path}
    )


def read_two_factor_pending(token: str) -> Optional[dict[str, Any]]:
    try:
        payload = _two_factor_serializer().loads(token, max_age=TWO_FACTOR_PENDING_MAX_AGE)
        return payload if isinstance(payload, dict) and payload.get("uid") else None
    except BadSignature:
        return None


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="UbyHost")


def recovery_code_hash(code: str) -> str:
    normalized = (code or "").replace("-", "").replace(" ", "").upper()
    return hmac.new(
        config.secret_key().encode(), normalized.encode(), hashlib.sha256
    ).hexdigest()


def new_recovery_codes(count: int = 8) -> list[str]:
    return [f"{secrets.token_hex(4)[:4]}-{secrets.token_hex(4)[:4]}".upper() for _ in range(count)]


def enable_totp(user_id: int, secret: str, recovery_codes: list[str]) -> None:
    db.execute(
        "UPDATE user_account SET totp_secret_enc = ?, totp_enabled = 1, "
        "recovery_codes_hash = ?, totp_last_step = NULL, "
        "session_version = session_version + 1 WHERE id = ?",
        (
            db.encrypt_secret(secret),
            json.dumps([recovery_code_hash(code) for code in recovery_codes]),
            user_id,
        ),
    )


def stage_totp(user_id: int, secret: str) -> None:
    # A new secret invalidates the old device, so the old replay watermark goes
    # with it: otherwise the first code from the new phone could be refused as
    # a step the (now useless) old secret already spent.
    db.execute(
        "UPDATE user_account SET totp_secret_enc = ?, totp_enabled = 0, "
        "totp_last_step = NULL WHERE id = ?",
        (db.encrypt_secret(secret), user_id),
    )


def reset_totp(user_id: int) -> None:
    db.execute(
        "UPDATE user_account SET totp_secret_enc = NULL, totp_enabled = 0, "
        "recovery_codes_hash = NULL, totp_last_step = NULL, "
        "session_version = session_version + 1 WHERE id = ?",
        (user_id,),
    )


def verify_second_factor(account, code: str) -> bool:
    # Strip every kind of whitespace, including the NBSP a phone's keyboard or
    # an e-mail client inserts, the same way spaces are stripped. What is left
    # must be ASCII: ``hmac.compare_digest`` raises TypeError on non-ASCII
    # input, and a pasted full-width digit must count as a failed attempt (and
    # feed the per-account lockout) rather than surface as an HTTP 500.
    normalized = re.sub(r"\s+", "", code or "")
    if not normalized.isascii():
        return False
    try:
        secret = db.decrypt_secret(account["totp_secret_enc"])
    except Exception:
        return False
    if secret and normalized:
        totp = pyotp.TOTP(secret)
        current = int(time.time() // totp.interval)
        for step in (current - 1, current, current + 1):
            if hmac.compare_digest(totp.at(step * totp.interval), normalized):
                # Accept each time step once: a code seen over someone's
                # shoulder cannot be replayed within its 90-second window.
                return db.update_if(
                    "user_account",
                    account["id"],
                    {"totp_last_step": step},
                    {},
                    extra_where="(totp_last_step IS NULL OR totp_last_step < ?)",
                    extra_params=(step,),
                )
    candidate = recovery_code_hash(normalized)
    try:
        hashes = json.loads(account["recovery_codes_hash"] or "[]")
    except ValueError:
        hashes = []
    for stored in hashes:
        if hmac.compare_digest(candidate, stored):
            hashes.remove(stored)
            # Only the request that still sees the old list may spend it.
            return db.update_if(
                "user_account",
                account["id"],
                {"recovery_codes_hash": json.dumps(hashes)},
                {"recovery_codes_hash": account["recovery_codes_hash"]},
            )
    return False


def normalise_username(value: str) -> str:
    return (value or "").strip().lower()


def username_is_valid(value: str) -> bool:
    return bool(_USERNAME_RE.fullmatch(normalise_username(value)))


def accounts_exist() -> bool:
    return bool(db.query_one("SELECT id FROM user_account LIMIT 1"))


def new_username(email: str) -> str:
    """An internal handle for a new account, derived from its e-mail.

    Hosts never type it: they log in with the e-mail. It names the account in
    the audit log, which so keeps no e-mail address.
    """
    local = (email or "").split("@", 1)[0].lower()
    local = re.sub(r"[^a-z0-9._-]", "", local)
    base = re.sub(r"^[^a-z0-9]+", "", local)[:20] or "host"
    for _ in range(20):
        candidate = f"{base}-{secrets.token_hex(2)}"
        if username_is_valid(candidate) and not db.query_one(
            "SELECT id FROM user_account WHERE username = ?", (candidate,)
        ):
            return candidate
    return f"host-{secrets.token_hex(6)}"


def account_by_email(email: str):
    """The active account that logs in with ``email``, or None."""
    if not email:
        return None
    return db.query_one(
        "SELECT * FROM user_account WHERE email = ? AND active = 1", (email,)
    )


def issue_session(
    user_id: int,
    session_version: int,
    workspace_user_id: Optional[int] = None,
    remember: bool = False,
    impersonation_started_at: Optional[int] = None,
    revealed_guest_ids: Optional[list[int]] = None,
) -> str:
    payload: dict[str, Any] = {"uid": int(user_id), "sv": int(session_version)}
    if remember:
        payload["rm"] = 1
    if workspace_user_id and workspace_user_id != user_id:
        payload["as"] = int(workspace_user_id)
        payload["ast"] = int(
            impersonation_started_at
            if impersonation_started_at is not None
            else time.time()
        )
        if revealed_guest_ids:
            unique: list[int] = []
            for guest_id in revealed_guest_ids:
                if int(guest_id) not in unique:
                    unique.append(int(guest_id))
            payload["rv"] = unique[-MAX_REVEALED_GUESTS:]
    return _serializer().dumps(payload)


def session_max_age(payload: Optional[dict[str, Any]]) -> int:
    if payload and payload.get("rm"):
        return SESSION_REMEMBER_MAX_AGE
    return SESSION_MAX_AGE


def _session_payload(token: Optional[str]) -> Optional[dict[str, Any]]:
    if not token:
        return None
    try:
        payload = _serializer().loads(token, max_age=SESSION_REMEMBER_MAX_AGE)
        if not isinstance(payload, dict):
            return None
        # Non-remember sessions expire with the shorter cookie lifetime even
        # though the signed payload could otherwise be replayed for 30 days.
        if not payload.get("rm"):
            try:
                _serializer().loads(token, max_age=SESSION_MAX_AGE)
            except BadSignature:
                return None
        return payload
    except BadSignature:
        return None
    except Exception:
        return None


def current_user(request: Request):
    cached = getattr(request.state, "user_account", None)
    if cached is not None:
        return cached
    payload = _session_payload(request.cookies.get(SESSION_COOKIE))
    if not payload or not payload.get("uid"):
        return None
    account = db.query_one(
        "SELECT * FROM user_account WHERE id = ? AND active = 1",
        (payload["uid"],),
    )
    if not account or int(account["session_version"]) != int(payload.get("sv", 0)):
        return None
    request.state.user_account = account
    request.state.session_payload = payload
    return account


def workspace_user(request: Request):
    account = current_user(request)
    if not account:
        return None
    payload = getattr(request.state, "session_payload", {}) or {}
    target_id = payload.get("as")
    if target_id and account["role"] == "admin":
        if impersonation_expired(payload):
            # The admin is back in their own view from this request on;
            # require_login writes the stop row and replaces the cookie.
            request.state.impersonation_expired_for = int(target_id)
            return account
        target = db.query_one(
            "SELECT * FROM user_account WHERE id = ? AND active = 1", (target_id,)
        )
        if target:
            return target
    return account


SUPPORT_REASON_MIN = 5
SUPPORT_REASON_MAX = 300


def support_reason(value) -> Optional[str]:
    """A reason for opening a workspace or revealing a guest, or None.

    Whitespace (including line breaks) is folded to single spaces so the
    reason sits on one line of the audit detail. 5 to 300 characters.
    """
    text = " ".join(str(value or "").split())
    if not SUPPORT_REASON_MIN <= len(text) <= SUPPORT_REASON_MAX:
        return None
    return text


def impersonation_audit_reason(value) -> str:
    """Reason stored when an admin opens a workspace or reveals a guest.

    Optional in the UI: empty or too short values become ``support`` so support
    is not blocked on a mandatory form field.
    """
    return support_reason(value) or "support"


def impersonation_expired(payload: Optional[dict[str, Any]]) -> bool:
    """True once an impersonation has run for IMPERSONATION_MAX_AGE.

    A payload with "as" but no usable start time (one issued before the limit
    existed) counts as expired, so every session inside a host's workspace has
    a reason and a clock. When IMPERSONATION_MAX_AGE is 0, never expires.
    """
    if IMPERSONATION_MAX_AGE <= 0:
        return False
    if not payload or not payload.get("as"):
        return False
    started = payload.get("ast")
    if not isinstance(started, int) or isinstance(started, bool):
        return True
    return time.time() - started >= IMPERSONATION_MAX_AGE


def impersonating(request: Request) -> bool:
    """Whether the signed-in admin is looking at another account's workspace.

    Cached on the request: templates ask once per guest row, and the answer
    cannot change while one request is being served.
    """
    cached = getattr(request.state, "impersonating", None)
    if cached is not None:
        return cached
    account = current_user(request)
    workspace = workspace_user(request)
    result = bool(account and workspace and workspace["id"] != account["id"])
    if account is not None:
        request.state.impersonating = result
    return result


def impersonation_started_at(request: Request) -> Optional[int]:
    if not impersonating(request):
        return None
    payload = getattr(request.state, "session_payload", None) or {}
    started = payload.get("ast")
    return started if isinstance(started, int) else None


def impersonation_minutes_left(request: Request) -> Optional[int]:
    """Whole minutes left in this impersonation, rounded up; None outside one."""
    started = impersonation_started_at(request)
    if started is None:
        return None
    if IMPERSONATION_MAX_AGE <= 0:
        return None
    remaining = IMPERSONATION_MAX_AGE - (time.time() - started)
    return max(0, int(-(-remaining // 60)))


def revealed_guest_ids(request: Request) -> list[int]:
    if not impersonating(request):
        return []
    payload = getattr(request.state, "session_payload", None) or {}
    values = payload.get("rv") or []
    if not isinstance(values, list):
        return []
    return [int(value) for value in values if isinstance(value, int)]


def end_expired_impersonation(request: Request) -> Optional[RedirectResponse]:
    """Send an admin whose impersonation ran out back to their own view.

    Writes ``impersonation_stopped`` (detail ``expired``) to the host's
    workspace and to the admin's own, and swaps the cookie for a plain one.
    """
    target_id = getattr(request.state, "impersonation_expired_for", None)
    account = current_user(request)
    if not target_id or not account:
        return None
    request.state.impersonation_expired_for = None
    db.set_current_actor(account["id"], account["username"], impersonating=True)
    for owner_id in dict.fromkeys((int(target_id), int(account["id"]))):
        db.audit(
            "impersonation_stopped",
            "expired",
            actor=account["username"],
            owner_user_id=owner_id,
        )
    notice = host_i18n.translate(
        host_i18n.lang_from_request(request), "impersonation.expired"
    )
    response = RedirectResponse(
        f"/admin/users?msg={quote(notice)}", status_code=303
    )
    attach_session(response, issue_session(account["id"], account["session_version"]))
    return response


def session_remembers(request: Request) -> bool:
    """Whether the session in this request was started with "Remember me".

    Re-issuing a session (switching 2FA on, adding a passkey) mints a
    fresh cookie, so the flag has to be carried across by hand or the host
    silently drops back to the short lifetime.
    """
    if current_user(request) is None:
        return False
    payload = getattr(request.state, "session_payload", None) or {}
    return bool(payload.get("rm"))


# Pages reachable while an acceptance is pending: the acceptance screen itself,
# the first-run/account screens, sign-out, and the documents it links to.
_ACCEPTANCE_EXEMPT_PATHS = (
    "/account/accept",
    "/account/2fa/setup",
    "/logout",
    "/terms",
    "/privacy",
    "/dpa",
    "/legal",
    "/subprocessors",
)


def require_login(request: Request) -> Optional[RedirectResponse]:
    """Return a redirect unless a valid account session identifies this host."""
    # Test/development databases may deliberately disable bootstrap and have no
    # accounts. A deployed app creates its administrator before serving.
    if (
        not accounts_exist()
        and not config.BOOTSTRAP_ADMIN
        and config.DEPLOYMENT != "production"
    ):
        return None
    account = current_user(request)
    if not account:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
    workspace = workspace_user(request)
    expired = end_expired_impersonation(request)
    if expired is not None:
        return expired
    # Acceptance evidence belongs to the real account, never to the workspace an
    # admin is previewing, so an impersonating admin is not sent to the screen.
    impersonating = bool(workspace and workspace["id"] != account["id"])
    if (
        not impersonating
        and request.url.path not in _ACCEPTANCE_EXEMPT_PATHS
        and acceptance.pending(account["id"])
    ):
        # Local import: security imports auth at module load, so a top-level
        # import here would be a cycle.
        from . import security

        next_path = security.safe_local_path(request.url.path, "/")
        return RedirectResponse(
            f"/account/accept?next={quote(next_path)}", status_code=303
        )
    db.set_current_actor(
        account["id"], account["username"], impersonating=impersonating
    )
    db.set_current_owner(workspace["id"] if workspace else None)
    return None


def attach_session(response, token: str, remember: bool = False) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=session_max_age({"rm": 1} if remember else None),
        httponly=True,
        samesite="strict",
        secure=secure_cookies(),
        path="/",
    )


def clear_session(response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=secure_cookies(),
        httponly=True,
        samesite="strict",
    )


def create_account(
    email: str,
    display_name: str = "",
    role: str = "host",
    *,
    username: str = "",
) -> int:
    """Create an active account that logs in with ``email``.

    ``email`` must already be normalised (``mail.normalise_email``). The
    username is generated unless the caller names one (tests, the bootstrap).
    """
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("users.email.error.invalid")
    if role not in ("admin", "host"):
        raise ValueError("Unknown account role.")
    username = normalise_username(username) or new_username(email)
    if not username_is_valid(username):
        raise ValueError("auth.error.username")
    return db.insert(
        "user_account",
        {
            "username": username,
            "display_name": (display_name or "").strip(),
            "email": email,
            "password_hash": "",
            "role": role,
            "active": 1,
            "must_change_password": 0,
            "session_version": 1,
            "created_at": db.utcnow(),
        },
    )


def email_taken(email: str, except_user_id: Optional[int] = None) -> bool:
    """Whether another account already logs in with this address."""
    row = db.query_one(
        "SELECT id FROM user_account WHERE email = ? AND id != ?",
        (email, int(except_user_id or 0)),
    )
    return bool(row)


def set_account_email(user_id: int, email: str) -> None:
    """Make ``email`` the account's login address.

    The address is unverified until the host proves it by using a link sent
    there, so ``email_verified_at`` is cleared. A change from an existing
    address also ends every session: whoever held the old address must not
    keep a session the new owner cannot see.
    """
    current = db.query_one("SELECT email FROM user_account WHERE id = ?", (user_id,))
    changing = bool(current and (current["email"] or "").strip())
    sql = "UPDATE user_account SET email = ?, email_verified_at = NULL"
    if changing:
        sql += ", session_version = session_version + 1"
    db.execute(sql + " WHERE id = ?", (email, user_id))


def end_all_sessions(user_id: int) -> None:
    """Retire every session cookie issued for this account, on every device."""
    db.execute(
        "UPDATE user_account SET session_version = session_version + 1 WHERE id = ?",
        (user_id,),
    )


def ensure_bootstrap_admin() -> Optional[str]:
    """Create the first administrator and claim all legacy unowned records.

    The administrator logs in with ``UBYHOST_ADMIN_EMAIL`` (or the operator
    e-mail). The first login link is written to ``initial_admin_login`` in the
    data directory, readable only by the app user, because on a fresh server
    mail may not be set up yet. Returns that link, or None if nothing was made.
    """
    if accounts_exist() or not config.BOOTSTRAP_ADMIN:
        return None
    from . import login_link, mail

    email = mail.normalise_email(config.ADMIN_EMAIL or config.OPERATOR_EMAIL)
    if not email:
        raise RuntimeError(
            "UBYHOST_ADMIN_EMAIL is empty: set the address the first administrator logs in with."
        )
    user_id = create_account(
        email,
        "Administrator",
        role="admin",
        username=normalise_username(config.ADMIN_USERNAME) or "admin",
    )
    db.execute("UPDATE apartment SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,))
    db.execute("UPDATE legal_entity SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,))
    db.execute("UPDATE alert SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,))
    db.execute("UPDATE audit SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,))
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (user_id,))
    token = login_link.issue(account, purpose=login_link.INVITE)
    link = f"{config.PUBLIC_BASE_URL}/login/link?t={token}"
    path = Path(config.DATA_DIR) / "initial_admin_login"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(f"email={email}\nlink={link}\n")
    return link


# No l, 0 or 1: a link read aloud or copied by hand stays unambiguous. The
# readable guest link's code (``guest_slug``) draws from the same letters.
PERMALINK_ALPHABET = "abcdefghijkmnopqrstuvwxyz23456789"


def new_permalink_token() -> str:
    """Short, unguessable, and readable enough to paste into a message."""
    return "".join(secrets.choice(PERMALINK_ALPHABET) for _ in range(20))


def new_permalink_pin() -> str:
    """Six-digit PIN guests enter before the registration form opens."""
    return f"{secrets.randbelow(1_000_000):06d}"


def normalise_permalink_pin(value: str) -> Optional[str]:
    """Return a valid guest PIN (six digits) or None.

    Four-digit PINs are refused: a 10^4 space is walkable in hours, and with
    ``UBYHOST_MAIL_BACKEND=disabled`` the link plus PIN is the only boundary on
    the whole registration flow. Stored legacy PINs are rotated at startup —
    see ``main.lifespan`` — because the guest gate compares against the stored
    value and never consults this normaliser.
    """
    value = (value or "").strip()
    if value.isdigit() and len(value) == 6:
        return value
    return None


PIN_COOKIE = "ubyhost_pin"
_PIN_MAX_AGE = 60 * 60 * 24 * 7  # Limit exposure on shared or lost phones.


def _pin_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.secret_key(), salt="ubyhost-guest-pin")


def pin_fingerprint(token: str, pin: str) -> str:
    """Keyed digest of one (link, PIN) pair.

    ``token`` is always the apartment's permanent ``permalink_token``, never a
    readable slug from the URL: the guest routes resolve the slug first, so the
    PIN cookie and the lockout are the same whichever link the guest opened.

    Safe to keep outside the PIN's own column — the key lives in ``SECRET_KEY``
    and the digest cannot be walked back — and stable enough to scope a lockout
    to the exact PIN it was earned against.
    """
    return hmac.new(
        config.secret_key().encode(),
        f"{token}\0{pin}".encode(),
        hashlib.sha256,
    ).hexdigest()


def pin_matches(token: str, entered: str, expected: str) -> bool:
    """Compare PINs without exposing their length through an early return."""
    return hmac.compare_digest(
        pin_fingerprint(token, entered), pin_fingerprint(token, expected)
    )


def issue_pin_session(token: str, pin: str) -> str:
    return _pin_serializer().dumps(
        {"token": token, "pin": pin_fingerprint(token, pin)}
    )


def pin_session_valid(request: Request, token: str, pin: str) -> bool:
    raw = request.cookies.get(PIN_COOKIE)
    if not raw:
        return False
    try:
        payload = _pin_serializer().loads(raw, max_age=_PIN_MAX_AGE)
        return (
            isinstance(payload, dict)
            and hmac.compare_digest(str(payload.get("token", "")), token)
            and hmac.compare_digest(
                str(payload.get("pin", "")), pin_fingerprint(token, pin)
            )
        )
    except BadSignature:
        return False


def secure_cookies() -> bool:
    """Whether session cookies may carry ``Secure``.

    Either signal is enough: an https public base URL means the browser only
    ever reaches us over TLS, and a production deployment must never hand out
    a cookie without the flag even if the base URL was left at its http
    default. The URL test alone let a production deployment that had not set
    ``UBYHOST_PUBLIC_BASE_URL`` ship insecure cookies, so it is not the gate on
    its own.
    """
    return config.DEPLOYMENT == "production" or config.PUBLIC_BASE_URL.lower().startswith(
        "https://"
    )


def attach_pin_session(response, token: str, pin: str) -> None:
    response.set_cookie(
        PIN_COOKIE,
        issue_pin_session(token, pin),
        max_age=_PIN_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure_cookies(),
        path="/",
    )
