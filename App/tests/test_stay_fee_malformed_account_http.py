"""#868: a malformed legal_entity.bank_account must not 500 HTTP pages.

Unit tests already cover payout_account and guest_pay_ways; this file pins the
routes that used to raise: the guest stay hub after registration is complete,
and an unrelated host property save that reconciles the no-pay-way alert.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import alerts, auth, claim, config, db, mail
from app.main import app
from tests.conftest import complete_guest_claim, login_as
from tests.test_endtoend import guest_form_data, passport_files

OWNER = "malformed-acct-http"
MALFORMED = "12-ab/0800"
IBAN = "CZ6508000000192000145399"
ALERT = "stay_fee_no_pay_way"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (OWNER,)):
        oid = row["id"]
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN (SELECT r.id FROM reservation r "
            "JOIN apartment a ON a.id = r.apartment_id WHERE a.owner_user_id = ?)",
            (oid,),
        )
        db.execute(
            "DELETE FROM reservation_claim WHERE reservation_id IN "
            "(SELECT r.id FROM reservation r JOIN apartment a ON a.id = r.apartment_id "
            "WHERE a.owner_user_id = ?)",
            (oid,),
        )
        db.execute(
            "DELETE FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (oid,),
        )
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _property_payload(entity_id: int, **overrides):
    data = {
        "internal_name": "Malformed HTTP flat",
        "addr_city": "Praha",
        "addr_obec": "Praha",
        "addr_street": "Synthetic",
        "addr_house_no": "12",
        "addr_zip": "120 00",
        "uby_idub": "123456789012",
        "uby_mark": "abc",
        "uby_name": "Penzion Malformed",
        "uby_contact": "host@malformed.test",
        "uby_ws_user": "UBY-WSmalformed",
        "permalink_window_days": "2",
        "permalink_reachback_days": "30",
        "legal_entity_id": str(entity_id),
    }
    data.update(overrides)
    return data


@pytest.fixture(autouse=True)
def _guest_pay_on(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)
    monkeypatch.setattr(config, "GUEST_PIN_REQUIRED", False)
    monkeypatch.setattr(mail, "mail_enabled", lambda: False)


@pytest.fixture
def seeded(monkeypatch):
    db.init_db()
    _cleanup()
    owner_id = auth.create_account(f"{OWNER}@example.test", "Malformed Host", username=OWNER)
    entity_id = db.insert("legal_entity", {
        "name": "Malformed s.r.o.", "owner_user_id": owner_id, "created_at": db.utcnow(),
        "iban": IBAN, "bank_account": "19-2000145399/0800",
    })
    client = TestClient(app)
    assert login_as(client, OWNER, url="/login?lang=en", follow_redirects=False).status_code == 303
    created = client.post("/apartments", data=_property_payload(entity_id), follow_redirects=False)
    assert created.status_code == 303, created.text
    apartment = db.query_one("SELECT * FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.update("legal_entity", entity_id, {"iban": None, "bank_account": MALFORMED})
    db.update("apartment", apartment["id"], {
        "stay_fee_collect": 1,
        "stay_fee_rate_czk": 50,
        "stay_fee_guest_rails": "iban,cash",
        "stay_fee_vs": "1234567890",
    })
    today = claim.prague_today()
    now = db.utcnow()
    stay_id = db.insert("reservation", {
        "apartment_id": apartment["id"], "source": "airbnb", "uid": "malformed-http-stay",
        "date_from": today.isoformat(), "date_to": (today + timedelta(days=3)).isoformat(),
        "status": "active", "declared_guests": 1, "created_at": now, "updated_at": now,
    })
    try:
        yield {
            "client": client,
            "apartment": apartment,
            "entity": entity_id,
            "token": apartment["permalink_token"],
            "stay": stay_id,
        }
    finally:
        _cleanup()


def test_the_completed_stay_hub_still_returns_200_with_a_malformed_operator_account(seeded):
    guest = TestClient(app)
    token, stay = seeded["token"], seeded["stay"]
    complete_guest_claim(guest, token, stay, party_size=1)
    saved = guest.post(
        f"/l/{token}/{stay}/save",
        data=guest_form_data(nationality="GBR"),
        files=passport_files("GBR"),
        follow_redirects=False,
    )
    assert saved.status_code == 303, saved.text
    hub = guest.get(f"/l/{token}/{stay}?lang=en")
    assert hub.status_code == 200, hub.text[:500]
    assert 'id="fee-pay"' in hub.text
    assert "CZ65" not in hub.text
    assert "g-fee-rail" in hub.text
    assert "g-fee-qr-img" not in hub.text


def test_a_property_save_still_succeeds_with_a_malformed_operator_account(seeded):
    aid = seeded["apartment"]["id"]
    db.update("apartment", aid, {"stay_fee_guest_rails": "iban"})
    alert_key = f"{ALERT}:{aid}"
    response = seeded["client"].post(
        f"/apartments/{aid}",
        data=_property_payload(seeded["entity"], internal_name="Malformed HTTP flat renamed"),
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    stored = db.query_one("SELECT internal_name FROM apartment WHERE id = ?", (aid,))
    assert stored["internal_name"] == "Malformed HTTP flat renamed"
    row = alerts.open_alert(alert_key)
    assert row is not None
    assert row["kind"] == ALERT
