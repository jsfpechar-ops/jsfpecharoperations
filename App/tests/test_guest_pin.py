"""Guest PIN gate must cover every mutating route, not only GET pages."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

TOKEN = "pingate-token"
PIN = "4321"


@pytest.fixture
def pin_required(monkeypatch):
    monkeypatch.setenv("UBYHOST_GUEST_PIN", "1")
    monkeypatch.setattr("app.config.GUEST_PIN_REQUIRED", True)


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def _stay_id() -> int:
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = date.today()
    entity_id = db.insert("legal_entity", {"name": "PIN gate test", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "PIN flat",
            "permalink_token": TOKEN,
            "permalink_pin": PIN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "pin-gate-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _with_pin(client: TestClient) -> TestClient:
    response = client.post(
        f"/l/{TOKEN}/pin",
        data={"pin": PIN, "return_to": f"/l/{TOKEN}"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def test_party_and_another_posts_require_pin(pin_required):
    stay_id = _stay_id()
    try:
        client = TestClient(app)
        blocked = client.post(
            f"/l/{TOKEN}/{stay_id}/party",
            data={"party_size": "4"},
            follow_redirects=False,
        )
        assert blocked.status_code == 200
        assert "PIN" in blocked.text
        assert db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (stay_id,)
        )["declared_guests"] is None

        blocked = client.post(f"/l/{TOKEN}/{stay_id}/another", follow_redirects=False)
        assert blocked.status_code == 200
        assert "PIN" in blocked.text

        client = _with_pin(TestClient(app))
        allowed = client.post(
            f"/l/{TOKEN}/{stay_id}/party",
            data={"party_size": "4"},
            follow_redirects=False,
        )
        assert allowed.status_code == 303
        assert db.query_one(
            "SELECT declared_guests FROM reservation WHERE id = ?", (stay_id,)
        )["declared_guests"] == 4
    finally:
        _cleanup()


def test_edit_form_requires_pin_before_owned_cookie(pin_required):
    stay_id = _stay_id()
    try:
        client = _with_pin(TestClient(app))
        saved = client.post(
            f"/l/{TOKEN}/{stay_id}/save",
            data={
                "surname": "Smith",
                "first_name": "John",
                "birth_date": "1.1.1990",
                "nationality": "GBR",
                "doc_number": "P1234567",
                "res_street": "Baker Street 221B",
                "res_city": "London",
                "res_country": "GBR",
                "purpose": "10",
                "party_size": "1",
                "signature": "data:image/png;base64,AA==",
            },
            follow_redirects=False,
        )
        assert saved.status_code == 303
        guest_id = db.query_one(
            "SELECT id FROM guest WHERE reservation_id = ?", (stay_id,)
        )["id"]

        edit = TestClient(app)
        edit.cookies.update(client.cookies)
        edit.cookies.pop("ubyhost_pin", None)
        page = edit.get(f"/l/{TOKEN}/{stay_id}/edit/{guest_id}", follow_redirects=False)
        assert page.status_code == 200
        assert "PIN" in page.text
    finally:
        _cleanup()
