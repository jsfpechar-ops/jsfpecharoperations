"""The Overview has to name the right next step on an empty workspace.

With no calendar connected the page offered three dead ends at once: a header
"Update calendars" that syncs zero calendars, an empty state that blamed the
calendars for having nothing booked, and a "Finish setup" panel repeating what
the onboarding banner already said. Now the header sync waits for a feed, the
empty state asks for a calendar, and the setup panel gives way to the banner.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "dashboard-empty-host"


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _owner_id():
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


@pytest.fixture
def host():
    """An owner with one entity and one property that is missing everything."""
    db.init_db()
    _cleanup()
    auth.create_account(USERNAME, PASSWORD, "Dashboard Host", must_change_password=False)
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Dashboard s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@dashboard.test",
            "owner_user_id": _owner_id(),
            "created_at": db.utcnow(),
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": _owner_id(),
            "internal_name": "Empty Flat",
            "addr_obec": "Praha",
            "addr_house_no": "12",
            "addr_zip": "12000",
            "permalink_token": "dashboardempty1",
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    try:
        yield client, apartment_id
    finally:
        _cleanup()


def _add_feed(apartment_id: int) -> None:
    db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": "https://example.test/feed.ics",
            "label": "Airbnb",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )


def test_without_a_calendar_the_empty_state_asks_for_one(host):
    client, apartment_id = host

    page = client.get("/?lang=en")

    assert page.status_code == 200
    assert (
        "No stays yet. Connect a booking calendar so arrivals appear here automatically."
        in page.text
    )
    assert f'href="/apartments/{apartment_id}#calendars"' in page.text
    assert "Connect a calendar" in page.text


def test_without_a_calendar_the_empty_state_does_not_blame_the_calendars(host):
    client, _ = host

    page = client.get("/?lang=en")

    assert "Either the calendars have nothing booked" not in page.text
    assert "Update calendars now" not in page.text


def test_the_header_sync_button_waits_for_a_calendar(host):
    client, apartment_id = host

    without = client.get("/?lang=en")

    assert "Update calendars</span>" not in without.text

    _add_feed(apartment_id)

    with_feed = client.get("/?lang=en")

    assert "Update calendars" in with_feed.text
    assert "Either the calendars have nothing booked" in with_feed.text
    assert "No stays yet. Connect a booking calendar" not in with_feed.text


def test_the_empty_state_asks_for_a_calendar_in_czech(host):
    client, _ = host

    page = client.get("/?lang=cs")

    assert "Zatím žádné pobyty. Připojte kalendář rezervací a příjezdy se tu objeví samy." in page.text
    assert "Připojit kalendář" in page.text
    assert "Aktualizovat kalendáře" not in page.text


def test_the_finish_setup_panel_gives_way_to_the_banner(host):
    client, _ = host

    page = client.get("/?lang=en")

    assert "Finish setup" not in page.text
    assert 'class="onboarding-banner"' in page.text


def test_the_finish_setup_panel_returns_when_the_banner_is_hidden(host):
    client, _ = host
    client.post("/onboarding/dismiss", data={"return_to": "/"}, follow_redirects=False)

    page = client.get("/?lang=en")

    assert "Finish setup" in page.text
    assert 'class="onboarding-banner"' not in page.text
