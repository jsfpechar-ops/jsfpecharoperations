"""Host accounts, sessions, and workspace impersonation.

Passwords are one-way PBKDF2 hashes. An administrator can reset a password,
but nobody can retrieve one. Guest links remain account-free: their random
apartment token and PIN are the boundary for the legal registration flow.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
import pyotp

from . import config, db

SESSION_COOKIE = "ubyhost_session"
SESSION_MAX_AGE = 60 * 60 * 12
SESSION_REMEMBER_MAX_AGE = 60 * 60 * 24 * 30
TWO_FACTOR_PENDING_MAX_AGE = 10 * 60
_PBKDF2_ROUNDS = 600_000
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
_dummy_password_hash: Optional[str] = None


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.SECRET_KEY, salt="ubyhost-session")


def _two_factor_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.SECRET_KEY, salt="ubyhost-2fa-pending")


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
        config.SECRET_KEY.encode(), normalized.encode(), hashlib.sha256
    ).hexdigest()


def new_recovery_codes(count: int = 8) -> list[str]:
    return [f"{secrets.token_hex(4)[:4]}-{secrets.token_hex(4)[:4]}".upper() for _ in range(count)]


def enable_totp(user_id: int, secret: str, recovery_codes: list[str]) -> None:
    db.execute(
        "UPDATE user_account SET totp_secret_enc = ?, totp_enabled = 1, "
        "recovery_codes_hash = ?, session_version = session_version + 1 WHERE id = ?",
        (
            db.encrypt_secret(secret),
            json.dumps([recovery_code_hash(code) for code in recovery_codes]),
            user_id,
        ),
    )


def stage_totp(user_id: int, secret: str) -> None:
    db.execute(
        "UPDATE user_account SET totp_secret_enc = ?, totp_enabled = 0 WHERE id = ?",
        (db.encrypt_secret(secret), user_id),
    )


def reset_totp(user_id: int) -> None:
    db.execute(
        "UPDATE user_account SET totp_secret_enc = NULL, totp_enabled = 0, "
        "recovery_codes_hash = NULL, session_version = session_version + 1 WHERE id = ?",
        (user_id,),
    )


def verify_second_factor(account, code: str) -> bool:
    normalized = (code or "").replace(" ", "")
    try:
        secret = db.decrypt_secret(account["totp_secret_enc"])
    except Exception:
        return False
    if secret and pyotp.TOTP(secret).verify(normalized, valid_window=1):
        return True
    candidate = recovery_code_hash(normalized)
    try:
        hashes = json.loads(account["recovery_codes_hash"] or "[]")
    except ValueError:
        hashes = []
    for stored in hashes:
        if hmac.compare_digest(candidate, stored):
            hashes.remove(stored)
            db.execute(
                "UPDATE user_account SET recovery_codes_hash = ? WHERE id = ?",
                (json.dumps(hashes), account["id"]),
            )
            return True
    return False


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
    if len(password or "") > 256:
        return "Use no more than 256 characters."
    if len(password or "") < 12:
        return "Use at least 12 characters."
    if password.lower() == password or password.upper() == password:
        return "Use both upper- and lower-case letters."
    if not any(char.isdigit() for char in password):
        return "Add at least one number."
    return ""


def generate_password() -> str:
    """Return a random password that satisfies password_error()."""
    while True:
        candidate = secrets.token_urlsafe(18)
        if not password_error(candidate):
            return candidate


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


def issue_session(
    user_id: int,
    session_version: int,
    workspace_user_id: Optional[int] = None,
    remember: bool = False,
) -> str:
    payload = {"uid": int(user_id), "sv": int(session_version)}
    if remember:
        payload["rm"] = 1
    if workspace_user_id and workspace_user_id != user_id:
        payload["as"] = int(workspace_user_id)
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
    if (
        not accounts_exist()
        and not config.BOOTSTRAP_ADMIN
        and config.DEPLOYMENT != "production"
    ):
        return None
    account = current_user(request)
    if not account:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
    if account["must_change_password"] and request.url.path not in (
        "/account/password", "/logout"
    ):
        return RedirectResponse("/account/password", status_code=303)
    if config.DEPLOYMENT == "production" and not account["totp_enabled"] and request.url.path not in (
        "/account/2fa/setup", "/logout"
    ):
        return RedirectResponse("/account/2fa/setup", status_code=303)
    workspace = workspace_user(request)
    db.set_current_owner(workspace["id"] if workspace else None)
    return None


def attach_session(response, token: str, remember: bool = False) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_REMEMBER_MAX_AGE if remember else SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
        secure=_secure_cookies(),
        path="/",
    )


def clear_session(response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=_secure_cookies(),
        httponly=True,
        samesite="strict",
    )


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
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(f"username={username}\npassword={generated_password}\n")
    return generated_password


def new_permalink_token() -> str:
    """Short, unguessable, and readable enough to paste into a message."""
    alphabet = "abcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(20))


def new_permalink_pin() -> str:
    """Six-digit PIN guests enter before the registration form opens."""
    return f"{secrets.randbelow(1_000_000):06d}"


def normalise_permalink_pin(value: str) -> Optional[str]:
    """Return a valid guest PIN (4 legacy or 6 current digits) or None."""
    value = (value or "").strip()
    if value.isdigit() and len(value) in (4, 6):
        return value
    return None


PIN_COOKIE = "ubyhost_pin"
_PIN_MAX_AGE = 60 * 60 * 24 * 7  # Limit exposure on shared or lost phones.


def _pin_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config.SECRET_KEY, salt="ubyhost-guest-pin")


def _pin_fingerprint(token: str, pin: str) -> str:
    return hmac.new(
        config.SECRET_KEY.encode(),
        f"{token}\0{pin}".encode(),
        hashlib.sha256,
    ).hexdigest()


def pin_matches(token: str, entered: str, expected: str) -> bool:
    """Compare PINs without exposing their length through an early return."""
    return hmac.compare_digest(
        _pin_fingerprint(token, entered), _pin_fingerprint(token, expected)
    )


def issue_pin_session(token: str, pin: str) -> str:
    return _pin_serializer().dumps(
        {"token": token, "pin": _pin_fingerprint(token, pin)}
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
                str(payload.get("pin", "")), _pin_fingerprint(token, pin)
            )
        )
    except BadSignature:
        return False


def _secure_cookies() -> bool:
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
        secure=_secure_cookies(),
        path="/",
    )


def clear_pin_session(response) -> None:
    response.delete_cookie(
        PIN_COOKIE,
        path="/",
        secure=_secure_cookies(),
        httponly=True,
        samesite="lax",
    )
