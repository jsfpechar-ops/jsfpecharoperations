"""Hosts can open the guest form from stay menus without the PIN gate."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db
from app.main import app

PASSWORD = "Secure-Password-123"
TOKEN = "hostform-token"
PIN = "246810"


@pytest.fixture
def pin_required(monkeypatch):
    monkeypatch.setenv("UBYHOST_GUEST_PIN", "1")
    monkeypatch.setattr("app.config.GUEST_PIN_REQUIRED", True)


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    if apartment["legal_entity_id"]:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))
    db.execute("DELETE FROM user_account WHERE username = ?", ("host-guest-form",))


def _host_stay():
    db.init_db()
    _cleanup()
    db.execute("DELETE FROM user_account WHERE username = ?", ("host-guest-form",))
    owner_id = auth.create_account(
        "host-guest-form", PASSWORD, role="host", must_change_password=False
    )
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Host Form s.r.o.",
            "seat": "Prague",
            "ico": "12345678",
            "contact_email": "host@example.com",
            "owner_user_id": owner_id,
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Host Form Studio",
            "permalink_token": TOKEN,
            "permalink_pin": PIN,
            "permalink_window_days": 14,
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    stay_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "host-form-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=2)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return owner_id, stay_id


def _host_client(owner_id: int) -> TestClient:
    account = db.query_one("SELECT * FROM user_account WHERE id = ?", (owner_id,))
    client = TestClient(app)
    client.cookies.set(
        auth.SESSION_COOKIE,
        auth.issue_session(owner_id, account["session_version"]),
    )
    return client


def test_guest_still_needs_pin_without_a_host_session(pin_required):
    _owner_id, stay_id = _host_stay()
    try:
        guest = TestClient(app)
        page = guest.get(f"/l/{TOKEN}/{stay_id}", follow_redirects=False)
        assert page.status_code == 200
        assert "PIN" in page.text
    finally:
        _cleanup()


def test_signed_in_host_opens_guest_form_without_pin(pin_required):
    owner_id, stay_id = _host_stay()
    try:
        client = _host_client(owner_id)
        overview = client.get("/")
        assert overview.status_code == 200
        assert f'href="/l/{TOKEN}/{stay_id}"' in overview.text
        assert "Open guest form" in overview.text

        stay = client.get(f"/reservations/{stay_id}")
        assert stay.status_code == 200
        assert "Open guest form" in stay.text

        form = client.get(f"/l/{TOKEN}/{stay_id}", follow_redirects=True)
        assert form.status_code == 200
        assert 'name="pin"' not in form.text
        assert f"/l/{TOKEN}/{stay_id}/save" in form.text
    finally:
        _cleanup()
