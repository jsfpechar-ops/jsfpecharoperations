"""SSRF guards for iCal calendar URLs."""
from __future__ import annotations

import pytest

from app import config
from app.feed_url import FeedUrlError, validate_calendar_url


@pytest.fixture(autouse=True)
def enforce_public_ical_only(monkeypatch):
    monkeypatch.setattr(config, "ICAL_ALLOW_PRIVATE", False)


def test_blocks_loopback_literal():
    with pytest.raises(FeedUrlError):
        validate_calendar_url("http://127.0.0.1:8081/ws_uby/ws_uby.svc")


def test_blocks_localhost_hostname():
    with pytest.raises(FeedUrlError):
        validate_calendar_url("http://localhost/calendar.ics")


def test_blocks_metadata_host():
    with pytest.raises(FeedUrlError):
        validate_calendar_url("http://metadata.google.internal/computeMetadata/v1/")


@pytest.mark.parametrize(
    "url",
    [
        # Alternative encodings of 127.0.0.1 that a plain string check misses.
        "http://2130706433/c.ics",
        "http://0177.0.0.1/c.ics",
        "http://0x7f000001/c.ics",
        "http://127.1/c.ics",
        # IPv6 loopback and IPv4-mapped IPv6.
        "http://[::1]/c.ics",
        "http://[::ffff:127.0.0.1]/c.ics",
        # Cloud metadata and the RFC 1918 ranges.
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/c.ics",
        "http://192.168.1.1/c.ics",
        "http://172.16.0.1/c.ics",
        "http://0.0.0.0/c.ics",
        # Credentials must not smuggle a blocked host past the check.
        "http://user:pass@127.0.0.1/c.ics",
        # Feed URLs must never carry credentials, even for public hosts.
        "https://calendar-user:calendar-password@www.google.com/c.ics",
        # Malformed authority syntax must fail closed rather than raising a 500.
        "http://[::1/c.ics",
        # Non-HTTP schemes.
        "file:///etc/passwd",
        "gopher://example.com/",
        # mDNS names resolve inside the LAN.
        "http://nas.local/c.ics",
        # Carrier-grade NAT. Python reports these as neither private nor
        # reserved, so they slipped through, but a self-hosted box behind CGNAT
        # or in a cluster that uses the range reaches its neighbours here.
        "http://100.64.0.1/c.ics",
        "http://100.127.255.254/c.ics",
        # IPv4-to-IPv6 translation and 6to4 wrappers around a private target.
        "http://[64:ff9b::a00:5]/c.ics",
    ],
)
def test_blocks_internal_targets_however_they_are_written(url):
    with pytest.raises(FeedUrlError):
        validate_calendar_url(url)


def test_redirects_are_revalidated_not_followed_blindly():
    """A public feed that 302s to the metadata service must be stopped."""
    from app.feed_url import resolve_redirect_url

    with pytest.raises(FeedUrlError):
        resolve_redirect_url(
            "https://www.google.com/calendar/ical/x.ics",
            "http://169.254.169.254/latest/meta-data/",
        )
    with pytest.raises(FeedUrlError):
        resolve_redirect_url("https://www.google.com/calendar/ical/x.ics", "http://localhost/x")
    # A relative hop inside the same public host is legitimate.
    assert resolve_redirect_url(
        "https://www.google.com/calendar/ical/x.ics", "/calendar/ical/y.ics"
    ) == "https://www.google.com/calendar/ical/y.ics"


def test_allows_public_https_calendar():
    # Does not fetch — only DNS resolution; use a stable public host.
    url = validate_calendar_url("https://www.google.com/calendar/ical/test/basic.ics")
    assert url.startswith("https://")


def test_production_cannot_enable_private_calendar_targets(monkeypatch):
    monkeypatch.setattr(config, "ICAL_ALLOW_PRIVATE", True)
    monkeypatch.setattr(config, "DEPLOYMENT", "production")

    with pytest.raises(FeedUrlError):
        validate_calendar_url("http://127.0.0.1/calendar.ics")


def test_staging_allows_loopback_when_private_ical_enabled(monkeypatch):
    """Local mock calendars (CI/staging) must work when private iCal is on."""
    monkeypatch.setattr(config, "ICAL_ALLOW_PRIVATE", True)
    monkeypatch.setattr(config, "DEPLOYMENT", "staging")

    url = validate_calendar_url("http://127.0.0.1:8081/ws_uby/ws_uby.svc")
    assert url == "http://127.0.0.1:8081/ws_uby/ws_uby.svc"
