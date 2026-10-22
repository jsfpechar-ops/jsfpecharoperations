"""0240: the data-box send POST starts a draft only when the gateway is on, never on GET."""
from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, config, db, isds_gateway, stay_fee_filing
from app.main import app
from tests.conftest import login_as

SIGNATURE = "data:image/png;base64,AAAA"
IBAN = "CZ3008000000192000781379"
ACCOUNT = "19-2000781379/0800"
USERNAME = "databox-send-owner"
PORTAL = "https://www.mojedatovaschranka.cz/dz/odeslani"


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
        "databox-send-owner@example.test",
        "Databox Demo",
        role="host",
        username=USERNAME,
    )
    entity_id = db.insert("legal_entity", {
        "name": "Databox Demo s.r.o.",
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
        "internal_name": "Databox Flat",
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
        "uid": "databox-stay-1",
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


def _post_databox(client, apartment_id, filing_id):
    token = _csrf(client, f"/stay-fees/{apartment_id}?month=2026-08")
    return client.post(
        f"/stay-fees/{apartment_id}/filings/{filing_id}/databox",
        data={"_csrf": token},
        follow_redirects=False,
    )


def _gateway_on(monkeypatch):
    monkeypatch.setattr(config, "ISDS_GATEWAY_ID", "test-gateway")
    monkeypatch.setattr(config, "ISDS_GATEWAY_CERT", "/nonexistent/test.pfx")
    monkeypatch.setattr(config, "ISDS_GATEWAY_SERVICE_URL", "https://isds.example.test/gw")


def test_gateway_off_answers_not_available_and_stores_nothing(host, monkeypatch):
    client, owner_id, entity_id = host
    monkeypatch.setattr(config, "ISDS_GATEWAY_ID", "")
    monkeypatch.setattr(config, "ISDS_GATEWAY_CERT", "")
    monkeypatch.setattr(config, "ISDS_GATEWAY_SERVICE_URL", "")
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    apartment_id, filing_id = _sealed_filing(client)
    response = _post_databox(client, apartment_id, filing_id)
    assert response.status_code == 303
    assert f"/stay-fees/{apartment_id}?month=2026-08" in response.headers["location"]
    assert "#fee-send" in response.headers["location"]
    page = client.get(response.headers["location"])
    assert "Sending by data box is not available for this property yet" in page.text
    assert db.query_one("SELECT COUNT(*) AS n FROM stay_fee_databox_send")["n"] == 0


def test_get_never_starts_a_send(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    apartment_id, filing_id = _sealed_filing(client)
    response = client.get(f"/stay-fees/{apartment_id}/filings/{filing_id}/databox", follow_redirects=False)
    assert response.status_code == 405
    assert db.query_one("SELECT COUNT(*) AS n FROM stay_fee_databox_send")["n"] == 0


def test_unknown_filing_is_404(host):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    apartment_id, _ = _sealed_filing(client)
    response = _post_databox(client, apartment_id, 999999)
    assert response.status_code == 404


def test_gateway_failure_marks_the_row_failed(host, monkeypatch):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    apartment_id, filing_id = _sealed_filing(client)
    _gateway_on(monkeypatch)

    def refuse(**kwargs):
        raise isds_gateway.GatewayError("refused")

    monkeypatch.setattr(isds_gateway, "create_draft", refuse)
    response = _post_databox(client, apartment_id, filing_id)
    assert response.status_code == 303
    assert "#fee-send" in response.headers["location"]
    row = db.query_one("SELECT * FROM stay_fee_databox_send WHERE filing_id = ?", (filing_id,))
    assert row["state"] == "failed"


def test_success_redirects_to_isds_with_a_pending_row(host, monkeypatch):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    apartment_id, filing_id = _sealed_filing(client)
    _gateway_on(monkeypatch)
    monkeypatch.setattr(isds_gateway, "create_draft", lambda **kwargs: PORTAL)
    response = _post_databox(client, apartment_id, filing_id)
    assert response.status_code == 303
    assert response.headers["location"] == PORTAL
    row = db.query_one("SELECT * FROM stay_fee_databox_send WHERE filing_id = ?", (filing_id,))
    assert row["state"] == "pending"
    assert row["user_account_id"] == owner_id
    created = datetime.fromisoformat(row["created_at"])
    expires = datetime.fromisoformat(row["expires_at"])
    assert (expires - created).total_seconds() == config.ISDS_GATEWAY_VALIDITY_SECONDS


def test_foreign_address_from_isds_is_refused(host, monkeypatch):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    apartment_id, filing_id = _sealed_filing(client)
    _gateway_on(monkeypatch)
    monkeypatch.setattr(isds_gateway, "create_draft", lambda **kwargs: "https://evil.example/x")
    response = _post_databox(client, apartment_id, filing_id)
    assert "evil.example" not in response.headers["location"]
    assert "#fee-send" in response.headers["location"]
    row = db.query_one("SELECT * FROM stay_fee_databox_send WHERE filing_id = ?", (filing_id,))
    assert row["state"] == "failed"


def test_return_after_send_lands_on_the_stay_fee_page(host, monkeypatch):
    client, owner_id, entity_id = host
    apartment_id = _property(owner_id, entity_id)
    _stay(apartment_id)
    apartment_id, filing_id = _sealed_filing(client)
    _gateway_on(monkeypatch)
    monkeypatch.setattr(isds_gateway, "create_draft", lambda **kwargs: PORTAL)
    assert _post_databox(client, apartment_id, filing_id).status_code == 303
    response = client.get("/stay-fees/databox/done", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"/stay-fees/{apartment_id}?month=2026-08")
    row = db.query_one("SELECT * FROM stay_fee_databox_send WHERE filing_id = ?", (filing_id,))
    assert row["state"] == "returned_done"
    assert row["returned_at"]


@pytest.mark.parametrize("url,ok", [
    ("https://www.mojedatovaschranka.cz/dz", True),
    ("https://mojedatovaschranka.cz/", True),
    ("https://isds.gov.cz/x", True),
    ("http://www.mojedatovaschranka.cz/dz", False),
    ("https://mojedatovaschranka.cz.evil.com/", False),
    ("https://evil.example/mojedatovaschranka.cz", False),
    ("", False),
])
def test_portal_url_check(url, ok):
    assert isds_gateway.portal_url_ok(url) is ok
