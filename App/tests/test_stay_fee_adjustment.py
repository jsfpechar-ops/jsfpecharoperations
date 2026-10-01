"""Aggregate stay-fee corrections stay out of the guest register."""
from __future__ import annotations

import secrets

from fastapi.testclient import TestClient

from app import auth, claim, db
from app.main import app

PASSWORD = f"Adjust-{secrets.token_urlsafe(8)}-9"


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
        "stay_fee_cadence": "monthly",
        "active": 1,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    client.post("/login", data={"username": username, "password": PASSWORD}, follow_redirects=False)
    return client, apartment


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
