"""Host accounts, sessions, and workspace impersonation.

Passwords are one-way PBKDF2 hashes. An administrator can reset a password,
but nobody can retrieve one. Guest links remain account-free: their random
apartment token and PIN are the boundary for the legal registration flow.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer

from . import config, db

SESSION_COOKIE = "ubyhost_session"
SESSION_MAX_AGE = 60 * 60 * 12
_PBKDF2_ROUNDS = 600_000
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
_dummy_password_hash: Optional[str] = None


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.SECRET_KEY, salt="ubyhost-session")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def normalise_username(value: str) -> str:
    return (value or "").strip().lower()


def username_is_valid(value: str) -> bool:
    return bool(_USERNAME_RE.fullmatch(normalise_username(value)))


def password_error(password: str) -> str:
    if len(password or "") < 12:
        return "Use at least 12 characters."
    if password.lower() == password or password.upper() == password:
        return "Use both upper- and lower-case letters."
    if not any(char.isdigit() for char in password):
        return "Add at least one number."
    return ""


def accounts_exist() -> bool:
    return bool(db.query_one("SELECT id FROM user_account LIMIT 1"))


def _dummy_hash() -> str:
    global _dummy_password_hash
    if _dummy_password_hash is None:
        _dummy_password_hash = hash_password("Timing-Only-Password-123")
    return _dummy_password_hash


def authenticate(username: str, password: str):
    account = db.query_one(
        "SELECT * FROM user_account WHERE username = ? AND active = 1",
        (normalise_username(username),),
    )
    stored = account["password_hash"] if account else _dummy_hash()
    if not verify_password(password, stored) or not account:
        return None
    db.execute("UPDATE user_account SET last_login_at = ? WHERE id = ?", (db.utcnow(), account["id"]))
    return account


def issue_session(user_id: int, session_version: int, workspace_user_id: Optional[int] = None) -> str:
    payload = {"uid": int(user_id), "sv": int(session_version)}
    if workspace_user_id and workspace_user_id != user_id:
        payload["as"] = int(workspace_user_id)
    return _serializer().dumps(payload)


def _session_payload(token: Optional[str]) -> Optional[dict[str, Any]]:
    if not token:
        return None
    try:
        payload = _serializer().loads(token, max_age=SESSION_MAX_AGE)
        return payload if isinstance(payload, dict) else None
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
        target = db.query_one(
            "SELECT * FROM user_account WHERE id = ? AND active = 1", (target_id,)
        )
        if target:
            return target
    return account


def is_logged_in(request: Request) -> bool:
    return current_user(request) is not None


def require_login(request: Request) -> Optional[RedirectResponse]:
    """Return a redirect unless a valid account session identifies this host."""
    # Test/development databases may deliberately disable bootstrap and have no
    # accounts. A deployed app creates its administrator before serving.
    if not accounts_exist() and not config.BOOTSTRAP_ADMIN:
        return None
    account = current_user(request)
    if not account:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
    if account["must_change_password"] and request.url.path not in (
        "/account/password", "/logout"
    ):
        return RedirectResponse("/account/password", status_code=303)
    workspace = workspace_user(request)
    db.set_current_owner(workspace["id"] if workspace else None)
    return None


def attach_session(response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
        secure=config.PUBLIC_BASE_URL.lower().startswith("https://"),
        path="/",
    )


def clear_session(response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def create_account(
    username: str,
    password: str,
    display_name: str = "",
    role: str = "host",
    must_change_password: bool = True,
) -> int:
    username = normalise_username(username)
    if not username_is_valid(username):
        raise ValueError("Use 3–32 lowercase letters, numbers, dots, dashes, or underscores.")
    error = password_error(password)
    if error:
        raise ValueError(error)
    if role not in ("admin", "host"):
        raise ValueError("Unknown account role.")
    return db.insert(
        "user_account",
        {
            "username": username,
            "display_name": (display_name or "").strip(),
            "password_hash": hash_password(password),
            "role": role,
            "active": 1,
            "must_change_password": 1 if must_change_password else 0,
            "session_version": 1,
            "created_at": db.utcnow(),
        },
    )


def set_account_password(user_id: int, password: str, must_change: bool = False) -> None:
    error = password_error(password)
    if error:
        raise ValueError(error)
    db.execute(
        "UPDATE user_account SET password_hash = ?, must_change_password = ?, "
        "session_version = session_version + 1 WHERE id = ?",
        (hash_password(password), 1 if must_change else 0, user_id),
    )


def ensure_bootstrap_admin() -> Optional[str]:
    """Create the first administrator and claim all legacy unowned records."""
    if accounts_exist() or not config.BOOTSTRAP_ADMIN:
        return None
    username = normalise_username(config.ADMIN_USERNAME) or "admin"
    password = config.ADMIN_PASSWORD
    if not password:
        while True:
            password = secrets.token_urlsafe(16)
            if not password_error(password):
                break
    legacy_hash = db.get_setting("admin_password")
    if legacy_hash and not config.ADMIN_PASSWORD:
        password_hash = legacy_hash
        generated_password = ""
    else:
        error = password_error(password)
        if error:
            raise RuntimeError(f"UBYHOST_ADMIN_PASSWORD is not strong enough: {error}")
        password_hash = hash_password(password)
        generated_password = "" if config.ADMIN_PASSWORD else password
    user_id = db.insert(
        "user_account",
        {
            "username": username,
            "display_name": "Administrator",
            "password_hash": password_hash,
            "role": "admin",
            "active": 1,
            "must_change_password": 1,
            "session_version": 1,
            "created_at": db.utcnow(),
        },
    )
    db.execute("UPDATE apartment SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,))
    db.execute("UPDATE legal_entity SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,))
    db.execute("UPDATE alert SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,))
    db.execute("UPDATE audit SET owner_user_id = ? WHERE owner_user_id IS NULL", (user_id,))
    if generated_password:
        path = Path(config.DATA_DIR) / "initial_admin_credentials"
        path.write_text(f"username={username}\npassword={generated_password}\n")
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return generated_password


def new_permalink_token() -> str:
    """Short, unguessable, and readable enough to paste into a message."""
    alphabet = "abcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))


def new_permalink_pin() -> str:
    """Four-digit PIN guests enter before the registration form opens."""
    return f"{secrets.randbelow(10000):04d}"


def normalise_permalink_pin(value: str) -> Optional[str]:
    """Return a valid four-digit PIN or None."""
    value = (value or "").strip()
    if len(value) == 4 and value.isdigit():
        return value
    return None


PIN_COOKIE = "ubyhost_pin"
_PIN_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _pin_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.SECRET_KEY, salt="ubyhost-guest-pin")


def issue_pin_session(token: str) -> str:
    return _pin_serializer().dumps({"token": token})


def pin_session_valid(request: Request, token: str) -> bool:
    raw = request.cookies.get(PIN_COOKIE)
    if not raw:
        return False
    try:
        payload = _pin_serializer().loads(raw, max_age=_PIN_MAX_AGE)
        return isinstance(payload, dict) and payload.get("token") == token
    except BadSignature:
        return False


def attach_pin_session(response, token: str) -> None:
    response.set_cookie(
        PIN_COOKIE,
        issue_pin_session(token),
        max_age=_PIN_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=config.PUBLIC_BASE_URL.lower().startswith("https://"),
        path="/",
    )


def clear_pin_session(response) -> None:
    response.delete_cookie(PIN_COOKIE, path="/")
