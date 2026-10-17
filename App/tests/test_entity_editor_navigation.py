"""Task 0076: one business editor with Business details and Invoice details.

Every business and invoice-settings link lands on ``/entities?edit={id}``
(0101: the old ``/invoices/settings`` URL is gone). Which business a property uses stays a
property setting, and issued invoices never change. ARES is never called.
"""
from __future__ import annotations

import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import ares, auth, db, invoices
from app.main import app
from tests.conftest import login_as

USERNAME = "entity-nav-0076-host"
OTHER = "entity-nav-0076-other"
ICO = "04656679"
EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0076-evidence"


def _owner(username: str = USERNAME) -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))["id"]


def _cleanup():
    for username in (USERNAME, OTHER):
        row = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
        if not row:
            continue
        user_id = row["id"]
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('invoice_purge_unlock', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = '1'"
        )
        db.execute("DELETE FROM invoice_item WHERE invoice_id IN (SELECT id FROM invoice WHERE "
                   "legal_entity_id IN (SELECT id FROM legal_entity WHERE owner_user_id = ?))",
                   (user_id,))
        db.execute("DELETE FROM invoice WHERE legal_entity_id IN "
                   "(SELECT id FROM legal_entity WHERE owner_user_id = ?)", (user_id,))
        db.execute("DELETE FROM invoice_sequence WHERE legal_entity_id IN "
                   "(SELECT id FROM legal_entity WHERE owner_user_id = ?)", (user_id,))
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
    ares._CACHE.clear()
    auth.create_account(f"{USERNAME}@example.test", "Nav Host", username=USERNAME)
    auth.create_account(f"{OTHER}@example.test", "Other Host", username=OTHER)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        ares._CACHE.clear()
        _cleanup()


