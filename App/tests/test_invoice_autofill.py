"""Invoice autofill: guest buyer, BIC from bank code, last price hint (task 0061)."""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from app import auth, db, payments
from app.main import app
from tests.conftest import login_as
from datetime import timedelta

from app import claim
from tests.invoice_stay_helper import drop_stays, make_stay, stay_form

USERNAME = "invoice-autofill-host"
OTHER = "invoice-autofill-other"

SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


def _owner(name: str = USERNAME) -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (name,))["id"]


def _cleanup():
    for username in (USERNAME, OTHER):
        owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
        if not owner:
            continue
        user_id = owner["id"]
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = '1'"
        )
        db.execute(
            "DELETE FROM invoice_item WHERE invoice_id IN "
            "(SELECT id FROM invoice WHERE owner_user_id = ?)",
            (user_id,),
        )
        db.execute("DELETE FROM invoice WHERE owner_user_id = ?", (user_id,))
        drop_stays(user_id)
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
            "ON CONFLICT(key) DO UPDATE SET value = ''"
        )
        db.execute(
            "DELETE FROM invoice_sequence WHERE legal_entity_id IN "
            "(SELECT id FROM legal_entity WHERE owner_user_id = ?)",
            (user_id,),
        )
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(f"{USERNAME}@example.test", "Autofill Host", username=USERNAME)
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (OTHER,)):
        auth.create_account(f"{OTHER}@example.test", "Other Host", username=OTHER)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def _add_entity(**over):
    values = {
        "name": "Autofill s.r.o.",
        "seat": "Praha 1",
        "ico": "04656679",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "non_payer",
        "invoice_due_days": 14,
        "owner_user_id": _owner(),
        "created_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("legal_entity", values)


def _complete_guest(stay_id: int, **over) -> int:
    values = {
        "reservation_id": stay_id,
        "surname": "Novák",
        "first_name": "Jan",
        "birth_date": "01011990",
        "nationality": "CZE",
        "doc_number": "123456789",
        "res_street": "Hlavní 1",
        "res_city": "Brno",
        "res_country": "CZE",
        "purpose": "10",
        "signature_png": SIGNATURE,
        "entered_by": "host",
        "created_at": db.utcnow(),
        "updated_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("guest", values)


def _issue_invoice(host, entity_id: int, stay_id: int, price: str = "8500", buyer_name: str = "Buyer"):
    response = host.post(
        "/invoices",
        data={
            "legal_entity_id": str(entity_id),
            **stay_form(stay_id, price=price),
            "buyer_name": buyer_name,
            "lang": "cs",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303), response.text


def test_bic_for_account_maps_czech_bank_codes():
    assert payments.bic_for_account("19-2000781379/0800") == "GIBACZPX"
    assert payments.bic_for_account("CZ6508000000192000781379") == "GIBACZPX"
    assert payments.bic_for_account("123/9999") == ""
    assert payments.bic_for_account("") == ""


def test_fill_guest_button_fills_blanks_only(host):
    entity_id = _add_entity()
    stay_id = make_stay(_owner(), entity_id=entity_id)
    _complete_guest(stay_id)
    page = host.get(f"/invoices/new?reservation_id={stay_id}&entity={entity_id}")
    assert 'name="fill_from_guest"' in page.text
    response = host.post(
        "/invoices",
        data={
            "legal_entity_id": str(entity_id),
            **stay_form(stay_id),
            "fill_from_guest": "1",
            "buyer_name": "Keep Me",
            "buyer_city": "",
            "lang": "cs",
        },
    )
    assert response.status_code == 200
    assert 'value="Keep Me"' in response.text
    assert 'value="Hlavní 1"' in response.text
    assert 'value="Brno"' in response.text


def test_no_complete_guest_means_no_fill_button(host):
    entity_id = _add_entity()
    stay_id = make_stay(_owner(), entity_id=entity_id)
    page = host.get(f"/invoices/new?reservation_id={stay_id}&entity={entity_id}")
    assert 'name="fill_from_guest"' not in page.text


def test_another_hosts_guest_is_never_used(host):
    entity_id = _add_entity()
    other_stay = make_stay(_owner(OTHER))
    _complete_guest(other_stay, res_street="Secret 9")
    page = host.get(f"/invoices/new?reservation_id={other_stay}&entity={entity_id}")
    assert page.status_code != 200 or "Secret 9" not in page.text


def test_settings_save_derives_bic_but_keeps_a_typed_one(host):
    entity_id = _add_entity(bic=None)
    host.post(
        "/invoices/settings",
        data={
            "legal_entity_id": str(entity_id),
            "bank_account": "19-2000781379/0800",
            "next": f"/invoices/new?entity={entity_id}",
        },
        follow_redirects=False,
    )
    row = db.query_one("SELECT bic FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["bic"] == "GIBACZPX"

    host.post(
        "/invoices/settings",
        data={
            "legal_entity_id": str(entity_id),
            "bank_account": "19-2000781379/0800",
            "bic": "CUSTOMBIC",
            "next": f"/invoices/new?entity={entity_id}",
        },
        follow_redirects=False,
    )
    row = db.query_one("SELECT bic FROM legal_entity WHERE id = ?", (entity_id,))
    assert row["bic"] == "CUSTOMBIC"


def _second_stay_same_property(owner_id: int, first_stay_id: int) -> int:
    row = db.query_one("SELECT * FROM reservation WHERE id = ?", (first_stay_id,))
    today = claim.prague_today()
    return db.insert(
        "reservation",
        {
            "apartment_id": row["apartment_id"],
            "source": "manual",
            "uid": row["uid"] + "-b",
            "date_from": (today - timedelta(days=10)).isoformat(),
            "date_to": (today - timedelta(days=7)).isoformat(),
            "status": "active",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )


def test_last_price_is_placeholder_not_value(host):
    entity_id = _add_entity()
    stay_a = make_stay(_owner(), entity_id=entity_id)
    _issue_invoice(host, entity_id, stay_a, price="7200")
    stay_b = _second_stay_same_property(_owner(), stay_a)
    page = host.get(f"/invoices/new?reservation_id={stay_b}&entity={entity_id}")
    assert 'placeholder="7200"' in page.text
    assert 'name="stay_price"' in page.text
    assert 'value="7200"' not in page.text.split('name="stay_price"', 1)[1].split(">", 1)[0]


def test_fill_then_preview_works_without_javascript(host):
    entity_id = _add_entity(bank_account="19-2000781379/0800", iban="CZ6508000000192000781379")
    stay_id = make_stay(_owner(), entity_id=entity_id)
    _complete_guest(stay_id)
    filled = host.post(
        "/invoices",
        data={
            "legal_entity_id": str(entity_id),
            **stay_form(stay_id, price="5000"),
            "fill_from_guest": "1",
            "lang": "cs",
        },
    )
    assert 'value="Jan Novák"' in filled.text
    preview = host.post(
        "/invoices/preview",
        data={
            "legal_entity_id": str(entity_id),
            **stay_form(stay_id, price="5000"),
            "buyer_name": "Jan Novák",
            "buyer_street": "Hlavní 1",
            "buyer_city": "Brno",
            "buyer_country": "CZE",
            "lang": "cs",
        },
    )
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "application/pdf"


def test_invoice_fill_screenshots_at_required_widths():
    """Acceptance screenshots: form before and after guest fill (brief §7)."""
    import os
    import secrets
    import socket
    import threading
    import time

    import pytest
    import uvicorn

    sync_api = pytest.importorskip("playwright.sync_api")
    from tests.test_invoice_stay_browser import _browser_session_cookie, _launch

    shots = os.environ.get("UBYHOST_SHOTS_DIR")
    if not shots:
        pytest.skip("set UBYHOST_SHOTS_DIR to capture acceptance screenshots")

    db.init_db()
    username = f"invfill{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Fill Shots", username=username)
    entity = db.insert(
        "legal_entity",
        {
            "name": "Fill s.r.o.",
            "seat": "Praha 1",
            "ico": "04656679",
            "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
            "vat_status": "non_payer",
            "invoice_due_days": 14,
            "owner_user_id": owner,
            "created_at": db.utcnow(),
        },
    )
    stay_id = make_stay(owner, entity_id=entity)
    _complete_guest(stay_id)

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    base = f"http://127.0.0.1:{port}"
    session = _browser_session_cookie(username)
    path = f"/invoices/new?reservation_id={stay_id}&entity={entity}&lang=en"
    widths = (360, 390, 1280)

    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for width in widths:
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
            page = context.new_page()
            page.goto(base + path)
            page.wait_for_load_state("networkidle")
            page.screenshot(path=os.path.join(shots, f"invoice-fill-before-{width}.png"), full_page=True)
            page.click('button[name="fill_from_guest"]')
            page.wait_for_load_state("networkidle")
            page.screenshot(path=os.path.join(shots, f"invoice-fill-after-{width}.png"), full_page=True)
            context.close()
        browser.close()
    server.should_exit = True
    thread.join(timeout=5)
