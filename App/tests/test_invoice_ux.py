"""Invoice host UI and routes (invoice step 6)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "invoice-ui-host"


def _cleanup():
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not owner:
        return
    user_id = owner["id"]
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
        "ON CONFLICT(key) DO UPDATE SET value = '1'"
    )
    db.execute("DELETE FROM invoice_item WHERE invoice_id IN (SELECT id FROM invoice WHERE owner_user_id = ?)", (user_id,))
    db.execute("DELETE FROM invoice WHERE owner_user_id = ?", (user_id,))
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
        "ON CONFLICT(key) DO UPDATE SET value = ''"
    )
    db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id IN (SELECT id FROM legal_entity WHERE owner_user_id = ?)", (user_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(USERNAME, PASSWORD, "Invoice UI Host", must_change_password=False)
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _stay():
    now = db.utcnow()
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]
    entity_id = db.insert(
        "legal_entity",
        {"name": "UI s.r.o.", "seat": "Praha 1", "ico": "04656679",
         "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
         "vat_status": "non_payer", "invoice_due_days": 14,
         "owner_user_id": owner, "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {"internal_name": "UI Flat", "owner_user_id": owner, "legal_entity_id": entity_id,
         "permalink_token": "invoiceuitoken", "created_at": now},
    )
    reservation_id = db.insert(
        "reservation",
        {"apartment_id": apartment_id, "uid": "ui-1", "source": "booking",
         "date_from": "2026-09-10", "date_to": "2026-09-14", "status": "active",
         "created_at": now, "updated_at": now},
    )
    return apartment_id, reservation_id


def test_issue_form_is_two_clicks_with_defaults(host):
    _apt, res = _stay()
    page = host.get(f"/reservations/{res}/invoice/new")
    assert page.status_code == 200
    assert 'id="already_paid"' in page.text
    assert "autofocus" in page.text
    assert 'formtarget="_blank"' in page.text
    assert "data-confirm" in page.text
    # Works without JS: every input is in the HTML.
    assert 'name="buyer_name"' in page.text
    assert 'name="price_czk"' in page.text


def test_issue_writes_a_pdf_and_redirects(host):
    _apt, res = _stay()
    response = host.post(
        f"/reservations/{res}/invoice",
        data={"buyer_name": "Buyer", "price_czk": "4000", "already_paid": "1", "lang": "cs"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303), response.text
    location = response.headers["location"]
    assert location.startswith("/invoices/")
    clean = location.split("?")[0]
    detail = host.get(clean)
    assert detail.status_code == 200
    pdf = host.get(f"{clean}.pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_mark_paid_and_the_stay_panel_lists_the_document(host):
    _apt, res = _stay()
    response = host.post(
        f"/reservations/{res}/invoice",
        data={"buyer_name": "Buyer", "price_czk": "4000", "already_paid": "1", "lang": "cs"},
        follow_redirects=False,
    )
    invoice_id = int(response.headers["location"].rstrip("/").split("/")[-1].split("?")[0])
    host.post(f"/invoices/{invoice_id}/paid", follow_redirects=False)
    assert db.query_one("SELECT marked_paid_at FROM invoice WHERE id = ?", (invoice_id,))["marked_paid_at"]
    stayed = host.get(f"/reservations/{res}")
    assert 'id="invoice"' in stayed.text
    assert f"/invoices/{invoice_id}" in stayed.text


def test_send_enqueues_a_mail_with_a_working_download_token(host, monkeypatch):
    from app import invoice_links, mail

    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    _apt, res = _stay()
    response = host.post(
        f"/reservations/{res}/invoice",
        data={"buyer_name": "Buyer", "buyer_email": "buyer@example.test",
              "price_czk": "4000", "already_paid": "1", "lang": "cs"},
        follow_redirects=False,
    )
    clean = response.headers["location"].split("?")[0]
    invoice_id = int(clean.rsplit("/", 1)[1])
    host.post(f"/invoices/{invoice_id}/send", follow_redirects=False)

    outbox = db.query_one(
        "SELECT * FROM email_outbox WHERE kind = 'invoice_issued' ORDER BY id DESC"
    )
    assert outbox is not None
    payload = json.loads(outbox["payload"])
    assert mail.CLAIM_SECRET_MARKER in payload["text"]
    assert mail.CLAIM_SECRET_KEY in payload

    invoice = db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,))
    assert invoice["emailed_at"]
    token = invoice_links.download_token(invoice_id, invoice["pdf_sha256"])
    pdf = host.get(f"/invoice/d/{token}")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert host.get("/invoice/d/garbage").status_code == 404
