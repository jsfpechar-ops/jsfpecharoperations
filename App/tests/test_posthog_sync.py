"""PostHog server-side funnel sync."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from app import admin_funnel, config, db, posthog_sync
from tests.test_admin_funnel import NOW, PREFIX, _account, _cleanup, _iso, _seed_host_at

API_KEY = "phc_test"
API_HOST = "https://analytics.example.invalid"
ASSETS_HOST = "https://assets.example.invalid"


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


@pytest.fixture
def posthog_on(monkeypatch):
    monkeypatch.setattr(config, "POSTHOG_PROJECT_API_KEY", API_KEY)
    monkeypatch.setattr(config, "POSTHOG_HOST", API_HOST)
    monkeypatch.setattr(config, "POSTHOG_ASSETS_HOST", ASSETS_HOST)


def test_unset_key_sends_nothing(monkeypatch):
    monkeypatch.setattr(config, "POSTHOG_PROJECT_API_KEY", "")
    assert posthog_sync.sync() == {"sent": 0, "skipped": 0, "failed": 0}


def test_first_property_backfill_and_second_run_is_quiet(posthog_on):
    uid = _seed_host_at(4)
    captured: list[dict] = []

    def fake_urlopen(request, timeout=0):
        captured.append(json.loads(request.data.decode()))
        return type("R", (), {"status": 200, "__enter__": lambda s: s, "__exit__": lambda *a: None})()

    with patch("urllib.request.urlopen", fake_urlopen):
        first = posthog_sync.sync()
    assert first["sent"] > 0 and first["failed"] == 0
    stored = db.query_one("SELECT posthog_stage FROM user_account WHERE id = ?", (uid,))
    assert stored["posthog_stage"] == "first_property"
    events = [body["event"] for body in captured]
    assert events[-1] == "first_property"
    assert events == [key for key, _ in admin_funnel.stages()[: events.index("first_property") + 1]]

    before = len(captured)
    with patch("urllib.request.urlopen", fake_urlopen):
        posthog_sync.sync()
    new_for_us = [body for body in captured[before:] if body["distinct_id"] == str(uid)]
    assert not new_for_us


def test_failed_post_does_not_advance_stage(posthog_on):
    uid = _seed_host_at(4)

    def boom(request, timeout=0):
        raise HTTPError(request.full_url, 503, "down", {}, None)

    with patch("urllib.request.urlopen", boom):
        summary = posthog_sync.sync()
    assert summary["failed"] == 1
    stored = db.query_one("SELECT posthog_stage FROM user_account WHERE id = ?", (uid,))
    assert stored["posthog_stage"] is None


def test_capture_body_shape(posthog_on):
    uid = _seed_host_at(1)
    bodies: list[dict] = []

    def fake_urlopen(request, timeout=0):
        bodies.append(json.loads(request.data.decode()))
        return type("R", (), {"status": 200, "__enter__": lambda s: s, "__exit__": lambda *a: None})()

    with patch("urllib.request.urlopen", fake_urlopen):
        posthog_sync.sync()

    assert bodies
    body = bodies[0]
    assert body["distinct_id"] == str(uid)
    assert body["properties"]["$ip"] is None
    assert "gclid" not in json.dumps(body)
    assert "fbclid" not in json.dumps(body)
    assert body["properties"]["$set"]["funnel_stage"] == body["event"]