def _entity(owner=None, **over) -> int:
    values = {
        "name": "Ukázka Pole s.r.o.", "seat": "Praha 1", "ico": ICO, "dic": "CZ04656679",
        "contact_email": "pole@example.test", "contact_phone": "+420777000111",
        "bank_account": "123/0600", "iban": "CZ9106000000000000000123", "bic": "AGBACZPP",
        "registry_entry": "Živnostenský rejstřík", "vat_status": "identified",
        "invoice_prefix": "UB", "invoice_due_days": 21, "signature_name": "Jana Pole",
        "owner_user_id": owner or _owner(), "created_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("legal_entity", values)


def _property(name, entity_id, owner=None) -> int:
    return db.insert("apartment", {
        "internal_name": name, "owner_user_id": owner or _owner(), "legal_entity_id": entity_id,
        "automation_mode": "manual", "submit_after_hours": 24, "default_purpose": "10",
        "permalink_token": auth.new_permalink_token(), "permalink_pin": auth.new_permalink_pin(),
        "active": 1, "created_at": db.utcnow(),
    })


def _row(entity_id):
    return dict(db.query_one("SELECT * FROM legal_entity WHERE id = ?", (entity_id,)))


def _location(response):
    assert response.status_code == 303, response.text[:300]
    return response.headers["location"]


def _section(page, anchor):
    start = page.index(f'id="{anchor}"')
    return page[start:page.index("</section>", start)]


# --- 0101: the old entry URL is gone ------------------------------------------

def test_the_old_invoice_settings_url_is_gone(host):
    entity_id = _entity()
    before = _row(entity_id)
    for path in ("/invoices/settings", f"/invoices/settings?entity={entity_id}"):
        assert host.get(path, follow_redirects=False).status_code == 404, path
    posted = host.post("/invoices/settings", data={
        "legal_entity_id": str(entity_id), "invoice_prefix": "OLD"}, follow_redirects=False)
    assert posted.status_code in (404, 405)
    assert _row(entity_id) == before


def test_invoice_details_post_saves_with_its_return_path(host):
    entity_id = _entity(bic=None)
    response = host.post(f"/entities/{entity_id}/invoice", data={
        "legal_entity_id": str(entity_id), "bank_account": "19-2000781379/0800",
        "next": "/invoices/12"}, follow_redirects=False)
    assert _location(response).startswith("/invoices/12?msg=")
    row = _row(entity_id)
    assert row["bank_account"] == "19-2000781379/0800" and row["bic"] == "GIBACZPX"


def test_invoice_details_post_refuses_a_foreign_entity_without_saving(host):
    own = _entity()
    foreign = _entity(owner=_owner(OTHER), name="Cizí s.r.o.")
    before_own, before_foreign = _row(own), _row(foreign)
    response = host.post(f"/entities/{foreign}/invoice", data={
        "legal_entity_id": str(foreign), "invoice_prefix": "HACK"}, follow_redirects=False)
    assert _location(response).startswith("/entities?err=")
    assert _row(own) == before_own and _row(foreign) == before_foreign


# --- the canonical editor -------------------------------------------------------

def test_editor_has_both_sections_and_the_linked_properties(host):
    entity_id = _entity()
    first = _property("Byt Alfa", entity_id)
    second = _property("Byt Beta", entity_id)
    page = host.get(f"/entities?edit={entity_id}&lang=en").text
    business = _section(page, "entity-business")
    invoice = _section(page, "entity-invoice")
    assert "Business details" in business and "Invoice details" in invoice
    assert f'action="/entities/{entity_id}" enctype="multipart/form-data"' in business
    assert f'action="/entities/{entity_id}/invoice"' in invoice
    assert 'name="vat_status"' in invoice and 'name="vat_status"' not in business
    assert 'name="contact_email"' in business and 'name="contact_email"' not in invoice
    linked = page[page.index('id="entity-linked"'):page.index('id="entity-business"')]
    for apartment_id, name in ((first, "Byt Alfa"), (second, "Byt Beta")):
        assert f'href="/apartments/{apartment_id}?view=settings&amp;section=property#operator-picker"' in linked
        assert name in linked
    assert 'id="entity-linked-help"' in linked
    # Choosing another business is a property operation: no picker here.
    assert 'name="legal_entity_id" required' not in page
    # The list keeps Edit, Invoice settings (now the editor section) and More.
    assert f'href="/entities?edit={entity_id}#entity-invoice"' in page
    assert "invoices/settings" not in page


def test_editor_keeps_a_safe_return_path_only(host):
    entity_id = _entity()
    page = host.get(f"/entities?edit={entity_id}&next=/apartments/5").text
    assert page.count('name="next" value="/apartments/5"') == 2
    assert 'href="/apartments/5"' in page
    evil = host.get(f"/entities?edit={entity_id}&next=https://evil.test/").text
    assert 'name="next"' not in _section(evil, "entity-business")
    assert "evil.test" not in evil


def test_canonical_post_saves_and_returns(host):
    entity_id = _entity(bic=None)
    response = host.post(f"/entities/{entity_id}/invoice", data={
        "account_prefix": "19", "account_number": "2000781379", "account_bank": "0800",
        "invoice_prefix": "NV", "_invoice_account_existing": "123/0600"}, follow_redirects=False)
    location = _location(response)
    assert location.startswith(f"/entities?edit={entity_id}&msg=") and location.endswith("#entity-invoice")
    row = _row(entity_id)
    assert row["bank_account"] == "19-2000781379/0800" and row["bic"] == "GIBACZPX"
    assert row["invoice_prefix"] == "NV" and row["name"] == "Ukázka Pole s.r.o."
    back = host.post(f"/entities/{entity_id}/invoice", data={
        "invoice_due_days": "10", "next": "/invoices/new?entity=%d" % entity_id},
        follow_redirects=False)
    assert _location(back).startswith(f"/invoices/new?entity={entity_id}&msg=")
    outside = host.post(f"/entities/{entity_id}/invoice", data={
        "invoice_due_days": "11", "next": "https://evil.test/"}, follow_redirects=False)
    assert "evil" not in _location(outside)


def test_canonical_post_rerenders_422_with_typed_values_on_the_editor(host):
    entity_id = _entity()
    response = host.post(f"/entities/{entity_id}/invoice?lang=en", data={
        "account_number": "1234567890", "account_bank": "0100", "account_prefix": "",
        "invoice_prefix": "TY", "registry_entry": "Typed", "next": "/apartments/9"})
    assert response.status_code == 422
    page = response.text
    invoice = _section(page, "entity-invoice")
    assert "That account number is not valid." in invoice
    for typed in ('value="1234567890"', 'value="0100"', 'value="TY"', 'value="Typed"'):
        assert typed in invoice, typed
    # The business form still shows the stored values and keeps the return path.
    assert 'value="pole@example.test"' in _section(page, "entity-business")
    assert page.count('name="next" value="/apartments/9"') == 2
    assert _row(entity_id)["bank_account"] == "123/0600"


def test_canonical_lookup_is_click_only_and_saves_nothing(host):
    entity_id = _entity(registry_entry=None, vat_status="non_payer")
    with patch("app.ares.requests.get") as mock_get:
        host.get(f"/entities?edit={entity_id}")
        assert not mock_get.called
        mock_get.return_value.status_code = 200
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {
            "obchodniJmeno": "ARES", "dic": "CZ04656679",
            "seznamRegistraci": {"stavZdrojeDph": "AKTIVNI"},
            "dalsiUdaje": [{"datovyZdroj": "vr", "spisovaZnacka": "B 8525/MSPH"}],
        }
        response = host.post(f"/entities/{entity_id}/invoice?lang=en", data={
            "fill_from_register": "1", "ico": ICO, "invoice_prefix": "KEEP",
            "vat_status": "non_payer", "registry_entry": ""})
    assert response.status_code == 200
    invoice = _section(response.text, "entity-invoice")
    assert 'value="KEEP"' in invoice and "Městského soudu v Praze" in invoice
    assert re.search(r'<option value="payer"\s+selected', invoice)
    row = _row(entity_id)
    assert row["registry_entry"] is None and row["vat_status"] == "non_payer"


def test_forged_and_archived_entities_are_refused(host):
    foreign = _entity(owner=_owner(OTHER), name="Cizí s.r.o.")
    before = _row(foreign)
    for path in (f"/entities/{foreign}/invoice", f"/entities/{foreign}"):
        response = host.post(path, data={"name": "Hack", "invoice_prefix": "HACK"},
                             follow_redirects=False)
        assert _location(response).startswith("/entities?err=")
    assert _row(foreign) == before
    assert "Cizí" not in host.get(f"/entities?edit={foreign}").text
    archived = _entity(name="Old s.r.o.", archived_at=db.utcnow())
    page = host.get(f"/entities?edit={archived}").text
    assert 'id="entity-business"' in page and 'id="entity-invoice"' not in page
    refused = host.post(f"/entities/{archived}/invoice", data={"invoice_prefix": "ZZ"},
                        follow_redirects=False)
    assert _location(refused).startswith("/entities?err=")
    assert _row(archived)["invoice_prefix"] == "UB"


def test_business_save_returns_to_the_opening_context(host):
    entity_id = _entity()
    body = {"name": "Ukázka Pole s.r.o.", "seat": "Brno", "ico": ICO,
            "contact_email": "pole@example.test"}
    back = host.post(f"/entities/{entity_id}", data={**body, "next": "/apartments/3"},
                     follow_redirects=False)
    assert _location(back).startswith("/apartments/3?msg=")
    plain = host.post(f"/entities/{entity_id}", data=body, follow_redirects=False)
    assert _location(plain).startswith("/entities?msg=")
    evil = host.post(f"/entities/{entity_id}", data={**body, "next": "//evil.test"},
                     follow_redirects=False)
    assert _location(evil).startswith("/entities?msg=")


# --- every entry point lands on the right record --------------------------------

def test_property_overview_properties_settings_and_builder_links(host):
    entity_id = _entity()
    first = _property("Byt Alfa", entity_id)
    _property("Byt Beta", entity_id)
    overview = host.get(f"/apartments/{first}").text
    assert f'href="/entities?edit={entity_id}&amp;next=/apartments/{first}"' in overview
    listing = host.get("/apartments").text
    assert f'href="/entities?edit={entity_id}&amp;next=/apartments"' in listing
    settings = host.get("/settings").text
    assert f'href="/entities?edit={entity_id}&amp;next=/settings"' in settings
    # The invoice builder link is pinned in test_invoice_settings/test_host_invoice_navigation.
    # Several businesses: Account settings opens the list, never an arbitrary one.
    _entity(name="Druhá s.r.o.")
    assert 'href="/entities">' in host.get("/settings").text


def test_property_without_a_business_links_to_its_own_settings(host):
    entity_id = _entity()
    apartment_id = _property("Bez firmy", entity_id)
    db.update("apartment", apartment_id, {"legal_entity_id": None})
    overview = host.get(f"/apartments/{apartment_id}").text
    assert (f'href="/apartments/{apartment_id}?view=settings&amp;section=property#operator-picker"'
            in overview)


def test_shared_business_change_reaches_both_properties_but_not_issued_invoices(host):
    entity_id = _entity()
    first = _property("Byt Alfa", entity_id)
    second = _property("Byt Beta", entity_id)
    draft = {
        "legal_entity_id": entity_id, "apartment_id": first, "reservation_id": None,
        "kind": "invoice", "lang": "cs", "vat_status": "non_payer",
        "issue_date": "2026-09-26", "duzp": None, "due_date": None,
        "paid_on": None, "paid_via": None,
        "seller": {"name": "Ukázka Pole s.r.o.", "seat": "Praha 1", "ico": ICO, "dic": "",
                   "registry": "ŽR", "bank_account": "123/0600", "iban": "", "bic": "",
                   "email": "pole@example.test", "phone": ""},
        "buyer": {"name": "Buyer", "street": "", "city": "", "zip": "", "country": "CZE",
                  "ico": "", "dic": "", "email": ""},
        "stay_from": "2026-09-10", "stay_to": "2026-09-14", "stay_label": "Flat",
        "items": [{"kind": "accommodation", "description": "Ubytování", "quantity": 1,
                   "unit": "pobyt", "vat_rate": None, "base_haler": None,
                   "vat_haler": None, "gross_haler": 10000}],
        "total_base_haler": None, "total_vat_haler": None, "total_haler": 10000,
    }
    invoice_id = invoices.issue(draft, actor_user_id=_owner())
    before = dict(db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,)))
    sequence = [dict(r) for r in db.query(
        "SELECT * FROM invoice_sequence WHERE legal_entity_id = ?", (entity_id,))]
    host.post(f"/entities/{entity_id}", data={
        "name": "Nové Jméno s.r.o.", "seat": "Ostrava", "ico": ICO,
        "contact_email": "nove@example.test"}, follow_redirects=False)
    host.post(f"/entities/{entity_id}/invoice", data={
        "bank_account": "19-2000781379/0800", "invoice_prefix": "ZZ",
        "invoice_next_number": "500"}, follow_redirects=False)
    for apartment_id in (first, second):
        assert "Nové Jméno s.r.o." in host.get(f"/apartments/{apartment_id}").text
    assert _row(entity_id)["contact_email"] == "nove@example.test"
    assert dict(db.query_one("SELECT * FROM invoice WHERE id = ?", (invoice_id,))) == before
    assert [dict(r) for r in db.query(
        "SELECT * FROM invoice_sequence WHERE legal_entity_id = ?", (entity_id,))] == sequence


