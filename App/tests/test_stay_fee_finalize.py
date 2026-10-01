"""Sealed stay-fee periods: finalize then frozen PDF/CSV bytes."""
from __future__ import annotations

import secrets
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, stay_fee_filing
from app.main import app

PASSWORD = f"Stay-fee-finalize-{secrets.token_urlsafe(12)}-9"
SIGNATURE = "data:image/png;base64,AAAA"


def _cleanup():
    for user in db.query("SELECT id FROM user_account WHERE username LIKE 'stay-fee-finalize-%'"):
        owner_id = user["id"]
        db.execute(
            "DELETE FROM stay_fee_filing WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN (SELECT id FROM reservation "
            "WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?))",
            (owner_id,),
        )
        db.execute(
            "DELETE FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (owner_id,),
        )
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    _cleanup()
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 9, 30))
    owner_id = auth.create_account(
        "stay-fee-finalize-owner",
        PASSWORD,
        "Finalize Demo",
        role="host",
        must_change_password=False,
    )
    entity_id = db.insert("legal_entity", {
        "name": "Finalize Demo s.r.o.",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    assert client.post(
        "/login?lang=en",
        data={"username": "stay-fee-finalize-owner", "password": PASSWORD},
        follow_redirects=False,
    ).status_code == 303
    try:
        yield client, owner_id, entity_id
    finally:
        _cleanup()


def _property(owner_id, entity_id):
    return db.insert("apartment", {
        "internal_name": "Finalize Flat",
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "stay_fee_rate_czk": 50,
        "stay_fee_vs": "123456",
        "stay_fee_authority_name": "Městský úřad",
        "stay_fee_council_account": "19-2000781379/0800",
        "stay_fee_council_iban": "CZ3008000000192000781379",
        "created_at": db.utcnow(),
    })


def _stay(apartment_id):
    now = db.utcnow()
    rid = db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": "fin-1",
        "date_from": "2026-08-10",
        "date_to": "2026-08-14",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    db.insert("guest", {
        "reservation_id": rid,
        "first_name": "Ada",
        "surname": "Guest",
        "birth_date": "01011990",
        "nationality": "DEU",
        "signature_png": SIGNATURE,
        "created_at": now,
        "updated_at": now,
    })


def test_finalize_then_downloads_are_frozen(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    page = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert page.status_code == 200
    token = page.text.split('name="csrf-token" content="')[1].split('"')[0]
    saved = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={
            "_csrf": token,
            "month": "2026-08",
            "rate_czk": "50",
            "confirm_collected": "1",
            f"collected_{guest_id}": "200",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    row = stay_fee_filing.latest(apartment_id, "2026-08")
    assert row is not None
    first_pdf = stay_fee_filing.pdf_bytes(row)
    pdf_resp = client.get(f"/stay-fees/{apartment_id}/pdf?month=2026-08")
    assert pdf_resp.status_code == 200
    assert pdf_resp.content == first_pdf
    db.update("apartment", apartment_id, {"stay_fee_rate_czk": 99})
    pdf_again = client.get(f"/stay-fees/{apartment_id}/pdf?month=2026-08")
    assert pdf_again.content == first_pdf
