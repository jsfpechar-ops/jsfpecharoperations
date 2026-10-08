"""A TTLock lock serves one property: it must not look attached to every property."""
from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db
from app.main import app
from tests.conftest import login_as

USERNAME = "onelock-host"
LOCK = {"lock_id": "35662508", "alias": "Vivus_A41", "battery": 80, "tz_offset_ms": 3600000}


@pytest.fixture
def two_properties(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    _cleanup()
    owner = auth.create_account(f"{USERNAME}@example.test", "One Lock", username=USERNAME)
    now = db.utcnow()
    entity = db.insert(
        "legal_entity",
        {"name": "One Lock", "seat": "Praha", "created_at": now, "owner_user_id": owner},
    )
    ids = []
    for n, name in enumerate(("Flat A", "Flat B")):
        ids.append(
            db.insert(
                "apartment",
                {
                    "legal_entity_id": entity,
                    "owner_user_id": owner,
                    "internal_name": name,
                    "permalink_token": f"onelock-tok-{n}",
                    "automation_mode": "manual",
                    "default_purpose": "10",
                    "active": 1,
                    "created_at": now,
                },
            )
        )
    db.insert(
        "lock_account",
        {
            "owner_user_id": owner,
            "provider": "ttlock",
            "username": "x_onelock",
            "status": "ok",
            "locks_json": json.dumps([LOCK]),
            "created_at": now,
            "updated_at": now,
        },
    )
    yield owner, entity, ids
    _cleanup()


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        oid = row["id"]
        for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
            db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _client() -> TestClient:
    client = TestClient(app)
    login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    return client


def _save(client, apartment_id: int, entity: int, *, lock: bool):
    data = {
        "internal_name": _apartment(apartment_id)["internal_name"],
        "legal_entity_id": str(entity),
        "door_code_section": "1",
        "lock_id": LOCK["lock_id"],
        "checkin_hour": "15",
        "checkout_hour": "10",
    }
    if lock:
        data["door_codes"] = "1"
    return client.post(f"/apartments/{apartment_id}", data=data, follow_redirects=False)


def _apartment(apartment_id: int):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))


def test_a_lock_in_use_cannot_be_given_to_a_second_property(two_properties):
    _, entity, (a, b) = two_properties
    client = _client()
    assert _save(client, a, entity, lock=True).status_code == 303
    assert _apartment(a)["lock_provider"] == "ttlock"

    _save(client, b, entity, lock=True)
    assert _apartment(b)["lock_provider"] is None


def test_the_second_property_does_not_offer_or_preselect_the_taken_lock(two_properties):
    _, entity, (a, b) = two_properties
    client = _client()
    _save(client, a, entity, lock=True)
    page = client.get(f"/apartments/{b}").text
    option = re.search(r'<option value="35662508"[^>]*>', page)
    assert option, "the lock should still be listed so the host sees why it is unavailable"
    assert "disabled" in option.group(0)
    assert "selected" not in option.group(0)
    assert "in use by Flat A" in page


def test_a_lone_free_lock_is_still_preselected(two_properties):
    _, _, (a, b) = two_properties
    page = _client().get(f"/apartments/{a}").text
    option = re.search(r'<option value="35662508"[^>]*>', page)
    assert option and "selected" in option.group(0) and "disabled" not in option.group(0)


def test_the_property_that_owns_the_lock_can_still_be_edited(two_properties):
    _, entity, (a, _) = two_properties
    client = _client()
    _save(client, a, entity, lock=True)
    assert _save(client, a, entity, lock=True).status_code == 303
    assert _apartment(a)["lock_provider"] == "ttlock"


def test_switching_it_off_frees_the_lock_for_another_property(two_properties):
    _, entity, (a, b) = two_properties
    client = _client()
    _save(client, a, entity, lock=True)
    _save(client, a, entity, lock=False)
    _save(client, b, entity, lock=True)
    assert _apartment(b)["lock_provider"] == "ttlock"
    assert _apartment(a)["lock_provider"] is None
