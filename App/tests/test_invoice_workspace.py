"""The builder reads as one invoice workspace: VAT answers the seller, the
payment row is one choice, and Issue is the only coral primary."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "invoice-workspace-host"


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
        auth.create_account(USERNAME, PASSWORD, "Workspace Host", must_change_password=False)
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
        "name": "Workspace s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "registry_entry": "Rejstřík", "vat_status": "non_payer",
        "invoice_due_days": 14,
        "owner_user_id": _owner(), "created_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("legal_entity", values)


def test_the_vat_column_answers_the_seller_status(host):
    import re
    payer_id = _add_entity(name="Payer s.r.o.", vat_status="payer",
                           registry_entry="Stavební", dic="CZ1")
    plain_id = _add_entity(name="Plain s.r.o.", vat_status="non_payer")
    payer_page = host.get(f"/invoices/new?entity={payer_id}").text
    plain_page = host.get(f"/invoices/new?entity={plain_id}").text

    # payer: visible columns, enabled selects
    assert re.search(r'<th data-vat-col(?! [^>]*hidden)', payer_page)
    assert not re.search(r'class="input-vat" disabled', payer_page)
    assert 'data-vat-payer="1"' in payer_page
    # non-payer: hidden columns, disabled selects (disabled never posts)
    assert re.search(r'<th data-vat-col [^>]*hidden', plain_page)
    assert 'class="input-vat" disabled' in plain_page
    assert 'data-vat-payer="0"' in plain_page


def test_the_payment_row_is_one_choice(host):
    entity_id = _add_entity()
    page = host.get(f"/invoices/new?entity={entity_id}").text
    assert 'name="already_paid" value="1"' in page
    assert 'name="already_paid" value="0"' in page
    # "already paid" starts on, so the paid row shows and the due row waits
    assert 'id="paid-fields"' in page and 'id="due-fields"' in page
    due_grid = page.split('id="due-fields"')[1]
    assert "hidden" in due_grid[:60]
    paid_grid = page.split('id="paid-fields"')[1]
    assert "hidden" not in paid_grid[:60]


def test_the_unpaid_choice_requests_payment(host):
    entity_id = _add_entity()
    response = host.post(
        "/invoices",
        data={"legal_entity_id": str(entity_id), "already_paid": "0",
              "buyer_name": "Buyer", "item_description": ["Stay"],
              "item_quantity": ["1"], "item_unit_price": ["1000"]},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    invoice_id = int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])
    row = db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,))
    assert row["paid_on"] is None and row["paid_via"] is None
    assert row["due_date"] is not None


def test_a_validation_error_keeps_payment_requested(host):
    """Payment requested posts already_paid=0. The 422 re-render used to treat
    any present field as already paid, so the radio flipped and a second Issue
    stored paid_on / dropped the due date."""
    import re

    entity_id = _add_entity()
    failed = host.post(
        "/invoices",
        data={"legal_entity_id": str(entity_id), "already_paid": "0",
              "buyer_name": "", "item_description": ["Stay"],
              "item_quantity": ["1"], "item_unit_price": ["1000"]},
        follow_redirects=False,
    )
    assert failed.status_code == 422
    page = failed.text
    paid = re.search(r'<input[^>]*id="already_paid"[^>]*>', page).group(0)
    requested = re.search(r'<input[^>]*id="payment_requested"[^>]*>', page).group(0)
    assert "checked" not in paid
    assert "checked" in requested
    due = page.split('id="due-fields"', 1)[1][:80]
    assert "hidden" not in due

    issued = host.post(
        "/invoices",
        data={"legal_entity_id": str(entity_id), "already_paid": "0",
              "buyer_name": "Buyer", "item_description": ["Stay"],
              "item_quantity": ["1"], "item_unit_price": ["1000"]},
        follow_redirects=False,
    )
    assert issued.status_code in (302, 303)
    invoice_id = int(issued.headers["location"].split("?")[0].rsplit("/", 1)[1])
    row = db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,))
    assert row["paid_on"] is None
    assert row["due_date"] is not None


def test_issue_is_the_only_coral_primary_in_the_builder(host):
    entity_id = _add_entity()
    page = host.get(f"/invoices/new?entity={entity_id}").text
    assert page.count("btn accent primary") == 1  # Issue invoice
    assert 'formaction="/invoices/preview"' in page  # preview stays quiet
    assert 'data-total' in page  # the live total mirrors the Decimal sum


def test_language_and_note_hide_behind_more_options(host):
    entity_id = _add_entity()
    page = host.get(f"/invoices/new?entity={entity_id}").text
    assert '<details class="invoice-more">' in page
    more = page.split('<details class="invoice-more">')[1].split("</details>")[0]
    assert 'id="lang"' in more
    assert 'id="note"' in more


def test_the_missing_bank_warning_waits_for_bank_transfer(host):
    entity_id = _add_entity()  # no account
    page = host.get(f"/invoices/new?entity={entity_id}").text
    assert 'data-bank-warning data-has-iban="0" hidden' in page
    with_account = _add_entity(
        name="Banked s.r.o.", bank_account="123/0600",
        iban="CZ9106000000000000000123",
    )
    page2 = host.get(f"/invoices/new?entity={with_account}").text
    assert 'data-has-iban="1"' in page2
    # and with an account the warning never needs to render server-side
    assert 'data-bank-warning data-has-iban="1" hidden' in page2
