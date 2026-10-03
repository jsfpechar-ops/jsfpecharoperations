"""Umami page analytics on the public marketing and legal pages only (WP09).

Permanent rule: no analytics or third-party script on app pages, guest pages
(``/l/...``, including ``pick.html``) or auth pages. Three things enforce it:

* ``PUBLIC_ANALYTICS_TEMPLATES`` names the only page templates that may carry
  the tag. ``templating.render`` marks a response as a public analytics page
  only when it renders one of them; guest pages use ``render_guest`` and are
  never marked.
* ``_umami.html`` renders the tag only when that mark is set, so including the
  partial anywhere else prints nothing.
* ``main._harden`` adds the Umami origins to the CSP only for marked responses;
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

# Where the Umami Cloud tracker sends events when no data-host-url is set. Read
# from https://cloud.umami.is/script.js on 2026-10-03: the script posts to
# "https://gateway.umami.is/api/send", not to its own origin. The CSP needs it.
UMAMI_CLOUD_SCRIPT_ORIGIN = "https://cloud.umami.is"
UMAMI_CLOUD_DEFAULT_ENDPOINT = "https://gateway.umami.is"

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


def _domains() -> str:
    if config.UMAMI_DOMAINS:
        return ",".join(d.strip() for d in config.UMAMI_DOMAINS.split(",") if d.strip())
    return urlsplit(config.PUBLIC_BASE_URL).hostname or ""


def enabled() -> bool:
    return bool(
        config.UMAMI_WEBSITE_ID
        and config.UMAMI_SCRIPT_URL
        and _https_origin(config.UMAMI_SCRIPT_URL)
    )


def script_origin() -> Optional[str]:
    return _https_origin(config.UMAMI_SCRIPT_URL) if enabled() else None


def connect_origins() -> Tuple[str, ...]:
    """Every origin the tracker may send events to, for CSP connect-src."""
    origin = script_origin()
    if not origin:
        return ()
    origins = [origin]
    if config.UMAMI_HOST_URL:
        host = _https_origin(config.UMAMI_HOST_URL)
        if host:
            origins.append(host)
    elif origin == UMAMI_CLOUD_SCRIPT_ORIGIN:
        origins.append(UMAMI_CLOUD_DEFAULT_ENDPOINT)
    return tuple(dict.fromkeys(origins))


def tag() -> Optional[dict]:
    """The attributes of the tracker tag, or None when analytics is off.

    No distinct ID, no tag, no performance or replay options: page views and
    the anonymous ``data-umami-event`` clicks only. Search and hash are left
    out so an ad click id or a token in a URL never reaches Umami.
    """
    if not enabled():
        return None
    host_url = _https_origin(config.UMAMI_HOST_URL) if config.UMAMI_HOST_URL else None
    return {
        "src": config.UMAMI_SCRIPT_URL,
        "website_id": config.UMAMI_WEBSITE_ID,
        "domains": _domains(),
        "host_url": config.UMAMI_HOST_URL if host_url else "",
    }


def mark_public_page(request, template_name: str) -> bool:
    """Flag the request when it renders an allowed public page. Returns the flag."""
    allowed = template_name in PUBLIC_ANALYTICS_TEMPLATES and enabled()
    if allowed:
        setattr(request.state, STATE_FLAG, True)
    return allowed


def is_public_page(request) -> bool:
    return bool(getattr(request.state, STATE_FLAG, False))
