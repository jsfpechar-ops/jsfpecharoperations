"""Sealed stay-fee periods: finalize then frozen PDF/CSV bytes."""
from __future__ import annotations

import secrets
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, stay_fee_filing
from app.main import app
from tests.conftest import login_as

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
    owner_id = auth.create_account("stay-fee-finalize-owner@example.test", "Finalize Demo", role="host", username="stay-fee-finalize-owner")
    entity_id = db.insert("legal_entity", {
        "name": "Finalize Demo s.r.o.",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    assert login_as(client, "stay-fee-finalize-owner", url="/login?lang=en", follow_redirects=False).status_code == 303
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


def _csrf(client, path: str) -> str:
    page = client.get(path)
    assert page.status_code == 200
    return page.text.split('name="csrf-token" content="')[1].split('"')[0]


def test_changing_cadence_cannot_file_over_a_saved_period(host, monkeypatch):
    client, owner_id, entity_id = host
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 10, 15))
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    token = _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08")
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
    first_pdf = stay_fee_filing.pdf_bytes(stay_fee_filing.latest(apartment_id, "2026-08"))
    db.update("apartment", apartment_id, {"stay_fee_cadence": "quarterly"})

    pdf_again = client.get(f"/stay-fees/{apartment_id}/pdf?month=2026-08")
    assert pdf_again.status_code == 200
    assert pdf_again.content == first_pdf
    august = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert "Saved (version 1)" in august.text

    overlap = client.get(f"/stay-fees/{apartment_id}?month=2026-07")
    assert "already covers part of this one" in overlap.text
    blocked = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={"_csrf": _csrf(client, f"/stay-fees/{apartment_id}?month=2026-07"), "month": "2026-07", "rate_czk": "50"},
        follow_redirects=False,
    )
    assert blocked.status_code == 303
    assert stay_fee_filing.latest(apartment_id, "2026-Q3") is None

    quarter = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={"_csrf": _csrf(client, f"/stay-fees/{apartment_id}?month=2026-04"), "month": "2026-04", "rate_czk": "50"},
        follow_redirects=False,
    )
    assert quarter.status_code == 303
    assert stay_fee_filing.latest(apartment_id, "2026-Q2") is not None

    correct = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={
            "_csrf": _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08&correct=1"),
            "month": "2026-08",
            "correct": "1",
            "rate_czk": "50",
            "confirm_collected": "1",
            f"collected_{guest_id}": "200",
        },
        follow_redirects=False,
    )
    assert correct.status_code == 303
    current = stay_fee_filing.latest(apartment_id, "2026-08")
    assert current["version"] == 2
    assert current["cadence"] == "monthly"
    previous = db.query_one(
        "SELECT * FROM stay_fee_filing WHERE apartment_id = ? AND period_key = ? AND version = 1",
        (apartment_id, "2026-08"),
    )
    assert previous["superseded_at"]
    assert stay_fee_filing.latest(apartment_id, "2026-Q3") is None


def test_a_failed_correction_keeps_the_sealed_file(host, monkeypatch):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    token = _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08")
    assert client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={
            "_csrf": token,
            "month": "2026-08",
            "rate_czk": "50",
            "confirm_collected": "1",
            f"collected_{guest_id}": "200",
        },
        follow_redirects=False,
    ).status_code == 303
    sealed = stay_fee_filing.latest(apartment_id, "2026-08")
    first_pdf = stay_fee_filing.pdf_bytes(sealed)

    def _boom(_report):
        raise ValueError("pdf failed")

    monkeypatch.setattr("app.stay_fee_filing.stay_fee_remittance_pdf.render", _boom)
    failed = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={
            "_csrf": _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08&correct=1"),
            "month": "2026-08",
            "correct": "1",
            "rate_czk": "50",
            "confirm_collected": "1",
            f"collected_{guest_id}": "200",
        },
        follow_redirects=False,
    )
    assert failed.status_code == 303
    current = stay_fee_filing.latest(apartment_id, "2026-08")
    assert current["id"] == sealed["id"]
    assert current["superseded_at"] is None
    assert stay_fee_filing.pdf_bytes(current) == first_pdf


def test_disabling_the_fee_leaves_the_sealed_period_downloadable(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    token = _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08")
    assert client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={
            "_csrf": token,
            "month": "2026-08",
            "rate_czk": "50",
            "confirm_collected": "1",
            f"collected_{guest_id}": "200",
        },
        follow_redirects=False,
    ).status_code == 303
    db.update("apartment", apartment_id, {"stay_fee_rate_czk": 0})

    august = client.get("/stay-fees?month=2026-08")
    july = client.get("/stay-fees?month=2026-07")
    pdf = client.get(f"/stay-fees/{apartment_id}/pdf?month=2026-08")
    assert "Finalize Flat" in august.text
    assert "Set up stay fee" in july.text
    assert f"/stay-fees/{apartment_id}/pdf?month=2026-07" not in july.text
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_a_correction_keeps_the_rate_the_period_was_sealed_with(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    saved = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={
            "_csrf": _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08"),
            "month": "2026-08",
            "confirm_collected": "1",
            f"collected_{guest_id}": "200",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    first = stay_fee_filing.latest(apartment_id, "2026-08")
    db.update("apartment", apartment_id, {"stay_fee_rate_czk": 90})
    corrected = client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={
            "_csrf": _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08&correct=1"),
            "month": "2026-08",
            "correct": "1",
            "confirm_collected": "1",
            f"collected_{guest_id}": "200",
        },
        follow_redirects=False,
    )
    assert corrected.status_code == 303
    second = stay_fee_filing.latest(apartment_id, "2026-08")
    assert second["id"] != first["id"]
    assert second["rate_czk"] == first["rate_czk"] == 50
    assert second["total_due_czk"] == first["total_due_czk"]
