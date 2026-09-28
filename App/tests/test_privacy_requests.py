"""BE-8/FE-5: the data-subject request register and the per-guest export."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db, dsr
from app.main import app

PASSWORD = "Secure-Password-123"
DOC = "P1234567"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username LIKE 'dsr-%'"):
        user_id = row["id"]
        db.execute("DELETE FROM data_subject_request WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        for apartment in db.query(
            "SELECT id FROM apartment WHERE owner_user_id = ?", (user_id,)
        ):
            apartment_id = apartment["id"]
            db.execute("DELETE FROM guest WHERE reservation_id IN "
                       "(SELECT id FROM reservation WHERE apartment_id = ?)", (apartment_id,))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
            db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))
    db.execute("DELETE FROM legal_entity WHERE name = 'Dsr entity' AND id NOT IN "
               "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)")


def _seed(username: str, token: str):
    owner = auth.create_account(
        username, PASSWORD, username.title(), must_change_password=False
    )
    now = db.utcnow()
    entity = db.insert(
        "legal_entity", {"name": "Dsr entity", "owner_user_id": owner, "created_at": now}
    )
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": owner,
            "internal_name": "Dsr flat",
            "permalink_token": token,
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
            "uid": f"dsr-{token}",
            "date_from": "2026-01-01",
            "date_to": "2026-01-03",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    guest = db.insert(
        "guest",
        {
            "reservation_id": reservation,
            "surname": "Smith",
            "first_name": "Jane",
            "nationality": "GBR",
            "doc_number": DOC,
            "purpose": "10",
            "entered_by": "guest",
            "created_at": now,
            "updated_at": now,
        },
    )
    return owner, guest


def _login(username: str) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def test_a_recorded_request_gets_a_one_month_deadline():
    owner, _guest = _seed("dsr-host", "dsrtok")
    client = _login("dsr-host")
    response = client.post(
        "/privacy-requests",
        data={
            "received_at": "2026-01-15T00:00:00+00:00",
            "channel": "email",
            "request_type": "access",
            "subject_kind": "guest",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    row = db.query_one("SELECT * FROM data_subject_request WHERE owner_user_id = ?", (owner,))
    assert row["due_at"].startswith("2026-02-15")
    assert dsr.one_month_later("2026-01-31T12:00:00+00:00").startswith("2026-02-28")


def test_a_request_due_within_the_window_raises_a_card():
    owner, _guest = _seed("dsr-due", "dsrdue")
    received = (date.today() - timedelta(days=27)).isoformat() + "T00:00:00+00:00"
    request_id = dsr.create(
        owner_user_id=owner,
        received_at=received,
        channel="email",
        request_type="erasure",
        subject_kind="guest",
    )
    assert dsr.raise_due_alerts(date.today()) >= 1
    alert = db.query_one("SELECT * FROM alert WHERE dedupe_key = ?", (f"dsr_due:{request_id}",))
    assert alert is not None
    assert alert["kind"] == "dsr_due"
    assert alert["owner_user_id"] == owner


def test_the_guest_export_is_decrypted_json_and_is_audited():
    owner, guest = _seed("dsr-export", "dsrexp")
    client = _login("dsr-export")
    response = client.get(f"/guests/{guest}/export.json")
    assert response.status_code == 200, response.text
    bundle = json.loads(response.text)
    assert bundle["guest"]["doc_number"] == DOC
    assert "signature_png_enc" not in bundle["guest"]
    assert "signature_present" in bundle["guest"]
    assert db.query_one(
        "SELECT id FROM audit WHERE action = 'export_guest_dsr' AND owner_user_id = ?",
        (owner,),
    )


def test_another_owner_cannot_export_a_guest():
    _owner, guest = _seed("dsr-owner", "dsrowner")
    _seed("dsr-other", "dsrother")
    client = _login("dsr-other")
    assert client.get(f"/guests/{guest}/export.json").status_code == 404
