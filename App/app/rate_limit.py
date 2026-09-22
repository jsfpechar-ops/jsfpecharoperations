"""Simple sliding-window rate limits backed by SQLite (single-tenant friendly)."""
from __future__ import annotations

import time
from typing import Optional

from . import db

_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_FAILURES = 12
_LOGIN_IP_MAX_FAILURES = 30
_PIN_MAX_FAILURES = 10
# A per-IP window can be sidestepped by rotating source addresses, so the same
# failures are also counted against the token alone; three windows' worth locks
# the link for a day.
_PIN_TOKEN_MAX_FAILURES = 3 * _PIN_MAX_FAILURES
_PIN_TOKEN_LOCK_SECONDS = 24 * 60 * 60
_BLOCK_SECONDS = 15 * 60

#: Used when the ASGI server hands us no peer address. It is a *single shared*
#: bucket — every such request counts against the same key — so a limit built on
#: it means "refuse once this bucket fills", not "refuse this visitor". That is
#: acceptable because uvicorn always supplies a peer and `client_ip` only ever
#: *overwrites* it with a verified visitor address; the constant exists so the
#: shared nature is visible at the point of use instead of hidden in a literal.
UNIDENTIFIED_CLIENT = "unknown"


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
    """True when ``key`` has used up its budget in ``scope``.

    Fails *closed* on an empty key. Returning False there — the old behaviour —
    means a caller that cannot name its subject silently loses the limit, which
    is a bypass reachable by anything that can produce an empty key. No current
    caller can (`client_key` never returns one), so this is a guard against the
    next one rather than a behaviour change.
    """
    if not key:
        return True
    return _count(scope, key, window) >= max_events


def login_blocked(client_key: str, ip_key: str = "") -> bool:
    return blocked("login_fail", client_key, _LOGIN_MAX_FAILURES) or (
        bool(ip_key)
        and blocked("login_fail_ip", ip_key, _LOGIN_IP_MAX_FAILURES)
    )


def record_login_failure(client_key: str, ip_key: str = "") -> None:
    record("login_fail", client_key)
    if ip_key:
        record("login_fail_ip", ip_key)


def pin_blocked(client_key: str) -> bool:
    return blocked("pin_fail", client_key, _PIN_MAX_FAILURES)


def pin_token_blocked(lock_key: str) -> bool:
    """Long cool-off once one link has burned a day's worth of attempts.

    The key is the link *and* the PIN it was tested against, so spreading the
    guesses over many source addresses — the weakness in the per-IP window —
    does not reset the budget, while generating a new PIN does: the host's
    ``regenerate-pin`` button is the remedy for a locked-out guest, and a
    token-only key would leave that guest shut out for a day.
    """
    return blocked("pin_fail_token", lock_key, _PIN_TOKEN_MAX_FAILURES, _PIN_TOKEN_LOCK_SECONDS)


def record_pin_failure(client_key: str, lock_key: str = "") -> None:
    record("pin_fail", client_key)
    if lock_key:
        record("pin_fail_token", lock_key)


def pin_failure_count(client_key: str) -> int:
    return _count("pin_fail", client_key, _WINDOW_SECONDS)


def client_key(request, suffix: str = "") -> str:
    """Identify a caller by peer address, never by a value the caller controls.

    A missing address becomes `UNIDENTIFIED_CLIENT` rather than an empty string,
    so it stays a *shared bucket* that limits still count against — never a key
    that `blocked` would have to fail closed on.
    """
    host = (request.client.host if request.client else "") or UNIDENTIFIED_CLIENT
    return f"{host}:{suffix}" if suffix else host
