"""One host cannot add the same calendar link twice (task 0026)."""
from __future__ import annotations

from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app import auth, db, feed_url, icalsync
from app.main import app
from tests.conftest import login_as

URL = "https://www.airbnb.com/calendar/ical/123.ics?s=abc"
USERS = ("dupfeed-a", "dupfeed-b")


@pytest.fixture
def homes(monkeypatch):
    db.init_db()
    _cleanup()
    # No network in tests: accept the link as typed and import nothing.
    monkeypatch.setattr(feed_url, "validate_calendar_url", lambda url: url.strip())
    monkeypatch.setattr(icalsync, "sync_all", lambda apartment_id: {"created": 0, "errors": 0})
    out = {}
    now = db.utcnow()
    for username in USERS:
        owner = auth.create_account(f"{username}@example.test", username, username=username)
        entity = db.insert(
            "legal_entity",
            {"name": username, "seat": "Praha", "created_at": now, "owner_user_id": owner},
        )
        flats = []
        for n, name in enumerate(("Flat A", "Flat B")):
            flats.append(
                db.insert(
                    "apartment",
                    {
                        "legal_entity_id": entity,
                        "owner_user_id": owner,
                        "internal_name": name,
                        "permalink_token": f"{username}-tok-{n}",
                        "automation_mode": "manual",
                        "default_purpose": "10",
                        "active": 1,
                        "created_at": now,
                    },
                )
            )
        out[username] = flats
    yield out
    _cleanup()


def _cleanup():
    for username in USERS:
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (username,)):
            oid = row["id"]
            for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
                db.execute("DELETE FROM ical_feed WHERE apartment_id = ?", (apt["id"],))
                db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
            db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
            db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
            db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _add(username, apartment_id, url=URL):
    client = TestClient(app)
    login_as(client, username, url="/login?lang=en", follow_redirects=False)
    return client.post(
        f"/apartments/{apartment_id}/feeds",
        data={"url": url, "label": "Airbnb", "own_name": "Airbnb"},
        follow_redirects=False,
    )


def _count(apartment_id):
    return len(db.query("SELECT id FROM ical_feed WHERE apartment_id = ?", (apartment_id,)))


def test_the_same_link_on_a_second_property_of_the_same_host_is_refused(homes):
    flat_a, flat_b = homes["dupfeed-a"]
    assert _add("dupfeed-a", flat_a).status_code == 303
    response = _add("dupfeed-a", flat_b)
    assert response.status_code == 303
    assert "already added to Flat A" in unquote(response.headers["location"])
    assert _count(flat_a) == 1
    assert _count(flat_b) == 0


def test_the_same_link_twice_on_one_property_is_refused(homes):
    flat_a, _ = homes["dupfeed-a"]
    _add("dupfeed-a", flat_a)
    response = _add("dupfeed-a", flat_a)
    assert "already added to Flat A" in unquote(response.headers["location"])
    assert _count(flat_a) == 1


def test_another_host_may_use_the_same_link(homes):
    _add("dupfeed-a", homes["dupfeed-a"][0])
    other = homes["dupfeed-b"][0]
    response = _add("dupfeed-b", other)
    assert "already added" not in unquote(response.headers["location"])
    assert _count(other) == 1


def test_a_different_link_on_the_second_property_is_fine(homes):
    flat_a, flat_b = homes["dupfeed-a"]
    _add("dupfeed-a", flat_a)
    response = _add("dupfeed-a", flat_b, url=URL + "-other")
    assert "already added" not in unquote(response.headers["location"])
    assert _count(flat_b) == 1
