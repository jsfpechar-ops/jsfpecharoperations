"""ISDS Odesílací brána: hand a stay-fee draft to the host's data box (brief 0240).

Our server creates a short-lived draft with the registration's client
certificate; ISDS answers with the address of its own page, where the host
logs in, checks the message and presses Send. UbyHost never sees or stores the
host's data-box login. Off until all four UBYHOST_ISDS_GATEWAY_* values are set.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from . import config

# The host's browser is only ever sent to ISDS's own pages.
_PORTAL_HOST_SUFFIXES = (".mojedatovaschranka.cz", ".czebox.cz", ".gov.cz")


class GatewayError(Exception):
    """ISDS refused or could not be reached; the host sends by hand instead."""


def configured() -> bool:
    return bool(
        config.ISDS_GATEWAY_ID
        and config.ISDS_GATEWAY_CERT
        and config.ISDS_GATEWAY_SERVICE_URL
    )


def portal_url_ok(url: str) -> bool:
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(host == s[1:] or host.endswith(s) for s in _PORTAL_HOST_SUFFIXES)


def create_draft(*, recipient_databox: str, subject: str, body: str,
                 pdf_name: str, pdf_bytes: bytes, token: str) -> str:
    """Create the draft and return the ISDS page address for the host's browser.

    Waiting for OdesilaciBrana_ISDS.pdf (Technická příloha 2): the request
    format is filled in from that spec in a later brief.
    """
    raise GatewayError("ISDS gateway request not built yet")