# --- browser: the editor fits 360-2048, EN and CS --------------------------------

BROWSER_USER = "entitynav0076"


@pytest.fixture(scope="module")
def browser_host():
    db.init_db()
    username = f"{BROWSER_USER}-{secrets.token_hex(3)}"
    owner_id = auth.create_account(f"{username}@example.test", "Pole Host", username=username)
    entity_id = db.insert("legal_entity", {
        "name": "Ukázka Pole s.r.o.", "seat": "Václavské náměstí 1, 110 00 Praha 1",
        "ico": ICO, "dic": "CZ04656679", "contact_email": "pole@example.test",
        "contact_phone": "+420 777 000 111", "bank_account": "19-2000781379/0800",
        "iban": "CZ6508000000192000781379", "bic": "GIBACZPX",
        "registry_entry": "Zapsáno v živnostenském rejstříku", "vat_status": "non_payer",
        "invoice_prefix": "UB", "invoice_due_days": 14, "signature_name": "Jana Pole",
        "owner_user_id": owner_id, "created_at": db.utcnow(),
    })
    for name in ("Byt Alfa", "Chata Beta u lesa"):
        _property(name, entity_id, owner=owner_id)
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner_id, "entity": entity_id}
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


@pytest.fixture(scope="module")
def live_base(browser_host):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the test server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


