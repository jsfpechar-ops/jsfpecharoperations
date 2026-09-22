"""Server-side Cloudflare Turnstile verification."""
from __future__ import annotations

import logging
from typing import Any

import requests
from fastapi import Request

from . import alerts, config, rate_limit

log = logging.getLogger("ubyhost.turnstile")
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# How many times one source address may skip the check while the verifier is
# unreachable, per window. Small on purpose: the point of failing open is to
# keep registration working through a Cloudflare outage, not to provide a
# bypass that outlives it.
_UNREACHABLE_MAX_ATTEMPTS = 5
_UNREACHABLE_WINDOW_SECONDS = 15 * 60


def required() -> bool:
    return config.DEPLOYMENT == "production" and config.TURNSTILE_ENABLED


def verify(request: Request, token: Any, expected_action: str) -> bool:
    """Redeem one token and verify its action and frontend hostname.

    There are three outcomes here, not two. A *failed challenge* — a missing,
    oversized, rejected or mis-scoped token — is a rejection. An *unreachable
    verifier* — Cloudflare down, a timeout, a non-2xx, an unparseable reply — is
    not evidence that the guest is a bot, so it fails open for a bounded number
    of attempts per source address. A CDN outage must not be able to stop guest
    registration outright: the statutory deadline does not pause for it.
    """
    if not required():
        return True
    if not isinstance(token, str) or not token or len(token) > 2048:
        return False
    try:
        response = requests.post(
            VERIFY_URL,
            data={
                "secret": config.TURNSTILE_SECRET,
                "response": token,
                "remoteip": request.client.host if request.client else "",
            },
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError):
        log.warning("Turnstile verification unavailable", exc_info=True)
        return _fail_open(request, expected_action)
    return bool(
        result.get("success") is True
        and result.get("action") == expected_action
        and str(result.get("hostname", "")).lower() in config.TURNSTILE_HOSTNAMES
    )


def _fail_open(request: Request, expected_action: str) -> bool:
    """Let a guest past an unreachable verifier, a bounded number of times."""
    key = rate_limit.client_key(request, expected_action)
    alerts.raise_alert(
        "warning",
        "turnstile_unavailable",
        "The security check could not be reached, so it was skipped.",
        detail=(
            "Cloudflare Turnstile did not answer. Guests were let through without the "
            "check for a short while; the alert clears itself once verification works "
            "again."
        ),
        dedupe_key=f"turnstile_unavailable:{expected_action}",
    )
    if rate_limit.blocked(
        "turnstile_unreachable", key, _UNREACHABLE_MAX_ATTEMPTS, _UNREACHABLE_WINDOW_SECONDS
    ):
        log.warning("Turnstile unreachable too often for %s; refusing this attempt", key)
        return False
    rate_limit.record("turnstile_unreachable", key)
    return True
