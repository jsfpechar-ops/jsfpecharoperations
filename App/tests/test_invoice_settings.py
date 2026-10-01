"""Seller details live next to (and inside) the invoice builder safely."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db, invoices
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "invoice-details-host"


def _owner() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _cleanup():
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not owner:
        return
    user_id = owner["id"]
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
        "ON CONFLICT(key) DO UPDATE SET value = '1'"
    )
    db.execute("DELETE FROM invoice_item WHERE invoice_id IN "
               "(SELECT id FROM invoice WHERE owner_user_id = ?)", (user_id,))
    db.execute("DELETE FROM invoice WHERE owner_user_id = ?", (user_id,))
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
        "ON CONFLICT(key) DO UPDATE SET value = ''"
    )
    db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id IN "
               "(SELECT id FROM legal_entity WHERE owner_user_id = ?)", (user_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(USERNAME, PASSWORD, "Details Host", must_change_password=False)
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


def _add_entity(**over):
    values = {
        "name": "Details s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "contact_email": "d@example.test",
        "bank_account": "123/0600", "iban": "CZ9106000000000000000123",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "non_payer", "invoice_due_days": 14,
        "owner_user_id": _owner(), "created_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("legal_entity", values)


def test_the_builder_shows_a_supplier_summary_with_the_details_link(host):
    entity_id = _add_entity()
    page = host.get(f"/invoices/new?entity={entity_id}")
    assert page.status_code == 200
    assert f"/invoices/settings?entity={entity_id}" in page.text
    assert "Details s.r.o." in page.text
    assert "IČO 04656679" in page.text
    assert "Edit invoice details" in page.text


def test_the_settings_route_is_not_eaten_by_the_dynamic_invoice_route(host):
    entity_id = _add_entity()
    page = host.get(f"/invoices/settings?entity={entity_id}")
    assert page.status_code == 200
    assert 'name="account_number"' in page.text


def test_settings_save_normalises_the_bank_and_keeps_absent_fields(host):
    entity_id = _add_entity(registry_entry=None)
    response = host.post(
        "/invoices/settings",
        data={"legal_entity_id": str(entity_id), "bank_account": "19-2000781379/0800",
              "next": f"/invoices/new?entity={entity_id}"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    row = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity_id,))
    # bank normalised through the payments helper
    assert row["bank_account"] == "19-2000781379/0800"
    assert row["iban"].startswith("CZ")
    # absent fields untouched
    assert row["registry_entry"] is None
    assert row["bic"] is None


def test_saving_other_fields_does_not_wipe_an_iban_only_account(host):
    entity_id = _add_entity(bank_account="CZ9106000000000000000123", iban="CZ9106000000000000000123")
    page = host.get(f"/invoices/settings?entity={entity_id}")
    token = page.text.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]
    host.post(
        "/invoices/settings",
        data={
            "_csrf": token,
            "legal_entity_id": str(entity_id),
            "account_prefix": "",
            "account_number": "",
            "account_bank": "",
            "bic": "GIBACZPX",
            "next": f"/invoices/new?entity={entity_id}",
        },
        follow_redirects=False,
    )
    row = db.query_one("SELECT bank_account, iban, bic FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["bank_account"] == "CZ9106000000000000000123"
    assert row["iban"] == "CZ9106000000000000000123"
    assert row["bic"] == "GIBACZPX"


def test_a_sent_blank_clears_the_field(host):
    entity_id = _add_entity()
    host.post(
        "/invoices/settings",
        data={"legal_entity_id": str(entity_id), "bank_account": "", "bic": "  ",
              "next": f"/invoices/new?entity={entity_id}"},
        follow_redirects=False,
    )
    row = db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["bank_account"] is None and row["iban"] is None
    assert row["bic"] is None


def test_a_bad_bank_number_keeps_the_old_value(host):
    entity_id = _add_entity()
    response = host.post(
        "/invoices/settings",
        data={"legal_entity_id": str(entity_id), "bank_account": "not-an-account",
              "next": f"/invoices/new?entity={entity_id}"},
        follow_redirects=True,
    )
    assert "That account number is not valid." in response.text
    row = db.query_one("SELECT bank_account FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["bank_account"] == "123/0600"


def test_a_failed_issue_rerenders_every_typed_value(host):
    entity_id = _add_entity()
    response = host.post(
        "/invoices",
        data={
            "legal_entity_id": str(entity_id),
            # customer name missing on purpose: this is the 422 path
            "buyer_email": "keep@me.test",
            "note": "typo note",
            "lang": "en",
            "item_description": ["Line one", "Line two"],
            "item_quantity": ["2", "1"],
            "item_unit": ["h", "pcs"],
            "item_unit_price": ["1000", ""],
            "item_vat_rate": ["21", "12"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 422, response.text[:400]
    page = response.text
    assert 'value="keep@me.test"' in page
    assert 'value="typo note"' in page
    assert 'value="Line one"' in page and 'value="Line two"' in page
    assert 'value="h"' in page and 'value="pcs"' in page
    # English was selected before the failed POST; it must stay selected.
    assert 'value="en" selected' in page
    # second line kept even with an empty price (the host may still be typing)
    assert page.count('name="item_description"') == 2


def test_seller_snapshot_presence_semantics():
    entity = {
        "name": "Op s.r.o.", "seat": "Praha", "ico": "04656679", "dic": "CZ1",
        "registry_entry": "Rejstřík", "bank_account": "123/0600",
        "iban": "CZ9106000000000000000123", "bic": "BIC",
        "contact_email": "e@x.test", "contact_phone": "+420",
    }

    # A field the form never sent falls back to the stored value.
    snapshot = invoices.seller_snapshot(entity, {})
    assert snapshot["name"] == "Op s.r.o."
    assert snapshot["registry"] == "Rejstřík"
    assert snapshot["email"] == "e@x.test"
    assert snapshot["bank_account"] == "123/0600"

    # A deliberately posted blank wins over the stored value…
    assert invoices.seller_snapshot(entity, {"seller_registry": ""})["registry"] == ""
    # …and a posted value is used verbatim.
    assert invoices.seller_snapshot(entity, {"seller_name": "Override"})["name"] == "Override"
    # Bank numbers the form posts are normalised through the payments helper.
    fixed = invoices.seller_snapshot(entity, {"seller_bank_account": "19-2000781379/0800"})
    assert fixed["bank_account"] == "19-2000781379/0800"
    assert fixed["iban"].startswith("CZ")
    # A garbage bank number falls back to the stored value rather than 500-ing.
    bad = invoices.seller_snapshot(entity, {"seller_bank_account": "not-a-bank"})
    assert bad["bank_account"] == "123/0600"
