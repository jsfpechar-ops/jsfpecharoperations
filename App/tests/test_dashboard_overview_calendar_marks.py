"""Overview calendar strip: one neutral label for placeholders, source carried as a mark.

Placeholders from Airbnb and Booking.com used to show the portal text ("Reserved",
"Booking"). Every placeholder now reads "Booked"; the source travels in the bar's
title and aria-label and as a logo in the template. A stay that covers today is
drawn in the "now" colour, not the green "done" one.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.routes import admin, dashboard_calendar


def test_overview_calendar_placeholders_share_one_label_and_carry_source(monkeypatch):
    today = date(2026, 11, 9)
    apartments = [{"id": 1, "active": 1, "internal_name": "Calendar test home"}]
    events = [
        {"propertyId": 1, "start": (today - timedelta(days=2)).isoformat(),
         "end": (today + timedelta(days=3)).isoformat(), "tone": "done", "source": "airbnb",
         "label": "Reserved", "guests": 0, "url": "/reservations/1"},
        {"propertyId": 1, "start": (today + timedelta(days=5)).isoformat(),
         "end": (today + timedelta(days=7)).isoformat(), "tone": "done", "source": "booking",
         "label": "CLOSED - Not available", "guests": 0, "url": "/reservations/2"},
        {"propertyId": 1, "start": (today - timedelta(days=1)).isoformat(),
         "end": (today + timedelta(days=2)).isoformat(), "tone": "done", "source": "direct",
         "label": "Novak", "guests": 2, "url": "/reservations/3"},
    ]
    monkeypatch.setattr(dashboard_calendar, "events", lambda owner, start, end, apartment_id=None: events)

    rows = admin._overview_calendar_rows(1, apartments, today, "en")
    bars = rows[0]["bars"]
    by_source = {bar["source"]: bar for bar in bars}

    airbnb, booking, direct = by_source["airbnb"], by_source["booking"], by_source["direct"]
    assert airbnb["label"] == booking["label"] == "Booked"
    assert "Booking" not in {bar["label"] for bar in bars}
    assert "Reserved" not in {bar["label"] for bar in bars}
    assert airbnb["source_label"] == "Airbnb"
    assert booking["source_label"] == "Booking"
    assert airbnb["title"] == "Airbnb · Booked"
    assert booking["title"] == "Booking · Booked"
    assert direct["source_label"] == ""
    assert direct["title"] == "Novak · 2"
    assert direct["label"] == "Novak · 2"
    assert direct["css"] == "b-now"
