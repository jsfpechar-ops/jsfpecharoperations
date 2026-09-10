"""Optional single-operator lock.

There are no accounts. The app runs on the host's own machine and opens
straight to the dashboard. A password is only asked for if the host has
deliberately set one in Settings, which matters when the app is put on a box
that other people can reach.

Guests never sign in either: their link is an unguessable token, because
nobody should have to register to satisfy a legal obligation.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Optional

from fastapi import Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer

from . import config, db

SESSION_COOKIE = "ubyhost_session"
SESSION_MAX_AGE = 60 * 60 * 12
PASSWORD_SETTING = "admin_password"
_PBKDF2_ROUNDS = 240_000


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


def password_is_set() -> bool:
    return bool(db.get_setting(PASSWORD_SETTING))


def set_password(password: str) -> None:
    db.set_setting(PASSWORD_SETTING, hash_password(password))
    db.audit("password_set")


def clear_password() -> None:
    db.set_setting(PASSWORD_SETTING, "")
    db.audit("password_cleared")


def check_login(password: str) -> bool:
    stored = db.get_setting(PASSWORD_SETTING)
    return bool(stored) and verify_password(password, stored)


def issue_session() -> str:
    return _serializer().dumps({"v": 1})


def session_is_valid(token: Optional[str]) -> bool:
    if not token:
        return False
    try:
        _serializer().loads(token, max_age=SESSION_MAX_AGE)
        return True
    except BadSignature:
        return False
    except Exception:
        return False


def is_logged_in(request: Request) -> bool:
    return session_is_valid(request.cookies.get(SESSION_COOKIE))


def require_login(request: Request) -> Optional[RedirectResponse]:
    """Return a redirect when a password exists and the caller has not entered it."""
    if not password_is_set():
        return None
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=303)
    return None


def attach_session(response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
        path="/",
    )


def clear_session(response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def new_permalink_token() -> str:
    """Short, unguessable, and readable enough to paste into a message."""
    alphabet = "abcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))
