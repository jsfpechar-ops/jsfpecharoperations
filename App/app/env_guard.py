"""Refuse unsafe UbyPort / deployment combinations at process start.

Lightsail is the only place live reporting may run. Render staging stays on
``mock``. These checks are process-level so a mis-set env var cannot quietly
talk to the police register.
"""
from __future__ import annotations

import logging
import os
from typing import Iterable, List, Mapping, Optional, Sequence

from . import config, mail

log = logging.getLogger("ubyhost.env_guard")

ALLOWED_UBYPORT = frozenset({"mock", "test", "prod"})


class EnvGuardError(RuntimeError):
    """Fatal environment misconfiguration — do not start the app."""


def is_render_like_environment(environ: Optional[Mapping[str, str]] = None) -> bool:
    env = environ if environ is not None else os.environ
    render_flag = (env.get("RENDER") or "").strip().lower()
    if render_flag in {"1", "true", "yes"}:
        return True
    if env.get("RENDER_SERVICE_ID") or env.get("RENDER_INSTANCE_ID"):
        return True
    haystack = " ".join(
        env.get(key, "")
        for key in (
            "RENDER_EXTERNAL_URL",
            "RENDER_EXTERNAL_HOSTNAME",
            "UBYHOST_PUBLIC_BASE_URL",
            "UBYHOST_DOMAIN",
        )
    ).lower()
    return "onrender.com" in haystack


def public_url_host(url: str) -> str:
    text = (url or "").strip()
    for prefix in ("https://", "http://"):
        if text.lower().startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.split("/", 1)[0].split(":", 1)[0].lower()


def validate_runtime_env(
    *,
    ubyport_env: Optional[str] = None,
    deployment: Optional[str] = None,
    guest_pin_required: Optional[bool] = None,
    scheduler_enabled: Optional[bool] = None,
    public_base_url: Optional[str] = None,
    domain: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> List[str]:
    """Return warnings. Raise EnvGuardError when starting would be unsafe."""
    env = (ubyport_env if ubyport_env is not None else config.UBYPORT_ENV).lower()
    deploy = (deployment if deployment is not None else config.DEPLOYMENT).lower()
    pin = (
        guest_pin_required
        if guest_pin_required is not None
        else config.GUEST_PIN_REQUIRED
    )
    scheduler = (
        scheduler_enabled
        if scheduler_enabled is not None
        else config.ENABLE_SCHEDULER
    )
    base_url = (
        public_base_url
        if public_base_url is not None
        else config.PUBLIC_BASE_URL
    )
    domain_name = (
        domain
        if domain is not None
        else (os.environ.get("UBYHOST_DOMAIN") or "")
    )
    os_env = environ if environ is not None else os.environ
    warnings: List[str] = []

    if env not in ALLOWED_UBYPORT:
        raise EnvGuardError(
            f"UBYHOST_UBYPORT_ENV={env!r} is invalid (use mock, test, or prod)."
        )

    if env == "prod" and deploy != "production":
        raise EnvGuardError(
            "UBYHOST_UBYPORT_ENV=prod requires UBYHOST_DEPLOYMENT=production. "
            "Staging and local stacks must stay on mock (or test on Lightsail)."
        )

    if env == "prod" and is_render_like_environment(os_env):
        raise EnvGuardError(
            "UBYHOST_UBYPORT_ENV=prod is not allowed on Render. "
            "Live police reporting runs only on AWS Lightsail (ubyhost.com)."
        )

    if deploy == "production" and env == "mock":
        warnings.append(
            "production deployment with UBYHOST_UBYPORT_ENV=mock — "
            "nothing is reported to the police"
        )

    if deploy == "production" and not pin:
        warnings.append(
            "UBYHOST_GUEST_PIN is off on production — guest permalinks are unprotected"
        )

    if deploy == "production" and not scheduler:
        warnings.append(
            "UBYHOST_ENABLE_SCHEDULER is off — iCal sync, auto-submit, "
            "deadline watch, and photo sweep will not run"
        )

    expected_host = (domain_name or "").strip().lower()
    actual_host = public_url_host(base_url)
    if expected_host and actual_host and expected_host != actual_host:
        warnings.append(
            f"UBYHOST_PUBLIC_BASE_URL host {actual_host!r} does not match "
            f"UBYHOST_DOMAIN {expected_host!r} — guest permalinks will be wrong"
        )

    if deploy == "production" and not str(base_url).lower().startswith("https://"):
        warnings.append("UBYHOST_PUBLIC_BASE_URL should use https:// in production")

    try:
        warnings.extend(
            mail.validate_mail_env(
                backend=(
                    (os_env.get("UBYHOST_MAIL_BACKEND") or None)
                    if environ is not None
                    else None
                ),
                deployment=deploy,
            )
        )
    except mail.MailConfigError as exc:
        raise EnvGuardError(str(exc)) from exc

    return warnings


def apply(warnings: Optional[Sequence[str]] = None) -> List[str]:
    found = list(warnings) if warnings is not None else validate_runtime_env()
    for message in found:
        log.warning("%s", message)
    return found


def format_warnings(messages: Iterable[str]) -> str:
    return "\n".join(f"WARNING: {item}" for item in messages)