_FIT_JS = """() => {
  const vw = document.documentElement.clientWidth;
  const bad = [];
  for (const el of document.querySelectorAll('#entity-edit input:not([type=hidden]):not(.sr-only), #entity-edit select, #entity-edit button, #entity-edit a, #entity-edit h3')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (r.right > vw + 1 || r.left < -1) bad.push(el.name || el.id || el.textContent.trim().slice(0, 30));
    if (el.tagName === 'INPUT' && el.type !== 'checkbox' && r.width < 40) bad.push('narrow:' + (el.name || el.id));
  }
  const sections = [...document.querySelectorAll('#entity-edit .entity-section')].map(s => s.id);
  const heads = [...document.querySelectorAll('#entity-edit .entity-section-title')]
    .map(h => getComputedStyle(h).display !== 'none' && h.getBoundingClientRect().height > 0);
  return {scroll: document.documentElement.scrollWidth, vw, bad, sections, heads};
}"""


def _sidebar(page, collapsed):
    page.evaluate(
        """(want) => {
          const now = document.body.classList.contains('sidebar-collapsed');
          if (want === now) return;
          const btn = document.querySelector('button[data-sidebar-collapse]');
          if (btn && btn.offsetParent !== null) { btn.click(); return; }
          document.body.classList.toggle('sidebar-collapsed', want);
        }""",
        collapsed,
    )


