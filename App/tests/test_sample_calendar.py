"""Bundled sample Airbnb calendar used by demo mode."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import icalsync
from app.main import app
from app.sample_calendar import sample_airbnb_ics


def test_sample_airbnb_ics_contains_expected_stays():
    body = sample_airbnb_ics()
    today = date.today()

    assert "BEGIN:VCALENDAR" in body
    assert "END:VCALENDAR" in body
    assert f"DTSTART;VALUE=DATE:{today:%Y%m%d}" in body
    assert (
        f"DTSTART;VALUE=DATE:{(today - timedelta(days=1)):%Y%m%d}" in body
    )
    assert "SUMMARY:Reserved" in body
    assert "SUMMARY:Airbnb (Not available)" in body
    assert "Phone Number (Last 4 Digits): 0431" in body


def test_sample_airbnb_ics_parses_into_reservations():
    events = icalsync.parse_events(sample_airbnb_ics())
    reservations = [event for event in events if not event["is_block"]]
    assert len(reservations) == 3
    assert all(event["date_from"] and event["date_to"] for event in reservations)


def test_sample_calendar_endpoint_serves_ics():
    client = TestClient(app)
    response = client.get("/sample-airbnb.ics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in response.text
