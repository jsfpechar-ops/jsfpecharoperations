"""BE-9: the Art 18 restriction flag is read-only, hidden from bulk exports, and
only blocks police filing when counsel has enabled the flag."""
from __future__ import annotations

import base64
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, housebook, reporting
from app.main import app

PASSWORD = "Secure-Password-123"
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = 'restrict-host'"):
        user_id = row["id"]
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        for apartment in db.query(
            "SELECT id FROM apartment WHERE owner_user_id = ?", (user_id,)
        ):
            apartment_id = apartment["id"]
            db.execute(
                "DELETE FROM guest WHERE reservation_id IN "
                "(SELECT id FROM reservation WHERE apartment_id = ?)",
                (apartment_id,),
            )
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))
    db.execute(
        "DELETE FROM legal_entity WHERE name = 'Restriction entity' AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)"
    )


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def _seed():
    db.init_db()
    now = db.utcnow()
    today = date.today()
    owner = auth.create_account(
        "restrict-host", PASSWORD, "Restrict", must_change_password=False
    )
    entity = db.insert(
        "legal_entity",
        {"name": "Restriction entity", "owner_user_id": owner, "created_at": now},
    )
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": owner,
            "internal_name": "Restriction flat",
            "permalink_token": "restricttok",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    reservation = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "uid": "restriction-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "expected_guests_override": 1,
            "created_at": now,
            "updated_at": now,
        },
    )
    guest = db.insert(
        "guest",
        {
            "reservation_id": reservation,
            "surname": "Smith",
            "first_name": "John",
            "birth_date": "01011990",
            "nationality": "GBR",
            "doc_number": "P1234567",
            "res_street": "Street 1",
            "res_city": "London",
            "res_country": "GBR",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "host",
            "signature_png": SIGNATURE,
            "signed_at": now,
            "identity_verified_at": now,
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )
    return owner, apartment, reservation, guest


def _login() -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": "restrict-host", "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def test_restricting_and_unrestricting_are_recorded():
    _owner, _apartment, _reservation, guest = _seed()
    client = _login()
    assert client.post(
        f"/guests/{guest}/restrict", data={"reason": "dispute"}, follow_redirects=False
    ).status_code == 303
    row = db.query_one("SELECT * FROM guest WHERE id = ?", (guest,))
    assert row["restricted_at"]
    assert row["restricted_reason"] == "dispute"

    assert client.post(
        f"/guests/{guest}/unrestrict", follow_redirects=False
    ).status_code == 303
    row = db.query_one("SELECT * FROM guest WHERE id = ?", (guest,))
    assert row["restricted_at"] is None


def test_a_restricted_guest_cannot_be_edited_by_the_host():
    _owner, _apartment, _reservation, guest = _seed()
    client = _login()
    client.post(f"/guests/{guest}/restrict", data={}, follow_redirects=False)
    response = client.post(
        f"/guests/{guest}",
        data={
            "surname": "Changed",
            "first_name": "John",
            "birth_date": "01011990",
            "nationality": "GBR",
            "doc_number": "P1234567",
            "purpose": "10",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert db.query_one("SELECT surname FROM guest WHERE id = ?", (guest,))["surname"] == "Smith"


def test_a_restricted_guest_is_hidden_from_the_housebook_export():
    owner, _apartment, _reservation, guest = _seed()
    client = _login()
    client.post(f"/guests/{guest}/restrict", data={}, follow_redirects=False)
    assert housebook.housebook_rows(owner_user_id=owner) == []

    client.post(f"/guests/{guest}/unrestrict", follow_redirects=False)
    assert len(housebook.housebook_rows(owner_user_id=owner)) == 1


def test_filing_is_only_blocked_when_the_counsel_flag_is_on(monkeypatch):
    _owner, apartment, _reservation, guest = _seed()
    db.update("guest", guest, {"restricted_at": db.utcnow()})

    monkeypatch.setattr(config, "RESTRICTED_BLOCKS_FILING", False)
    assert any(
        g["id"] == guest
        for g, _r in reporting.collect_sendable(apartment, ignore_automation=True)
    )

    monkeypatch.setattr(config, "RESTRICTED_BLOCKS_FILING", True)
    assert not any(
        g["id"] == guest
        for g, _r in reporting.collect_sendable(apartment, ignore_automation=True)
    )
