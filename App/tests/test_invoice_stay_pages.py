"""Stay invoice pages: picker, form, and stay-page button (task 0020)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as
from tests.invoice_stay_helper import drop_stays, make_stay, stay_form

USERNAME = "invoice-stay-host"


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
        auth.create_account(f"{USERNAME}@example.test", "Invoice Stay Host", username=USERNAME)
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


def test_new_without_a_stay_shows_the_picker(host):
    _add_entity()
    make_stay(_owner())
    page = host.get("/invoices/new")
    assert page.status_code == 200
    assert 'name="reservation_id"' in page.text
    assert "Chata" in page.text


def test_issue_without_a_stay_is_refused(host):
    _add_entity()
    response = host.post(
        "/invoices",
        data={"buyer_name": "Buyer", "already_paid": "1", "item_description": ["X"]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/invoices/new")
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM invoice WHERE owner_user_id = ?", (_owner(),)
    )["n"] == 0


def test_preview_without_a_stay_is_refused(host):
    _add_entity()
    response = host.post(
        "/invoices/preview",
        data={"buyer_name": "Buyer", "already_paid": "1", "item_description": ["X"]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert not response.headers.get("content-type", "").startswith("application/pdf")


def test_someone_elses_stay_is_refused(host):
    _add_entity()
    other_id = auth.create_account(
        "other-stay@example.test", "Other", username="other-stay-host"
    )
    other_stay = make_stay(other_id)
    try:
        response = host.get(
            f"/invoices/new?reservation_id={other_stay}", follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"].startswith("/invoices/new")
    finally:
        drop_stays(other_id)
        db.execute("DELETE FROM user_account WHERE id = ?", (other_id,))


def test_issue_for_a_stay_prints_the_stay(host):
    _add_entity()
    sid = make_stay(_owner())
    response = host.post(
        "/invoices",
        data={"buyer_name": "Buyer", "already_paid": "1", "lang": "cs", **stay_form(sid)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    clean = response.headers["location"].split("?")[0]
    assert clean.startswith("/invoices/")
    invoice_id = int(clean.rsplit("/", 1)[1])
    row = db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,))
    assert row["reservation_id"] == sid
    assert "Chata" in (row["stay_label"] or "")
    first = db.query_one(
        "SELECT * FROM invoice_item WHERE invoice_id = ? ORDER BY position LIMIT 1",
        (invoice_id,),
    )
    assert first["kind"] == "accommodation"
    pdf = host.get(f"/invoices/{invoice_id}.pdf")
    assert pdf.content.startswith(b"%PDF")


def test_second_invoice_for_the_stay_goes_to_the_first(host):
    _add_entity()
    sid = make_stay(_owner())
    first = host.post(
        "/invoices",
        data={"buyer_name": "Buyer", "already_paid": "1", "lang": "cs", **stay_form(sid)},
        follow_redirects=False,
    )
    first_id = int(first.headers["location"].split("?")[0].rsplit("/", 1)[1])
    again = host.get(f"/invoices/new?reservation_id={sid}", follow_redirects=False)
    assert again.status_code == 303
    assert again.headers["location"].startswith(f"/invoices/{first_id}")
    second = host.post(
        "/invoices",
        data={"buyer_name": "Buyer", "already_paid": "1", "lang": "cs", **stay_form(sid)},
        follow_redirects=False,
    )
    assert second.status_code == 303
    assert second.headers["location"].startswith(f"/invoices/{first_id}")
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM invoice WHERE owner_user_id = ?", (_owner(),)
    )["n"] == 1


def test_property_operator_is_forced(host):
    a = _add_entity()
    b = _add_entity(name="Other s.r.o.")
    sid = make_stay(_owner(), entity_id=b)
    page = host.get(f"/invoices/new?reservation_id={sid}", follow_redirects=True)
    assert page.status_code == 200
    select = page.text.split('name="legal_entity_id"', 1)[1].split("</select>", 1)[0]
    assert f'value="{b}"' in select
    assert f'value="{a}"' not in select


def test_stay_page_links_to_the_builder_then_to_the_invoice(host):
    _add_entity()
    sid = make_stay(_owner())
    before = host.get(f"/reservations/{sid}")
    assert f"/invoices/new?reservation_id={sid}" in before.text
    issued = host.post(
        "/invoices",
        data={"buyer_name": "Buyer", "already_paid": "1", "lang": "cs", **stay_form(sid)},
        follow_redirects=False,
    )
    invoice_id = int(issued.headers["location"].split("?")[0].rsplit("/", 1)[1])
    number = db.query_one("SELECT number FROM invoice WHERE id = ?", (invoice_id,))["number"]
    after = host.get(f"/reservations/{sid}")
    assert f"/invoices/{invoice_id}" in after.text
    assert number in after.text


def test_the_form_works_without_javascript_fields(host):
    entity_id = _add_entity()
    sid = make_stay(_owner())
    page = host.get(f"/invoices/new?reservation_id={sid}&entity={entity_id}")
    assert 'name="stay_price"' in page.text
    assert 'name="item_kind"' in page.text
    assert 'name="reservation_id"' in page.text
    assert 'name="item_description" maxlength="60" required' not in page.text
