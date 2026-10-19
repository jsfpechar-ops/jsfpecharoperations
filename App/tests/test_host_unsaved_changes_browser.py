"""0084 O1: in-app Save / Discard / Stay for host forms with unsaved changes.

Property Settings and the business editor carry ``data-unsaved-guard``. An
in-app link that would leave a dirty form opens a native <dialog>: Stay (and
Esc) keeps the edits and focus, Discard restores the loaded values and follows
the link, Save submits the form through the normal server path. A clean form,
or a link that keeps the draft on screen, never asks. Without JavaScript the
dialog never opens and the forms post as before. Synthetic data only.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, config, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0084-evidence"
LOCK = {"lock_id": "70840001", "alias": "Synthetic O1 Door", "battery": 90, "tz_offset_ms": 3600000}
NAME = "Synthetic O1 Flat"
PHONE = "+420 777 000 111"
TEXT = {
    "en": {"title": "You have unsaved changes", "save": "Save", "discard": "Discard", "stay": "Stay",
           "reset": "Discard changes"},
    "cs": {"title": "Máte neuložené změny", "save": "Uložit", "discard": "Zahodit", "stay": "Zůstat",
           "reset": "Zahodit změny"},
}
SIZES = [(360, 780), (1280, 900)]


@pytest.fixture(scope="module")
def host():
    db.init_db()
    patch = pytest.MonkeyPatch()
    patch.setattr(config, "DOOR_CODES_ENABLED", True)
    patch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    patch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    username = f"o1-{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "O1 Host", role="host", username=username)
    now = db.utcnow()
    entity = db.insert("legal_entity", {
        "name": "Synthetic O1 s.r.o.", "seat": "Synthetická 1, 110 00 Praha 1", "ico": "04656679",
        "contact_email": "o1@example.test", "contact_phone": PHONE, "owner_user_id": owner,
        "created_at": now,
    })
    apartment = db.insert("apartment", {
        "internal_name": NAME, "city_en": "Brno", "owner_user_id": owner, "legal_entity_id": entity,
        "data_controller_entity_id": entity,
        "addr_obec": "Brno", "addr_house_no": "12", "addr_zip": "60200", "addr_street": "Synthetic",
        "automation_mode": "manual", "submit_after_hours": 6, "default_purpose": "10",
        "permalink_token": f"o1tok{secrets.token_hex(4)}", "permalink_pin": "246810",
        "permalink_window_days": 3, "permalink_reachback_days": 90, "passport_photo_policy": "required_foreign",
        "guest_message": "Synthetic welcome.", "lock_provider": "ttlock", "lock_id": LOCK["lock_id"],
        "checkin_hour": 15, "checkout_hour": 10, "active": 1, "created_at": now,
    })
    db.insert("lock_account", {"owner_user_id": owner, "provider": "ttlock", "username": "synthetic_o1",
                               "status": "ok", "locks_json": json.dumps([LOCK]), "created_at": now, "updated_at": now})
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"client": client, "owner": owner, "apartment": apartment, "entity": entity}
    db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner,))
    patch.undo()


@pytest.fixture(scope="module")
def base(host):
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


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        launched = playwright.chromium.launch(**chromium_launch_kwargs())
        yield launched
        launched.close()


def _page(browser, base, host, width=1280, height=900, **kwargs):
    context = browser.new_context(viewport={"width": width, "height": height}, **kwargs)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": host["client"].cookies.get(auth.SESSION_COOKIE),
                          "url": base + "/"}])
    page = context.new_page()
    native = []
    page.on("dialog", lambda dialog: (native.append(dialog.type), dialog.accept()))
    page.native_dialogs = native
    return page


def _shot(page, name):
    if os.environ.get("UBYHOST_CAPTURE_O1") == "1":
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f"o1-{name}.png"), full_page=False)


def _open(page):
    return page.evaluate("() => document.getElementById('unsaved-dialog').open")


def _focused(page):
    return page.evaluate("""() => {
      const el = document.activeElement;
      if (!el) return null;
      for (const key of ['unsavedStay', 'unsavedDiscard', 'unsavedSave', 'propertyTab']) {
        if (key in el.dataset) return key + ':' + el.dataset[key];
      }
      return el.id || el.textContent.trim();
    }""")


def _view(page):
    return page.evaluate("() => [...document.querySelectorAll('[data-property-view].is-active')].map(e => e.dataset.propertyView)")


def _stored(host, column, table="apartment", key="apartment"):
    return db.query_one(f"SELECT {column} FROM {table} WHERE id = ?", (host[key],))[column]


def _check_dialog(page, lang, width):
    assert _open(page)
    dialog = page.locator("#unsaved-dialog")
    assert dialog.locator("h2").inner_text() == TEXT[lang]["title"]
    labels = [b.inner_text() for b in dialog.locator("button").all()]
    assert labels == [TEXT[lang]["stay"], TEXT[lang]["discard"], TEXT[lang]["save"]]
    assert _focused(page) == "unsavedStay:"
    box = dialog.bounding_box()
    assert box and box["x"] >= 0 and box["x"] + box["width"] <= width + 1, box
    for button in dialog.locator("button").all():
        b = button.bounding_box()
        assert b["x"] >= box["x"] - 1 and b["x"] + b["width"] <= box["x"] + box["width"] + 1, b
        assert b["height"] >= 40


@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_property_settings_save_discard_stay(browser, base, host, lang, width, height):
    db.execute("UPDATE apartment SET internal_name = ? WHERE id = ?", (NAME, host["apartment"]))
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host, width, height)
    page.goto(f"{url}?view=settings&section=property&lang={lang}")
    reset = page.locator(".host-property-save [data-unsaved-reset]")
    bookings = page.locator('.property-tabs a[data-property-tab="bookings"]')
    settings = page.locator('.property-tabs a[data-property-tab="settings"]')

    # Clean form: no dialog, the tab simply switches.
    assert not reset.is_visible()
    bookings.click()
    assert not _open(page) and _view(page) == ["bookings"]
    settings.click()

    # Dirty: the save bar offers Discard changes; the Settings sub-nav keeps the draft.
    page.fill("#internal_name", "Typed O1 draft")
    assert reset.is_visible() and reset.inner_text() == TEXT[lang]["reset"]
    page.locator('[data-property-section-link="guests"]').click()
    assert not _open(page) and _view(page) == ["settings"]
    page.locator('[data-property-section-link="property"]').click()

    # Another tab asks. Stay keeps the value and the focus on the tab.
    bookings.click()
    _check_dialog(page, lang, width)
    _shot(page, f"property-dialog-{lang}-{width}")
    page.locator("#unsaved-dialog [data-unsaved-stay]").click()
    assert not _open(page) and _view(page) == ["settings"]
    assert page.input_value("#internal_name") == "Typed O1 draft"
    assert _focused(page) == "propertyTab:bookings"

    # Esc is Stay.
    bookings.click()
    assert _open(page)
    page.keyboard.press("Escape")
    assert not _open(page) and _view(page) == ["settings"]
    assert page.input_value("#internal_name") == "Typed O1 draft"
    assert _focused(page) == "propertyTab:bookings"

    # Discard restores the loaded value and follows the link.
    bookings.click()
    page.locator("#unsaved-dialog [data-unsaved-discard]").click()
    assert not _open(page) and _view(page) == ["bookings"] and "view=bookings" in page.url
    assert page.input_value("#internal_name") == NAME
    assert _stored(host, "internal_name") == NAME
    settings.click()
    assert not reset.is_visible()
    bookings.click()  # clean again: no dialog
    assert not _open(page) and _view(page) == ["bookings"]

    # Save submits the form; the host lands where return_to says.
    settings.click()
    saved = f"Saved O1 {lang} {width}"
    page.fill("#internal_name", saved)
    page.locator('.property-tabs a[data-property-tab="overview"]').click()
    assert _open(page)
    with page.expect_navigation():
        page.locator("#unsaved-dialog [data-unsaved-save]").click()
    assert "view=settings&section=property" in page.url
    assert _stored(host, "internal_name") == saved
    assert page.input_value("#internal_name") == saved
    assert page.native_dialogs == [], "the browser's own prompt must not fire after Save or Discard"
    page.context.close()


def test_property_rail_and_back_links_ask_and_cards_into_settings_do_not(browser, base, host):
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    page.fill("#internal_name", "Rail O1 draft")
    page.locator('.sidebar-nav a[href="/reservations"]').first.click()
    assert _open(page)
    page.keyboard.press("Escape")
    page.locator('.host-property-save a[href="/apartments"]').click()
    assert _open(page)
    page.locator("#unsaved-dialog [data-unsaved-stay]").click()
    assert "/apartments/" in page.url and page.input_value("#internal_name") == "Rail O1 draft"
    # Back to Overview keeps the draft; a card into Settings keeps it too.
    page.goto(f"{url}?view=overview&lang=en")
    page.locator('.property-tabs a[data-property-tab="settings"]').click()
    page.fill("#internal_name", "Card O1 draft")
    page.go_back()
    assert not _open(page) and _view(page) == ["overview"]
    page.locator(".host-property-card", has_text="Police reporting").click()
    assert not _open(page) and _view(page) == ["settings"]
    assert page.input_value("#internal_name") == "Card O1 draft"
    # Discard via the rail leaves the page without the native prompt (the
    # goto above left a dirty form, so the browser asked once already).
    page.native_dialogs.clear()
    page.locator('.sidebar-nav a[href="/reservations"]').first.click()
    with page.expect_navigation():
        page.locator("#unsaved-dialog [data-unsaved-discard]").click()
    assert page.url.split("?")[0].endswith("/reservations")
    assert page.native_dialogs == []
    assert _stored(host, "internal_name") != "Card O1 draft"
    page.context.close()


@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_save_bar_discard_changes_button(browser, base, host, lang, width, height):
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host, width, height)
    page.goto(f"{url}?view=settings&section=guests&lang={lang}")
    reset = page.locator(".host-property-save [data-unsaved-reset]")
    status = page.locator("#door_codes-status")
    loaded_status = status.inner_text()
    loaded_message = page.input_value("#guest_message")
    assert not reset.is_visible()
    page.fill("#guest_message", "Typed welcome to discard")
    # 0096: the door-code switch lives in its own Door lock group.
    page.locator('[data-property-section-link="lock"]').click()
    page.locator("#door_codes").click()
    assert status.inner_text() != loaded_status
    assert reset.is_visible()
    box = reset.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= width + 1
    _shot(page, f"property-discard-button-{lang}-{width}")
    reset.click()
    assert page.input_value("#guest_message") == loaded_message
    assert status.inner_text() == loaded_status
    assert not reset.is_visible()
    assert _focused(page) in (TEXT[lang]["save"], "Save changes", "Uložit změny")
    page.locator('.property-tabs a[data-property-tab="overview"]').click()
    assert not _open(page) and _view(page) == ["overview"]
    page.context.close()


def test_keyboard_only_flow(browser, base, host):
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    page.focus("#internal_name")
    page.keyboard.press("End")
    page.keyboard.type(" keyed")
    typed = page.input_value("#internal_name")
    page.focus('.property-tabs a[data-property-tab="bookings"]')
    page.keyboard.press("Enter")
    assert _open(page) and _focused(page) == "unsavedStay:"
    # Tab stays inside the dialog, both ways.
    page.keyboard.press("Tab")
    assert _focused(page) == "unsavedDiscard:"
    page.keyboard.press("Tab")
    assert _focused(page) == "unsavedSave:"
    page.keyboard.press("Tab")
    assert _focused(page) == "unsavedStay:"
    page.keyboard.press("Shift+Tab")
    assert _focused(page) == "unsavedSave:"
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Shift+Tab")
    assert _focused(page) == "unsavedStay:"
    page.keyboard.press("Enter")  # Stay
    assert not _open(page) and _focused(page) == "propertyTab:bookings"
    assert page.input_value("#internal_name") == typed
    page.keyboard.press("Enter")
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")  # Discard
    assert not _open(page) and _view(page) == ["bookings"]
    assert page.input_value("#internal_name") != typed
    page.context.close()


@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_business_editor_save_discard_stay(browser, base, host, lang, width, height):
    db.execute("UPDATE legal_entity SET contact_phone = ? WHERE id = ?", (PHONE, host["entity"]))
    page = _page(browser, base, host, width, height)
    editor = f"{base}/entities?edit={host['entity']}&lang={lang}"
    page.goto(editor)
    close = page.locator("#entity-edit .ui-section-h a.ui-btn")

    # Clean: the link just goes.
    with page.expect_navigation():
        close.click()
    assert "edit=" not in page.url
    page.goto(editor)

    page.fill("#edit_contact_phone", "+420 111 222 333")
    close.click()
    _check_dialog(page, lang, width)
    _shot(page, f"business-dialog-{lang}-{width}")
    page.locator("#unsaved-dialog [data-unsaved-stay]").click()
    assert not _open(page) and "edit=" in page.url
    assert page.input_value("#edit_contact_phone") == "+420 111 222 333"
    assert _focused(page) == close.inner_text().strip()

    close.click()
    page.keyboard.press("Escape")
    assert not _open(page) and page.input_value("#edit_contact_phone") == "+420 111 222 333"

    close.click()
    with page.expect_navigation():
        page.locator("#unsaved-dialog [data-unsaved-discard]").click()
    assert "edit=" not in page.url
    assert _stored(host, "contact_phone", "legal_entity", "entity") == PHONE

    page.goto(editor)
    page.fill("#edit_contact_phone", "+420 999 888 777")
    close.click()
    assert _open(page)
    with page.expect_navigation():
        page.locator("#unsaved-dialog [data-unsaved-save]").click()
    assert _stored(host, "contact_phone", "legal_entity", "entity").replace(" ", "") == "+420999888777"
    assert page.native_dialogs == []
    page.context.close()


def test_without_javascript_nothing_changes(browser, base, host):
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host, java_script_enabled=False)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    assert not page.locator("#unsaved-dialog").is_visible()
    assert not page.locator(".host-property-save [data-unsaved-reset]").is_visible()
    page.fill("#internal_name", "No JS O1 name")
    with page.expect_navigation():
        page.locator(".host-property-save .ui-btn-primary").click()
    assert _stored(host, "internal_name") == "No JS O1 name"
    page.goto(f"{url}?view=settings&section=property&lang=en")
    page.fill("#internal_name", "No JS unsaved")
    with page.expect_navigation():
        page.locator('.property-tabs a[data-property-tab="bookings"]').click()
    assert "view=bookings" in page.url
    assert _stored(host, "internal_name") == "No JS O1 name"
    page.context.close()
    db.execute("UPDATE apartment SET internal_name = ? WHERE id = ?", (NAME, host["apartment"]))
