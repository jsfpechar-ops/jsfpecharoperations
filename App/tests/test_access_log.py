"""OPS-3: one PII-free access line per request, and a switch to turn it off.

uvicorn's own access log records the raw request line, which includes guest
permalink tokens and query strings. The app's line carries the matched route
template instead (``/l/{token}``), never a path, query, IP or user agent.
"""
from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app import config, db
from app.main import app

ACCESS_LOGGER = "ubyhost.access"


def _records(caplog, name: str = ACCESS_LOGGER) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == name]


def _all_messages(caplog) -> str:
    return " ".join(record.getMessage() for record in caplog.records)


def test_a_guest_permalink_token_never_reaches_the_log(caplog):
    db.init_db()
    token = "a1b2c3d4e5f6g7h8i9j0" * 2  # real-looking, 40 chars
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        TestClient(app).get(f"/l/{token}")

    lines = _records(caplog)
    assert lines, "the app logged nothing for the request"
    assert any("route=/l/{token}" in line for line in lines), lines
    assert token not in _all_messages(caplog)


def test_a_query_string_and_email_never_reach_the_log(caplog):
    db.init_db()
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        TestClient(app).get("/?lang=cs&email=guest@example.test")

    lines = _records(caplog)
    assert lines
    joined = _all_messages(caplog)
    assert "guest@example.test" not in joined
    assert "lang=" not in joined


def test_static_and_healthz_are_not_logged(caplog):
    db.init_db()
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        client.get("/healthz")
        client.get("/static/app.css")
    assert _records(caplog) == []


def test_the_access_log_can_be_switched_off(monkeypatch, caplog):
    db.init_db()
    monkeypatch.setattr(config, "ACCESS_LOG", False)
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        TestClient(app).get("/")
    assert _records(caplog) == []


def _line_for(caplog, **headers) -> str:
    db.init_db()
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        TestClient(app).get("/", headers=headers)
    lines = _records(caplog)
    assert lines
    return lines[-1]


def test_a_plain_request_line_has_no_kind(caplog):
    line = _line_for(caplog)
    assert "kind=" not in line
    assert line.endswith(tuple("0123456789"))  # still ends with lock_ms=<n>


def test_prefetch_requests_are_tagged(caplog):
    assert _line_for(caplog, **{"X-Sec-Purpose": "prefetch"}).endswith(" kind=prefetch")


def test_sec_purpose_prefetch_wins_over_background(caplog):
    line = _line_for(caplog, **{"Sec-Purpose": "Prefetch;anonymous-client-ip", "X-Uby-Background": "1"})
    assert line.endswith(" kind=prefetch")


def test_background_polls_are_tagged(caplog):
    assert _line_for(caplog, **{"X-Uby-Background": "1"}).endswith(" kind=poll")
