"""PostHog server-side funnel sync."""
from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from app import admin_funnel, config, db, posthog_sync
from tests.test_admin_funnel import NOW, _cleanup, _iso, _seed_host_at

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
    events = [body["event"] for body in captured if body["distinct_id"] == str(uid)]
    assert events[-1] == "first_property"
    row = next(r for r in admin_funnel.rows()["rows"] if r["id"] == uid)
    expected = []
    for key, column in admin_funnel.stages():
        if row.get(column):
            expected.append(key)
        if key == "first_property":
            break
    assert events == expected

    calls_for_us = 0

    def counting_urlopen(request, timeout=0):
        body = json.loads(request.data.decode())
        if body.get("distinct_id") == str(uid):
            nonlocal calls_for_us
            calls_for_us += 1
        return fake_urlopen(request, timeout)

    with patch("urllib.request.urlopen", counting_urlopen):
        posthog_sync.sync()
    assert calls_for_us == 0


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
    assert body["properties"]["$geoip_disable"] is True
    assert "uuid" in body
    assert "gclid" not in json.dumps(body)
    assert "fbclid" not in json.dumps(body)
    assert body["properties"]["$set"]["funnel_stage"] == body["event"]


def _ok_response():
    return type("R", (), {"status": 200, "__enter__": lambda s: s, "__exit__": lambda *a: None})()


def test_skipped_stage_is_not_sent(posthog_on):
    uid = _seed_host_at(4)
    at = _iso(NOW - timedelta(days=30))
    apartment_id = db.query_one("SELECT id FROM apartment WHERE owner_user_id = ?", (uid,))["id"]
    db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "uid": "skip-cal",
            "date_from": "2026-08-01",
            "date_to": "2026-08-03",
            "registration_completed_at": at,
            "created_at": at,
            "updated_at": at,
        },
    )
    captured: list[dict] = []

    def fake_urlopen(request, timeout=0):
        captured.append(json.loads(request.data.decode()))
        return _ok_response()

    with patch("urllib.request.urlopen", fake_urlopen):
        posthog_sync.sync()
    events = [body["event"] for body in captured if body["distinct_id"] == str(uid)]
    assert "first_guest" in events
    assert not any(body["event"] == "first_calendar" for body in captured)


def test_partial_failure_resumes_without_duplicates(posthog_on):
    uid = _seed_host_at(4)
    captured: list[dict] = []
    sent_for_uid = 0

    def flaky_urlopen(request, timeout=0):
        body = json.loads(request.data.decode())
        if body.get("distinct_id") != str(uid):
            return _ok_response()
        nonlocal sent_for_uid
        if sent_for_uid >= 2:
            raise HTTPError(request.full_url, 503, "down", {}, None)
        captured.append(body)
        sent_for_uid += 1
        return _ok_response()

    with patch("urllib.request.urlopen", flaky_urlopen):
        posthog_sync.sync()
    our_events = [body["event"] for body in captured if body["distinct_id"] == str(uid)]
    assert len(our_events) == 2
    stored = db.query_one("SELECT posthog_stage FROM user_account WHERE id = ?", (uid,))
    assert stored["posthog_stage"] == our_events[1]

    captured.clear()

    def fake_urlopen(request, timeout=0):
        captured.append(json.loads(request.data.decode()))
        return _ok_response()

    with patch("urllib.request.urlopen", fake_urlopen):
        posthog_sync.sync()
    resumed = [body["event"] for body in captured if body["distinct_id"] == str(uid)]
    row = next(r for r in admin_funnel.rows()["rows"] if r["id"] == uid)
    expected = []
    for key, column in admin_funnel.stages():
        if row.get(column):
            expected.append(key)
        if key == row["stage"]:
            break
    assert resumed[0] == expected[2]
    assert resumed[0] != expected[0]


def test_event_uuid_is_stable(posthog_on):
    uid = _seed_host_at(4)
    uuids_first: list[str] = []

    def fake_urlopen(request, timeout=0):
        body = json.loads(request.data.decode())
        if body.get("distinct_id") == str(uid):
            uuids_first.append(body["uuid"])
        return _ok_response()

    with patch("urllib.request.urlopen", fake_urlopen):
        posthog_sync.sync()
    db.execute("UPDATE user_account SET posthog_stage = NULL WHERE id = ?", (uid,))
    uuids_second: list[str] = []

    def fake_again(request, timeout=0):
        body = json.loads(request.data.decode())
        if body.get("distinct_id") == str(uid):
            uuids_second.append(body["uuid"])
        return _ok_response()

    with patch("urllib.request.urlopen", fake_again):
        posthog_sync.sync()
    assert uuids_first == uuids_second
