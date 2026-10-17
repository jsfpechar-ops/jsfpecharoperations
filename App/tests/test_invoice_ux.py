"""Invoice host UI: the standalone free-form builder (routes)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as
from tests.invoice_stay_helper import drop_stays, make_stay, stay_form

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
    drop_stays(user_id)
    db.execute(
        "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
        "ON CONFLICT(key) DO UPDATE SET value = ''"
    )
    db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id IN (SELECT id FROM legal_entity WHERE owner_user_id = ?)", (user_id,))
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
        auth.create_account(f"{USERNAME}@example.test", "Invoice UI Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _owner() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _add_entity(**over):
    values = {
        "name": "UI s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "non_payer", "invoice_due_days": 14,
        "owner_user_id": _owner(), "created_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("legal_entity", values)


def _items(**over):
    data = {
        **stay_form(make_stay(_owner())),
        "item_description": ["Consulting"],
        "item_quantity": ["2"],
        "item_unit": ["h"],
        "item_unit_price": ["1000"],
        "item_vat_rate": ["21"],
    }
    data.update(over)
    return data


def test_invoice_list_month_filter_matches_issue_date(host, monkeypatch):
    from datetime import date

    from app import claim

    monkeypatch.setattr(claim, "prague_today", lambda: date(2026, 9, 30))
    entity_id = _add_entity()
    owner = _owner()
    now = db.utcnow()
    for issue_date, number in (("2026-08-05", "2026-0008"), ("2026-09-10", "2026-0009")):
        db.execute(
            "INSERT INTO invoice (legal_entity_id, kind, seq_year, seq_no, number, vs, lang,"
            " vat_status, issue_date, seller_name, seller_seat, buyer_name, total_haler,"
            " created_at, issued_at, owner_user_id)"
            " VALUES (?, 'invoice', 2026, ?, ?, ?, 'cs', 'non_payer',"
            " ?, 'UI s.r.o.', 'Praha 1', 'Buyer', 1000, ?, ?, ?)",
            (
                entity_id,
                int(number.split("-")[1]),
                number,
                number.replace("-", ""),
                issue_date,
                now,
                now,
                owner,
            ),
        )

    all_page = host.get("/invoices")
    assert all_page.status_code == 200
    assert "2026-0008" in all_page.text
    assert "2026-0009" in all_page.text
    assert 'type="month"' in all_page.text
    assert "list-filter" in all_page.text
    assert "month-control is-empty" in all_page.text
    assert "All dates" in all_page.text
    assert "list-filter-reset" not in all_page.text

    august = host.get("/invoices?month=2026-08")
    assert august.status_code == 200
    assert "2026-0008" in august.text
    assert "2026-0009" not in august.text
    assert 'value="2026-08"' in august.text
    assert "month-control is-empty" not in august.text
    assert 'class="btn ghost list-filter-reset" href="/invoices"' in august.text

    unpaid = host.get("/invoices?status=unpaid&q=0009")
    assert "2026-0009" in unpaid.text
    assert "2026-0008" not in unpaid.text
    assert host.get("/invoices?status=paid").text.count("/invoices/") < all_page.text.count("/invoices/")


def test_the_builder_form_is_a_free_form_with_items(host):
    entity_id = _add_entity()
    stay_id = make_stay(_owner())
    page = host.get(f"/invoices/new?reservation_id={stay_id}&entity={entity_id}")
    assert page.status_code == 200
    assert 'name="legal_entity_id"' in page.text
    assert 'name="item_description"' in page.text
    assert "data-add-item" in page.text
    assert 'formtarget="_blank"' in page.text
    assert "data-confirm" in page.text


def test_issue_a_custom_invoice_and_download_the_pdf(host):
    _add_entity()
    response = host.post(
        "/invoices",
        data={"buyer_name": "Buyer", "already_paid": "1", "lang": "cs", **_items()},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303), response.text
    clean = response.headers["location"].split("?")[0]
    assert clean.startswith("/invoices/")
    detail = host.get(clean)
    assert detail.status_code == 200
    assert "Consulting" in detail.text
    pdf = host.get(f"{clean}.pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_no_operator_shows_an_error(host):
    stay_id = make_stay(_owner())
    page = host.get(f"/invoices/new?reservation_id={stay_id}")
    assert page.status_code == 200
    assert "Assign an operator to this property first." in page.text


def test_mark_paid(host):
    _add_entity()
    response = host.post(
        "/invoices",
        data={"buyer_name": "Buyer", "already_paid": "1", "lang": "cs", **_items()},
        follow_redirects=False,
    )
    invoice_id = int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])
    host.post(f"/invoices/{invoice_id}/paid", follow_redirects=False)
    assert db.query_one("SELECT marked_paid_at FROM invoice WHERE id = ?", (invoice_id,))["marked_paid_at"]


def test_send_enqueues_a_mail_with_a_working_download_token(host, monkeypatch):
    from app import invoice_links, mail

    monkeypatch.setattr(mail, "mail_enabled", lambda: True)
    _add_entity()
    response = host.post(
        "/invoices",
        data={"buyer_name": "Buyer", "buyer_email": "buyer@example.test",
              "already_paid": "1", "lang": "cs", **_items()},
        follow_redirects=False,
    )
    invoice_id = int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])
    host.post(f"/invoices/{invoice_id}/send", follow_redirects=False)

    outbox = db.query_one("SELECT * FROM email_outbox WHERE kind = 'invoice_issued' ORDER BY id DESC")
    assert outbox is not None
    payload = json.loads(outbox["payload"])
    assert mail.CLAIM_SECRET_MARKER in payload["text"]
    assert mail.CLAIM_SECRET_KEY in payload

    invoice = db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,))
    assert invoice["emailed_at"]
    token = invoice_links.download_token(invoice_id, invoice["pdf_sha256"])
    pdf = host.get(f"/invoice/d/{token}")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert host.get("/invoice/d/garbage").status_code == 404


def test_a_payers_issued_invoice_shows_the_vat_breakdown(host):
    payer_id = _add_entity(name="VAT Break s.r.o.", vat_status="payer", dic="CZ1",
                           registry_entry="Stavební")
    stay_id = make_stay(_owner(), entity_id=payer_id)
    response = host.post(
        "/invoices",
        data={"legal_entity_id": str(payer_id), "buyer_name": "Buyer",
              "already_paid": "0", **stay_form(stay_id), "stay_vat_rate": "12",
              "item_description": ["Stay"],
              "item_quantity": ["2"], "item_unit_price": ["1000"],
              "item_vat_rate": ["12"]},
        follow_redirects=False,
    )
    invoice_id = int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])
    detail = host.get(f"/invoices/{invoice_id}?lang=en").text
    # stay 10000@12% + item 2×1000@12%: base 12000, VAT 1440, gross 13440
    assert "Unit price (excl. VAT)" in detail
    assert "13\u00a0440,00 Kč" in detail
    assert "Base (excl. VAT)" in detail
    assert "12\u00a0000,00 Kč" in detail  # base total
    assert "1\u00a0440,00 Kč" in detail   # VAT total


def test_a_non_payers_issued_invoice_keeps_the_plain_table(host):
    entity_id = _add_entity()
    stay_id = make_stay(_owner(), entity_id=entity_id)
    response = host.post(
        "/invoices",
        data={"legal_entity_id": str(entity_id), "buyer_name": "Buyer",
              "already_paid": "1", **stay_form(stay_id), "item_description": ["Stay"],
              "item_quantity": ["1"], "item_unit_price": ["1000"]},
        follow_redirects=False,
    )
    invoice_id = int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])
    detail = host.get(f"/invoices/{invoice_id}?lang=en").text
    assert "Unit price (excl. VAT)" not in detail
    assert "Base (excl. VAT)" not in detail


def test_switching_operator_keeps_the_form_instead_of_a_reload(host):
    """The switch patch swaps the operator chrome, so no confirm is needed
    and nothing typed can be lost."""
    entity_id = _add_entity()
    stay_id = make_stay(_owner())
    page = host.get(f"/invoices/new?reservation_id={stay_id}&entity={entity_id}&lang=en").text
    assert 'data-next-number' in page
    assert "switch_operator_confirm" not in page
    assert "window.confirm" not in page
    # the fetch patch reads the same URL the select posts to
    assert 'fetch("/invoices/new?reservation_id=' in page
