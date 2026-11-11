"""Regression cover for PR #902: birth dates must persist as ASCII for the Go filer.

Unit tests in test_validation.py prove normalisation; these lock the guest save path
and Python/Go filing parity on non-ASCII values that must never be stored again.
"""
from __future__ import annotations

import base64
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import claim, db, mail
from app.main import app
from app.routes import guest

TOKEN = "birthasciitok"
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
ARABIC_DOB = "٠١.٠١.١٩٩٠"


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
    db.execute(
        "DELETE FROM legal_entity WHERE name = ? AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)",
        ("Birth ASCII",),
    )


def _seed() -> int:
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Birth ASCII", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "ASCII DOB flat",
            "uby_name": "ASCII Facility",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "passport_photo_policy": "off",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "birth-ascii-stay",
            "date_from": (today - timedelta(days=1)).isoformat(),
            "date_to": (today + timedelta(days=2)).isoformat(),
            "declared_guests": 1,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


@pytest.fixture(autouse=True)
def _no_mail(monkeypatch):
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)
    yield
    _cleanup()


def _client() -> TestClient:
    client = TestClient(app)
    client.cookies.set(guest.LANG_COOKIE, "en")
    return client


def test_guest_save_stores_ascii_birth_date_from_arabic_keypad():
    rid = _seed()
    client = _client()
    response = client.post(
        f"/l/{TOKEN}/{rid}/save?lang=en",
        data={
            "surname": "Nguyen",
            "first_name": "Lan",
            "birth_date": ARABIC_DOB,
            "nationality": "VNM",
            "doc_number": "P99887766",
            "res_street": "Le Loi 5",
            "res_city": "Hanoi",
            "res_country": "VNM",
            "purpose": "10",
            "party_size": "1",
            "signature": SIGNATURE,
            "legal_ack": "1",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    row = db.query_one("SELECT * FROM guest WHERE reservation_id = ?", (rid,))
    assert row is not None
    assert row["birth_date"] == "01011990"
    assert row["birth_date"].isascii()
    assert row["birth_date_enc"]
