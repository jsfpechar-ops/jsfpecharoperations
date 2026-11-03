"""0400: a second property's lock is added inside the setup wizard."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, property_setup
from app.main import app
from tests.conftest import login_as

USERNAME = "secondlock-host"
LOCK_A = {"lock_id": "35874326", "alias": "Vivus A2.6", "battery": 100, "tz_offset_ms": 3600000}
LOCK_B = {"lock_id": "35874327", "alias": "Garden door", "battery": 90, "tz_offset_ms": 3600000}


@pytest.fixture
def world(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    _cleanup()
    owner = auth.create_account(f"{USERNAME}@example.test", "Second Lock", username=USERNAME)
    now = db.utcnow()
    entity = db.insert(
        "legal_entity", {"name": "Second Lock", "seat": "Praha", "created_at": now, "owner_user_id": owner}
    )
    ids = []
    for n, name in enumerate(("Flat A", "Flat B")):
        ids.append(db.insert("apartment", {
            "legal_entity_id": entity, "owner_user_id": owner, "internal_name": name,
            "permalink_token": f"secondlock-tok-{n}", "permalink_pin": "123456",
            "automation_mode": "manual", "default_purpose": "10", "active": 1, "created_at": now,
            "addr_obec": "Praha", "addr_house_no": "1", "addr_zip": "11000",
            "lock_provider": "ttlock" if n == 0 else None,
            "lock_id": LOCK_A["lock_id"] if n == 0 else None,
            "checkin_hour": 15 if n == 0 else None, "checkout_hour": 10 if n == 0 else None,
        }))
    db.insert("lock_account", {
        "owner_user_id": owner, "provider": "ttlock", "username": "x_secondlock",
        "status": "ok", "locks_json": json.dumps([LOCK_A]), "created_at": now, "updated_at": now,
    })
    second = ids[1]
    property_setup.start(second)
    for step, mark in (("property", "done"), ("calendar", "skipped"), ("police", "waiting"),
                       ("automation", "done"), ("stay_fee", "skipped")):
        property_setup.mark(second, step, mark)
    yield owner, entity, ids[0], second
    _cleanup()


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        oid = row["id"]
        for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
            db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM settings WHERE key = ?", (f"property_setup:{apt['id']}",))
            db.execute("DELETE FROM apartment_slug WHERE apartment_id = ?", (apt["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _client() -> TestClient:
    client = TestClient(app)
    login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    return client


def _step(client, apartment_id):
    response = client.get(f"/apartments/{apartment_id}/setup/door_lock")
    assert response.status_code == 200
    return response.text


def _add_lock_b(owner):
    db.execute(
        "UPDATE lock_account SET locks_json = ? WHERE owner_user_id = ?",
        (json.dumps([LOCK_A, LOCK_B]), owner),
    )


def test_the_door_lock_tab_still_shows_its_sharing_steps(world):
    _, _, _, second = world
    page = _client().get(f"/apartments/{second}?view=settings&section=lock").text
    assert 'id="smart-locks-add-more"' in page
    assert "x_secondlock" in page
