"""Server-side Cloudflare Turnstile verification."""
from __future__ import annotations

import logging
from typing import Any

import requests
from fastapi import Request

from . import config

log = logging.getLogger("ubyhost.turnstile")
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def required() -> bool:
    return config.DEPLOYMENT == "production" and config.TURNSTILE_ENABLED


def verify(request: Request, token: Any, expected_action: str) -> bool:
    """Redeem one token and verify its action and frontend hostname."""
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
        return False
    return bool(
        result.get("success") is True
        and result.get("action") == expected_action
        and str(result.get("hostname", "")).lower() in config.TURNSTILE_HOSTNAMES
    )
