"""0081: invoice list, picker, builder and detail navigation (layout only)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as
from tests.invoice_stay_helper import drop_stays, make_stay, stay_form
from tests.test_invoice_stay_browser import (  # noqa: F401 (fixtures and helpers)
    WIDTHS,
    _browser_session_cookie,
    _launch,
    base,
    sync_api,
)

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0081-evidence"
USERNAME = "invoice-nav-host"


def _cleanup():
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not owner:
        return
    uid = owner["id"]
    db.execute("INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
               "ON CONFLICT(key) DO UPDATE SET value = '1'")
    db.execute("DELETE FROM invoice_item WHERE invoice_id IN (SELECT id FROM invoice WHERE owner_user_id = ?)", (uid,))
    db.execute("DELETE FROM invoice WHERE owner_user_id = ?", (uid,))
    drop_stays(uid)
    db.execute("INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '') "
               "ON CONFLICT(key) DO UPDATE SET value = ''")
    db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id IN (SELECT id FROM legal_entity WHERE owner_user_id = ?)", (uid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (uid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (uid,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (uid,))
    db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (uid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (uid,))


@pytest.fixture
def world():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Invoice Nav Host", username=USERNAME)
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]
    entity = db.insert("legal_entity", {
        "name": "Nav s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "non_payer", "invoice_due_days": 14,
        "owner_user_id": owner, "created_at": db.utcnow(),
    })
    stay = make_stay(owner, entity_id=entity)
    client = TestClient(app)
    assert login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False).status_code == 303
    try:
        yield {"client": client, "owner": owner, "entity": entity, "stay": stay}
    finally:
        _cleanup()


def _issue(world, paid=True, stay=None):
    data = {"buyer_name": "Buyer", "lang": "cs", **stay_form(stay or world["stay"])}
    if paid:
        data["already_paid"] = "1"
    response = world["client"].post("/invoices", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text
    return int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])


def test_list_and_picker_link_to_settings(world):
    client = world["client"]
    _issue(world)
    listing = client.get("/invoices").text
    assert 'href="/invoices/settings"' in listing
    assert 'href="/invoices/new"' in listing
    picker = client.get("/invoices/new").text
    assert 'aria-describedby="reservation_id-help"' in picker
    assert 'id="reservation_id-help"' in picker
    assert 'href="/invoices/settings"' in picker


def test_builder_shows_stay_and_unfolds_options_without_changing_fields(world):
    client = world["client"]
    html = client.get(f"/invoices/new?reservation_id={world['stay']}&entity={world['entity']}").text
    assert f'href="/reservations/{world["stay"]}"' in html
    form = html[html.index('class="invoice-form"'):html.index("</form>", html.index('class="invoice-form"'))]
    assert "<details" not in form
    assert 'id="invoice-items-help"' in html
    for name in ("lang", "note", "buyer_name", "stay_price", "_csrf", "reservation_id", "legal_entity_id"):
        assert f'name="{name}"' in html, name
    # 0076: supplier details open the shared business editor's Invoice details.
    assert f"/entities?edit={world['entity']}&amp;next=" in html
    assert "#entity-invoice" in html


def test_detail_links_stay_settings_and_payment_fact(world):
    client = world["client"]
    invoice_id = _issue(world, paid=True)
    html = client.get(f"/invoices/{invoice_id}").text
    assert f'href="/reservations/{world["stay"]}"' in html
    assert f"/invoices/settings?entity={world['entity']}&amp;next=/invoices/{invoice_id}" in html
    assert "Paid on" in html
    unpaid = _issue(world, paid=False, stay=make_stay(world["owner"], entity_id=world["entity"]))
    html = client.get(f"/invoices/{unpaid}").text
    assert "Paid on" not in html
    assert f'action="/invoices/{unpaid}/paid"' in html


def test_navigation_pages_fit_and_capture(base):
    username = "invnav" + os.urandom(3).hex()
    owner = auth.create_account(f"{username}@example.test", "Nav", role="host", username=username)
    entity = db.insert("legal_entity", {
        "name": "Demo Hospitality s.r.o.", "seat": "Praha 1", "ico": "04656679",
        "registry_entry": "Fyzická osoba zapsaná v živnostenském rejstříku",
        "vat_status": "non_payer", "invoice_due_days": 14,
        "owner_user_id": owner, "created_at": db.utcnow(),
    })
    stay = make_stay(owner, entity_id=entity)
    session = _browser_session_cookie(username)
    client = TestClient(app)
    login_as(client, username, url="/login?lang=en", follow_redirects=False)
    response = client.post("/invoices", data={"buyer_name": "Demo Guest", "already_paid": "1", "lang": "cs", **stay_form(stay)},
                           follow_redirects=False)
    invoice_id = int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])
    capture = os.environ.get("UBYHOST_CAPTURE_0081") == "1"
    if capture:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
    pages = {
        "list": "/invoices",
        "picker": "/invoices/new",
        "builder": f"/invoices/new?reservation_id={make_stay(owner, entity_id=entity)}&entity={entity}",
        "detail": f"/invoices/{invoice_id}",
    }
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        for locale in ("en", "cs"):
            for width in WIDTHS:
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base + "/"}])
                page = context.new_page()
                for name, path in pages.items():
                    page.goto(f"{base}{path}{'&' if '?' in path else '?'}lang={locale}")
                    page.wait_for_load_state("networkidle")
                    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    assert overflow <= 1, (name, width, overflow)
                    if name in ("list", "detail"):
                        for link in page.locator(".page-actions a, .stay-command-actions a").all():
                            box = link.bounding_box()
                            assert box and box["x"] >= -1 and box["x"] + box["width"] <= width + 1, (name, width)
                    if capture:
                        page.screenshot(path=str(EVIDENCE / f"{name}-{locale}-{width}.png"), full_page=True)
                context.close()
        browser.close()
