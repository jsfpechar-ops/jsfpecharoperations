"""Invoice entity settings: IČO checksum and the delete guard (invoice step 2)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db, validation
from app.main import app
from tests.conftest import login_as

USERNAME = "invoice-entity-host"


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
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(f"{USERNAME}@example.test", "Invoice Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def test_ico_checksum_vectors():
    assert validation.ico_ok("04656679")
    assert not validation.ico_ok("12345678")
    assert not validation.ico_ok("123")
    assert not validation.ico_ok("abcdefgh")


def test_entity_with_a_valid_ico_is_saved(host):
    host.post(
        "/entities?lang=en",
        data={"name": "Valid s.r.o.", "seat": "Praha 1", "ico": "04656679",
              "contact_email": "v@invoice.test", "vat_status": "non_payer"},
    )
    row = db.query_one("SELECT * FROM legal_entity WHERE name = ?", ("Valid s.r.o.",))
    assert row is not None
    assert row["vat_status"] == "non_payer"
    assert row["invoice_due_days"] == 14


def test_entity_with_a_bad_ico_shows_the_error_and_saves_nothing(host):
    response = host.post(
        "/entities?lang=en",
        data={"name": "Bad Ico s.r.o.", "seat": "Praha 1", "ico": "12345678",
              "contact_email": "b@invoice.test"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "That company ID (IČO) is not valid." in response.text
    assert db.query_one("SELECT 1 AS x FROM legal_entity WHERE name = ?", ("Bad Ico s.r.o.",)) is None


def test_entity_with_an_invoice_cannot_be_deleted(host):
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    entity_id = db.insert(
        "legal_entity",
        {"name": "Invoiced s.r.o.", "ico": "04656679", "seat": "Praha",
         "owner_user_id": owner["id"], "created_at": db.utcnow()},
    )
    now = db.utcnow()
    db.execute(
        "INSERT INTO invoice (legal_entity_id, kind, seq_year, seq_no, number, vs, lang,"
        " vat_status, issue_date, seller_name, seller_seat, buyer_name, total_haler,"
        " created_at, issued_at, owner_user_id)"
        " VALUES (?, 'invoice', 2026, 1, '2026-0001', '20260001', 'cs', 'non_payer',"
        " '2026-09-26', 'Invoiced s.r.o.', 'Praha', 'Buyer', 100, ?, ?, ?)",
        (entity_id, now, now, owner["id"]),
    )
    host.post(f"/entities/{entity_id}/archive", follow_redirects=False)
    response = host.post(f"/entities/{entity_id}/delete", follow_redirects=True)
    assert "This operator has issued invoices, so it cannot be deleted." in response.text
    assert db.query_one("SELECT 1 AS x FROM legal_entity WHERE id = ?", (entity_id,))