def test_editor_fits_every_width_and_both_languages(browser_host, live_base):
    sync_api = pytest.importorskip("playwright.sync_api")
    from tests.browser_support import chromium_launch_kwargs

    entity_id = browser_host["entity"]
    capture = os.environ.get("UBYHOST_CAPTURE_0076") == "1"
    cookie = browser_host["client"].cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            for width in (360, 390, 768, 1280, 1440, 2048):
                context = browser.new_context(viewport={"width": width, "height": 900})
                context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie,
                                      "url": live_base + "/"}])
                page = context.new_page()
                for lang in ("en", "cs"):
                    page.goto(f"{live_base}/entities?edit={entity_id}&next=/apartments&lang={lang}")
                    for collapsed in ((False, True) if width >= 1024 else (False,)):
                        _sidebar(page, collapsed)
                        fit = page.evaluate(_FIT_JS)
                        assert fit["scroll"] <= fit["vw"], (width, lang, collapsed, fit)
                        assert not fit["bad"], (width, lang, collapsed, fit)
                        assert fit["sections"] == ["entity-business", "entity-invoice"], fit
                        assert all(fit["heads"]), fit
                    _sidebar(page, False)
                    if capture and width in (360, 390, 1280):
                        EVIDENCE.mkdir(parents=True, exist_ok=True)
                        page.locator("#entity-edit").screenshot(
                            path=str(EVIDENCE / f"entity-editor-{width}-{lang}.png"))
                # The Invoice settings link lands on Invoice details, scrolled into view.
                page.goto(f"{live_base}/entities?edit={entity_id}&lang=en#entity-invoice")
                box = page.locator("#entity-invoice").bounding_box()
                assert box and box["y"] < 900, box
                if capture and width == 1280:
                    page.screenshot(path=str(EVIDENCE / "invoice-details-1280-en.png"))
                context.close()
        finally:
            browser.close()


def test_unsaved_business_draft_asks_before_saving_invoice_details(browser_host, live_base):
    sync_api = pytest.importorskip("playwright.sync_api")
    from tests.browser_support import chromium_launch_kwargs

    entity_id = browser_host["entity"]
    cookie = browser_host["client"].cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie,
                                  "url": live_base + "/"}])
            page = context.new_page()
            page.goto(f"{live_base}/entities?edit={entity_id}&lang=en")
            page.fill("#edit_contact_phone", "+420 111 222 333")
            dialogs = []

            def _dismiss(dialog):
                dialogs.append(dialog.type)
                dialog.dismiss()

            page.on("dialog", _dismiss)
            page.click("#entity-invoice button[type=submit]:not([name])")
            page.wait_for_timeout(500)
            assert dialogs == ["beforeunload"], dialogs
            # Dismissed: still here, the draft intact, nothing saved.
            assert page.input_value("#edit_contact_phone") == "+420 111 222 333"
            stored = db.query_one("SELECT contact_phone FROM legal_entity WHERE id = ?", (entity_id,))
            assert stored["contact_phone"] == "+420 777 000 111"
            context.close()
        finally:
            browser.close()
