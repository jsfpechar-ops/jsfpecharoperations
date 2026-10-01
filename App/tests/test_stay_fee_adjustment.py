"""Aggregate stay-fee corrections stay out of the guest register."""
from __future__ import annotations

import secrets
from datetime import date

from fastapi.testclient import TestClient

from app import auth, claim, db, stay_fee_filing
from app.main import app

PASSWORD = f"Adjust-{secrets.token_urlsafe(8)}-9"
SIGNATURE = "data:image/png;base64,AAAA"


def _host():
    db.init_db()
    username = f"fee-adjust-{secrets.token_hex(4)}"
    owner = auth.create_account(username, PASSWORD, "Adjust", role="host", must_change_password=False)
    entity = db.insert("legal_entity", {"name": "Adjust s.r.o.", "owner_user_id": owner, "created_at": db.utcnow()})
    apartment = db.insert("apartment", {
        "internal_name": "Adjust loft",
        "owner_user_id": owner,
        "legal_entity_id": entity,
        "stay_fee_rate_czk": 50,
        "stay_fee_vs": "123456",
        "stay_fee_authority_name": "Městský úřad",
        "stay_fee_council_account": "19-2000781379/0800",
        "stay_fee_council_iban": "CZ3008000000192000781379",
        "stay_fee_cadence": "monthly",
        "active": 1,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    client.post("/login", data={"username": username, "password": PASSWORD}, follow_redirects=False)
    return client, apartment


def _csrf(client, path: str) -> str:
    page = client.get(path)
    assert page.status_code == 200
    return page.text.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]


def _guest_stay(apartment_id: int) -> int:
    now = db.utcnow()
    rid = db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": f"adj-{secrets.token_hex(3)}",
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
    return db.query_one("SELECT id FROM guest WHERE reservation_id = ?", (rid,))["id"]


def _finalize_august(client, apartment_id: int, monkeypatch) -> None:
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 9, 30))
    guest_id = _guest_stay(apartment_id)
    token = _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08&lang=en")
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
    assert stay_fee_filing.latest(apartment_id, "2026-08") is not None


def test_people_times_nights_changes_the_total_without_a_guest(monkeypatch):
    monkeypatch.setattr(claim, "prague_today", lambda: __import__("datetime").date(2026, 9, 30))
    client, apartment = _host()
    page = client.get(f"/stay-fees/{apartment}?month=2026-08&lang=en")
    assert "Adjust calculation" in page.text
    token = page.text.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]
    guests_before = db.query_one("SELECT COUNT(*) AS n FROM guest")["n"]
    saved = client.post(f"/stay-fees/{apartment}/adjustment", data={
        "_csrf": token, "month": "2026-08", "direction": "add", "mode": "people",
        "people": "2", "nights": "3", "reason": "Walk-in guests",
    }, follow_redirects=False)
    assert saved.status_code == 303
    again = client.get(f"/stay-fees/{apartment}?month=2026-08&lang=en")
    assert "6" in again.text
    assert "300" in again.text or "300 Kč" in again.text
    assert db.query_one("SELECT COUNT(*) AS n FROM guest")["n"] == guests_before


def test_a_correction_cannot_make_the_total_negative(monkeypatch):
    monkeypatch.setattr(claim, "prague_today", lambda: __import__("datetime").date(2026, 9, 30))
    client, apartment = _host()
    page = client.get(f"/stay-fees/{apartment}")
    token = page.text.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]
    refused = client.post(f"/stay-fees/{apartment}/adjustment", data={
        "_csrf": token, "month": "2026-08", "direction": "remove", "mode": "bed_days",
        "bed_days": "2", "reason": "Too many",
    }, follow_redirects=True)
    assert refused.status_code == 200
    assert "záporný" in refused.text or "fee total negative" in refused.text
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM stay_fee_adjustment WHERE apartment_id = ?",
        (apartment,),
    )["n"] == 0


def test_filed_period_rejects_an_open_adjustment(monkeypatch):
    client, apartment = _host()
    _finalize_august(client, apartment, monkeypatch)
    token = _csrf(client, f"/stay-fees/{apartment}?month=2026-08&lang=en")
    refused = client.post(
        f"/stay-fees/{apartment}/adjustment",
        data={
            "_csrf": token,
            "month": "2026-08",
            "direction": "add",
            "mode": "bed_days",
            "bed_days": "1",
            "reason": "Late walk-in",
        },
        follow_redirects=True,
    )
    assert refused.status_code == 200
    assert "already filed" in refused.text
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM stay_fee_adjustment WHERE apartment_id = ?",
        (apartment,),
    )["n"] == 0


def test_an_adjustment_saved_in_a_filing_cannot_be_undone(monkeypatch):
    client, apartment = _host()
    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 9, 30))
    token = _csrf(client, f"/stay-fees/{apartment}?month=2026-08&lang=en")
    added = client.post(
        f"/stay-fees/{apartment}/adjustment",
        data={
            "_csrf": token,
            "month": "2026-08",
            "direction": "add",
            "mode": "bed_days",
            "bed_days": "2",
            "reason": "Council audit note",
        },
        follow_redirects=False,
    )
    assert added.status_code == 303
    adjustment_id = db.query_one(
        "SELECT id FROM stay_fee_adjustment WHERE apartment_id = ? ORDER BY id DESC",
        (apartment,),
    )["id"]
    _finalize_august(client, apartment, monkeypatch)
    row = db.query_one("SELECT filing_id, reversed_at FROM stay_fee_adjustment WHERE id = ?", (adjustment_id,))
    assert row["filing_id"] is not None
    assert row["reversed_at"] is None
    token = _csrf(client, f"/stay-fees/{apartment}?month=2026-08&lang=en")
    blocked = client.post(
        f"/stay-fees/{apartment}/adjustment/{adjustment_id}/undo",
        data={"_csrf": token, "month": "2026-08"},
        follow_redirects=True,
    )
    assert blocked.status_code == 200
    assert "saved filing and cannot be undone" in blocked.text
    still = db.query_one("SELECT reversed_at FROM stay_fee_adjustment WHERE id = ?", (adjustment_id,))
    assert still["reversed_at"] is None
