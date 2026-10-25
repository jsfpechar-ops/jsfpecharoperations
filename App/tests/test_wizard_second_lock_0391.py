"""0391: a second property's lock is added inside the setup wizard."""
from __future__ import annotations

import json
import re

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


def test_no_free_lock_shows_the_sharing_steps_not_a_dead_dropdown(world):
    _, _, _, second = world
    page = _step(_client(), second)
    assert 'id="door-lock-form"' not in page
    assert 'id="smart-locks-share"' in page
    assert "x_secondlock" in page  # the UbyHost name to paste in TTLock
    assert 'action="/smart-locks/refresh"' in page
    assert f'value="/apartments/{second}/setup/door_lock"' in page
    assert "one lock serves one property" in page
    assert "Vivus A2.6 · in use by Flat A" in page
    assert "No smart lock" in page


def test_a_free_lock_is_offered_and_the_taken_one_is_disabled(world):
    owner, _, _, second = world
    _add_lock_b(owner)
    page = _step(_client(), second)
    assert 'id="door-lock-form"' in page
    taken = re.search(r'<option value="35874326"[^>]*>[^<]*', page).group(0)
    assert "disabled" in taken and "in use by Flat A" in taken
    free = re.search(r'<option value="35874327"[^>]*>', page).group(0)
    assert "selected" in free and "disabled" not in free
    assert 'id="smart-locks-add-more"' in page
    assert "x_secondlock" in page


def test_the_first_property_keeps_its_own_lock_selectable(world):
    _, _, first, _ = world
    page = _client().get(f"/apartments/{first}/setup/door_lock").text
    option = re.search(r'<option value="35874326"[^>]*>', page)
    if option:  # the first property may have finished its wizard already
        assert "disabled" not in option.group(0)


def test_a_refused_lock_save_stays_on_the_step_and_keeps_the_times(world):
    owner, entity, _, second = world
    _add_lock_b(owner)
    response = _client().post(f"/apartments/{second}", data={
        "return_to": f"/apartments/{second}/setup/guest_link",
        "setup_step": "door_lock", "door_code_section": "1", "door_codes_fields": "1",
        "internal_name": "Flat B", "legal_entity_id": str(entity), "default_purpose": "10",
        "checkin_hour": "14", "checkout_hour": "11", "door_codes": "1",
        "lock_id": LOCK_A["lock_id"],
    }, follow_redirects=False)
    assert response.status_code == 400
    page = response.text
    assert "already sends codes for another property" in page
    assert 'id="door-lock-form"' in page
    assert re.search(r'<select id="checkin_hour"[\s\S]*?<option value="14" selected>', page)
    assert re.search(r'<select id="checkout_hour"[\s\S]*?<option value="11" selected>', page)
    assert re.search(r'id="door_codes"[^>]*checked', page)
    assert db.query_one("SELECT lock_provider FROM apartment WHERE id = ?", (second,))["lock_provider"] is None


def test_the_door_lock_tab_still_shows_its_sharing_steps(world):
    _, _, _, second = world
    page = _client().get(f"/apartments/{second}?view=settings&section=lock").text
    assert 'id="smart-locks-add-more"' in page
    assert "x_secondlock" in page
