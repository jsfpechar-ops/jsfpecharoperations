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


def test_allows_public_https_calendar():
    # Does not fetch — only DNS resolution; use a stable public host.
    url = validate_calendar_url("https://www.google.com/calendar/ical/test/basic.ics")
    assert url.startswith("https://")
