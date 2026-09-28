"""BE-7/FE-6: an incomplete controller warns the host, and never blocks the guest.

Decision G-D9 overrides the plan's "block new claims/forms": the guest form keeps
working, a critical alert tells the host, and saving the entity clears it.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db
from app.main import app
from app.routes import admin
from tests.conftest import complete_guest_claim

PASSWORD = "Secure-Password-123"
TOKEN = "controllertok"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = 'controller-host'"):
        user_id = row["id"]
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))
    db.execute(
        "DELETE FROM legal_entity WHERE name = 'Controller entity' AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)"
    )


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def _seed(*, complete: bool = False):
    """A host, an entity (complete or not) and one active stay."""
    now = db.utcnow()
    today = claim.prague_today()
    host = auth.create_account(
        "controller-host", PASSWORD, "Controller", must_change_password=False
    )
    entity = db.insert(
        "legal_entity",
        {
            "name": "Controller entity",
            "seat": "Praha 1" if complete else None,
            "ico": "12345678" if complete else None,
            "contact_email": "pm@example.test" if complete else None,
            "owner_user_id": host,
            "created_at": now,
        },
    )
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": host,
            "internal_name": "Controller flat",
            "uby_name": "Controller Facility",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "passport_photo_policy": "off",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    reservation = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "source": "airbnb",
            "uid": "controller-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "declared_guests": 1,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return host, entity, apartment, reservation


def test_an_incomplete_controller_warns_the_host_without_blocking_the_guest():
    _host, _entity, apartment, reservation = _seed(complete=False)
    client = TestClient(app)

    pick = client.get(f"/l/{TOKEN}")
    assert pick.status_code == 200, pick.text

    alert = db.query_one(
        "SELECT * FROM alert WHERE dedupe_key = ?", (f"controller_missing:{apartment}",)
    )
    assert alert is not None
    assert alert["kind"] == "controller_missing"
    assert alert["level"] == "critical"
    assert alert["owner_user_id"]

    # The form itself is still reachable after claiming.
    complete_guest_claim(client, TOKEN, reservation, party_size=1, lang="en")
    new_form = client.get(f"/l/{TOKEN}/{reservation}/new?lang=en")
    assert new_form.status_code == 200, new_form.text

    # A second visit refreshes the same card, it does not add another.
    client.get(f"/l/{TOKEN}")
    rows = db.query(
        "SELECT id FROM alert WHERE dedupe_key = ?", (f"controller_missing:{apartment}",)
    )
    assert len(rows) == 1


def test_saving_a_complete_entity_clears_the_alert():
    host, entity, apartment, _reservation = _seed(complete=False)
    client = TestClient(app)
    client.get(f"/l/{TOKEN}")
    assert db.query_one(
        "SELECT id FROM alert WHERE dedupe_key = ?", (f"controller_missing:{apartment}",)
    )

    login = client.post(
        "/login?lang=en",
        data={"username": "controller-host", "password": PASSWORD},
        follow_redirects=False,
    )
    assert login.status_code == 303
    saved = client.post(
        f"/entities/{entity}",
        data={
            "name": "Controller entity",
            "seat": "Praha 1",
            "contact_email": "pm@example.test",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303, saved.text

    alert = db.query_one(
        "SELECT resolved_at FROM alert WHERE dedupe_key = ?", (f"controller_missing:{apartment}",)
    )
    assert alert["resolved_at"]


def test_the_readiness_checklist_lists_the_controller_item():
    _host, entity, apartment, _reservation = _seed(complete=False)
    apartment_row = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment,))
    entity_row = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity,))

    incomplete = admin._readiness(apartment_row, [entity_row], [], False)
    by_key = {item["key"]: item for item in incomplete["invite"]}
    assert "controller" in by_key
    assert by_key["controller"]["done"] is False

    db.update("legal_entity", entity, {"seat": "Praha 1", "contact_email": "pm@example.test"})
    entity_row = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity,))
    complete = admin._readiness(apartment_row, [entity_row], [], False)
    assert {item["key"]: item for item in complete["invite"]}["controller"]["done"] is True
