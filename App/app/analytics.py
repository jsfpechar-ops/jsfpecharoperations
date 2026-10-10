"""PostHog page analytics on the public marketing and legal pages only (WP09).

Permanent rule: no analytics or third-party script on app pages, guest pages
(``/l/...``, including ``pick.html``) or auth pages. Three things enforce it:

* ``PUBLIC_ANALYTICS_TEMPLATES`` names the only page templates that may carry
  the tag. ``templating.render`` marks a response as a public analytics page
  only when it renders one of them; guest pages use ``render_guest`` and are
  never marked.
* ``_posthog.html`` renders the tag only when that mark is set, so including the
  partial anywhere else prints nothing.
* ``main._harden`` adds the PostHog origins to the CSP only for marked responses;
  every other page keeps the strict policy, so even a stray tag would be
  blocked by the browser.

``tests/test_umami_guard.py`` checks all three.
"""
from __future__ import annotations

from typing import Optional, Tuple
from urllib.parse import urlsplit

from . import config

PUBLIC_ANALYTICS_TEMPLATES = frozenset(
    {
        "landing.html",
        "product.html",
        "pricing.html",
        "public_guide.html",
        # Everything below extends public_legal_base.html.
        "legal.html",
        "terms.html",
        "privacy.html",
        "dpa.html",
        "subprocessors.html",
    }
)

_US_API_HOST = "us.i.posthog.com"
_US_ASSETS_HOST = "us-assets.i.posthog.com"

STATE_FLAG = "public_analytics_page"


def _https_origin(url: str) -> Optional[str]:
    """``https://host[:port]`` of an absolute https URL, else None."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname:
        return None
    host = parts.hostname
    if parts.port:
        host = f"{host}:{parts.port}"
    return f"https://{host}"


def _host_allowed(url: str) -> bool:
    origin = _https_origin(url)
    if not origin:
        return False
    lower = origin.lower()
    if _US_API_HOST in lower or _US_ASSETS_HOST in lower:
        return False
    return True


def enabled() -> bool:
    return bool(
        config.POSTHOG_PROJECT_API_KEY
        and _host_allowed(config.POSTHOG_HOST)
        and _host_allowed(config.POSTHOG_ASSETS_HOST)
    )


def script_origin() -> Optional[str]:
    return _https_origin(config.POSTHOG_ASSETS_HOST) if enabled() else None


def connect_origins() -> Tuple[str, ...]:
    """The PostHog API origin events are sent to, for CSP connect-src."""
    if not enabled():
        return ()
    api = _https_origin(config.POSTHOG_HOST)
    return (api,) if api else ()


def tag() -> Optional[dict]:
    """PostHog init parameters, or None when analytics is off."""
    if not enabled():
        return None
    api_host = _https_origin(config.POSTHOG_HOST)
    assets_host = _https_origin(config.POSTHOG_ASSETS_HOST)
    if not api_host or not assets_host:
        return None
    return {
        "api_key": config.POSTHOG_PROJECT_API_KEY,
        "api_host": api_host,
        "assets_host": assets_host,
    }


def mark_public_page(request, template_name: str) -> bool:
    """Flag the request when it renders an allowed public page. Returns the flag."""
    allowed = template_name in PUBLIC_ANALYTICS_TEMPLATES and enabled()
    if allowed:
        setattr(request.state, STATE_FLAG, True)
    return allowed


def is_public_page(request) -> bool:
    return bool(getattr(request.state, STATE_FLAG, False))
