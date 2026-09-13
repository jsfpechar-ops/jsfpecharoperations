"""Simple sliding-window rate limits backed by SQLite (single-tenant friendly)."""
from __future__ import annotations

import time
from typing import Optional

from . import db

_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_FAILURES = 12
_PIN_MAX_FAILURES = 30
_BLOCK_SECONDS = 15 * 60


def _prune(scope: str, key: str, window: int) -> None:
    cutoff = time.time() - window
    db.execute(
        "DELETE FROM rate_limit_event WHERE scope = ? AND key = ? AND at < ?",
        (scope, key, cutoff),
    )


def _count(scope: str, key: str, window: int) -> int:
    _prune(scope, key, window)
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM rate_limit_event WHERE scope = ? AND key = ?",
        (scope, key),
    )
    return int(row["n"]) if row else 0


def record(scope: str, key: str) -> None:
    db.insert(
        "rate_limit_event",
        {"scope": scope, "key": key, "at": time.time()},
    )


def blocked(scope: str, key: str, max_events: int, window: int = _WINDOW_SECONDS) -> bool:
    if not key:
        return False
    return _count(scope, key, window) >= max_events


def login_blocked(client_key: str) -> bool:
    return blocked("login_fail", client_key, _LOGIN_MAX_FAILURES)


def record_login_failure(client_key: str) -> None:
    record("login_fail", client_key)


def pin_blocked(client_key: str) -> bool:
    return blocked("pin_fail", client_key, _PIN_MAX_FAILURES)


def record_pin_failure(client_key: str) -> None:
    record("pin_fail", client_key)


def client_key(request, suffix: str = "") -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{suffix}" if suffix else host
