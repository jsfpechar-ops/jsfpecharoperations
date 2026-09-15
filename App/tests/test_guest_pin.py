"""Guest PIN gate must cover every mutating route, not only GET pages."""
from __future__ import annotations

import base64
import re
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app import auth, db, passport_photos
from app.main import app

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
PNG_BYTES = base64.b64decode(SIGNATURE.split(",", 1)[1])

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
    guests = db.query("SELECT id FROM guest WHERE reservation_id IN "
                      "(SELECT id FROM reservation WHERE apartment_id = ?)", (apartment["id"],))
    for guest in guests:
        passport_photos.delete_photo(guest["id"])
    db.execute("DELETE FROM guest WHERE reservation_id IN "
               "(SELECT id FROM reservation WHERE apartment_id = ?)", (apartment["id"],))
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


def test_pin_page_accepts_the_length_the_app_generates(pin_required):
    """A 6-digit PIN in a maxlength=4 box cannot be typed at all."""
    generated = auth.new_permalink_pin()
    assert len(generated) == 6
    assert auth.normalise_permalink_pin(generated) == generated

    stay_id = _stay_id()
    try:
        db.execute(
            "UPDATE apartment SET permalink_pin = ? WHERE permalink_token = ?",
            (generated, TOKEN),
        )
        client = TestClient(app)
        page = client.get(f"/l/{TOKEN}", follow_redirects=False)
        assert page.status_code == 200
        field = re.search(r"<input[^>]*name=\"pin\"[^>]*>", page.text, re.S)
        assert field, "the PIN page should render a pin input"
        markup = field.group(0)
        assert 'maxlength="6"' in markup, markup
        assert "[0-9]{4}|[0-9]{6}" in markup, markup

        accepted = client.post(
            f"/l/{TOKEN}/pin",
            data={"pin": generated, "return_to": f"/l/{TOKEN}"},
            follow_redirects=False,
        )
        assert accepted.status_code == 303
        # A legacy 4-digit PIN must keep working for links already sent out.
        db.execute(
            "UPDATE apartment SET permalink_pin = ? WHERE permalink_token = ?",
            (PIN, TOKEN),
        )
        legacy = TestClient(app).post(
            f"/l/{TOKEN}/pin",
            data={"pin": PIN, "return_to": f"/l/{TOKEN}"},
            follow_redirects=False,
        )
        assert legacy.status_code == 303
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
                "signature": SIGNATURE,
                "legal_ack": "1",
            },
            files={"passport_photo": ("passport.png", PNG_BYTES, "image/png")},
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


def test_rotating_pin_invalidates_existing_pin_session(pin_required):
    _stay_id()
    try:
        client = _with_pin(TestClient(app))
        db.execute(
            "UPDATE apartment SET permalink_pin = ? WHERE permalink_token = ?",
            ("654321", TOKEN),
        )

        page = client.get(f"/l/{TOKEN}", follow_redirects=False)

        assert page.status_code == 200
        assert 'name="pin"' in page.text
    finally:
        _cleanup()


def test_wrong_pin_delay_does_not_block_event_loop(pin_required, monkeypatch):
    _stay_id()
    delayed = AsyncMock()
    monkeypatch.setattr("app.routes.guest.asyncio.sleep", delayed)
    try:
        response = TestClient(app).post(
            f"/l/{TOKEN}/pin",
            data={"pin": "9999"},
            follow_redirects=False,
        )

        assert response.status_code == 200
        delayed.assert_awaited_once()
    finally:
        db.execute("DELETE FROM rate_limit_event WHERE key LIKE ?", (f"%:{TOKEN}",))
        _cleanup()
