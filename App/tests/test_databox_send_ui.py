"""0241: the "Send by data box" button and the email step appear only when the gateway is on."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, isds_gateway, stay_fee_filing
from app.main import app
from app.mail_notify import build_stay_fee_report
from tests.conftest import login_as

SIGNATURE = "data:image/png;base64,AAAA"
IBAN = "CZ3008000000192000781379"
ACCOUNT = "19-2000781379/0800"
USERNAME = "databox-send-ui-owner"
REPORT_URL = "https://example.test/stay-fees/1?month=2026-08"


def _cleanup():
    for user in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        owner_id = user["id"]
        db.execute(
            "DELETE FROM stay_fee_databox_send WHERE user_account_id = ?", (owner_id,)
        )
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
        "databox-send-ui-owner@example.test",
        "Databox UI Demo",
        role="host",
        username=USERNAME,
    )
    entity_id = db.insert("legal_entity", {
        "name": "Databox UI Demo s.r.o.",
        "ico": "12345678",
        "owner_user_id": owner_id,
        "created_at": db.utcnow(),
    })
    client = TestClient(app)
    assert login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False).status_code == 303
    try:
        yield client, owner_id, entity_id
    finally:
        _cleanup()


def _property(owner_id, entity_id, **extra):
    values = {
        "internal_name": "Databox UI Flat",
        "owner_user_id": owner_id,
        "legal_entity_id": entity_id,
        "stay_fee_rate_czk": 50,
        "stay_fee_vs": "123456",
        "stay_fee_authority_name": "Městský úřad",
        "stay_fee_authority_databox": "abc1234",
        "stay_fee_council_account": ACCOUNT,
        "stay_fee_council_iban": IBAN,
        "created_at": db.utcnow(),
    }
    values.update(extra)
    return db.insert("apartment", values)


def _stay(apartment_id):
    now = db.utcnow()
    rid = db.insert("reservation", {
        "apartment_id": apartment_id,
        "uid": "databox-ui-stay-1",
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


def _csrf(client, url):
    page = client.get(url)
    return page.text.split('name="csrf-token" content="')[1].split('"')[0]


def _finalize(client, apartment_id, month="2026-08"):
    guest_id = db.query_one("SELECT id FROM guest ORDER BY id DESC")["id"]
    token = _csrf(client, f"/stay-fees/{apartment_id}?month={month}")
    return client.post(
        f"/stay-fees/{apartment_id}/finalize",
        data={
            "_csrf": token,
            "month": month,
            "confirm_collected": "1",
            f"collected_{guest_id}": "200",
        },
        follow_redirects=False,
    )


def _sealed_filing(client):
    apartment_id = db.query_one("SELECT id FROM apartment ORDER BY id DESC")["id"]
    assert _finalize(client, apartment_id).status_code == 303
    filing = stay_fee_filing.latest(apartment_id, "2026-08")
    return apartment_id, filing["id"]


def _databox_forms(text, filing_id):
    return text.count(f"/filings/{filing_id}/databox\"")


@pytest.fixture
def gateway_off(monkeypatch):
    monkeypatch.setattr(isds_gateway, "configured", lambda: False)


@pytest.fixture
def gateway_on(monkeypatch):
    monkeypatch.setattr(isds_gateway, "configured", lambda: True)


def test_gateway_off_no_databox_form_and_no_email_step(host, gateway_off):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    apartment_id, filing_id = _sealed_filing(client)

    listing = client.get("/stay-fees?month=2026-08")
    report = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert listing.status_code == 200
    assert report.status_code == 200
    assert _databox_forms(listing.text, filing_id) == 0
    assert _databox_forms(report.text, filing_id) == 0
    assert "fee-databox-send" not in listing.text and "fee-databox-send" not in report.text
    assert "Send by data box" not in listing.text
    assert "Send by data box" not in report.text

    mail = build_stay_fee_report(
        lang="en", property_name="Databox UI Flat", period="08/2026", amount="200 CZK",
        total_czk=200, authority="Městský úřad", databox="abc1234", account=ACCOUNT,
        vs="123456", has_qr=True, report_url=REPORT_URL,
    )
    assert "Send by data box" not in str(mail)
    assert "#fee-send" not in str(mail)


def test_gateway_on_form_on_list_and_report(host, gateway_on):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    apartment_id, filing_id = _sealed_filing(client)

    listing = client.get("/stay-fees?month=2026-08")
    report = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert listing.status_code == 200
    assert report.status_code == 200
    assert _databox_forms(listing.text, filing_id) == 1
    assert _databox_forms(report.text, filing_id) == 1
    assert 'class="ui-btn ui-btn-primary fee-databox-send"' in listing.text
    assert 'class="ui-btn ui-btn-primary fee-databox-send"' in report.text
    assert report.text.count("ui-btn-primary") == 2 and "ui-btn-primary filter-apply" in report.text
    assert "ui-btn ui-btn-secondary" in report.text
    assert "Or send it by hand" in report.text

    mail = build_stay_fee_report(
        lang="en", property_name="Databox UI Flat", period="08/2026", amount="200 CZK",
        total_czk=200, authority="Městský úřad", databox="abc1234", account=ACCOUNT,
        vs="123456", has_qr=True, report_url=REPORT_URL, databox_send=True,
    )
    assert "Send by data box" in str(mail)
    assert "#fee-send" in str(mail)


def test_gateway_on_without_council_databox_no_form(host, gateway_on):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id, stay_fee_authority_databox="")
    _stay(apartment_id)
    apartment_id, filing_id = _sealed_filing(client)

    listing = client.get("/stay-fees?month=2026-08")
    report = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert _databox_forms(listing.text, filing_id) == 0
    assert _databox_forms(report.text, filing_id) == 0


def test_not_frozen_no_databox_form(host, gateway_on):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    listing = client.get("/stay-fees?month=2026-08")
    report = client.get(f"/stay-fees/{apartment_id}?month=2026-08")
    assert listing.status_code == 200
    assert report.status_code == 200
    assert '/databox"' not in listing.text
    assert '/databox"' not in report.text
    assert 'id="fee-send"' not in report.text
