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
from urllib.parse import urlparse

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
from tests.conftest import login_as, mark_security_prompt_seen

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0084-evidence"
LOCK = {"lock_id": "70840001", "alias": "Synthetic O1 Door", "battery": 90, "tz_offset_ms": 3600000}
NAME = "Synthetic O1 Flat"
PHONE = "+420 777 000 111"
TEXT = {
    "en": {"title": "You have unsaved changes", "save": "Save", "discard": "Discard", "stay": "Stay",
           "reset": "Cancel"},
    "cs": {"title": "Máte neuložené změny", "save": "Uložit", "discard": "Zahodit", "stay": "Zůstat",
           "reset": "Zrušit"},
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
    owner = mark_security_prompt_seen(auth.create_account(f"{username}@example.test", "O1 Host", role="host", username=username))
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


def _section_opener(page, key):
    """Owner decision 2026-11-08: 6 pills as switcher (brief 1030). At >=768 px the pill opens a section; phones tap the title."""
    if page.viewport_size["width"] >= 768:
        return page.locator(f'nav.prop-strip a[href="#sec-{key}"]').first
    return page.locator(f"#sec-{key} > summary")


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


def _open_sections(page):
    return page.evaluate("() => [...document.querySelectorAll('details.prop-sec[open]')].map(e => e.id)")


def _focus_is(page, selector):
    return page.evaluate("(sel) => !!document.activeElement && document.activeElement.matches(sel)", selector)


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
        assert b["height"] >= (36 if width >= 1024 else 44), b


@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_property_settings_save_discard_stay(browser, base, host, lang, width, height):
    db.execute("UPDATE apartment SET internal_name = ? WHERE id = ?", (NAME, host["apartment"]))
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host, width, height)
    page.goto(f"{url}?view=settings&section=property&lang={lang}")
    reset = page.locator(".savebar[data-for='property-settings-form'] [data-unsaved-reset]")
    leave = 'a.airbnb-back'
    crumb = page.locator(leave)
    calendars = _section_opener(page, "calendars")

    # Clean form: no dialog, the in-page link just opens its section.
    assert not page.locator(".savebar[data-for='property-settings-form']").is_visible()
    calendars.click()
    assert not _open(page) and "sec-calendars" in _open_sections(page)

    # Dirty: the save bar offers Discard changes; in-page links keep the draft.
    if width >= 768:  # owner decision 2026-11-08 (brief 1030): one section at a time, so go back to Basic details
        _section_opener(page, "basics").click()
    page.fill("#internal_name", "Typed O1 draft")
    assert page.locator(".savebar[data-for='property-settings-form']").is_visible() and reset.inner_text() == TEXT[lang]["reset"]
    _section_opener(page, "lock").click()
    assert not _open(page)
    assert page.input_value("#internal_name") == "Typed O1 draft"

    # A link that leaves the page asks. Stay keeps the value and the focus on that link.
    crumb.click()
    _check_dialog(page, lang, width)
    _shot(page, f"property-dialog-{lang}-{width}")
    page.locator("#unsaved-dialog [data-unsaved-stay]").click()
    assert not _open(page) and "/apartments/" in page.url
    assert page.input_value("#internal_name") == "Typed O1 draft"
    assert _focus_is(page, leave)

    # Esc is Stay.
    crumb.click()
    assert _open(page)
    page.keyboard.press("Escape")
    assert not _open(page) and "/apartments/" in page.url
    assert page.input_value("#internal_name") == "Typed O1 draft"
    assert _focus_is(page, leave)

    # Discard restores the loaded value and follows the link.
    crumb.click()
    with page.expect_navigation():
        page.locator("#unsaved-dialog [data-unsaved-discard]").click()
    assert urlparse(page.url).path.rstrip("/") == "/apartments"
    assert _stored(host, "internal_name") == NAME
    page.goto(f"{url}?view=settings&section=property&lang={lang}")
    assert not page.locator(".savebar[data-for='property-settings-form']").is_visible()
    assert page.input_value("#internal_name") == NAME

    # Save: the form posts, and the value is stored.
    saved = f"Saved O1 {lang} {width}"
    page.fill("#internal_name", saved)
    crumb.click()
    assert _open(page)
    with page.expect_navigation():
        page.locator("#unsaved-dialog [data-unsaved-save]").click()
    assert _stored(host, "internal_name") == saved
    assert page.native_dialogs == [], "the browser's own prompt must not fire after Save or Discard"
    page.context.close()


def test_property_rail_and_back_links_ask_and_cards_into_settings_do_not(browser, base, host):
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    page.fill("#internal_name", "Rail O1 draft")
    page.locator(".me-menu > summary").click()  # 0896: Settings lives in the profile menu
    page.locator('.me-menu-list a[href="/settings"]').click()
    assert _open(page)
    page.keyboard.press("Escape")
    page.locator('a.airbnb-back[href="/apartments"]').click()
    assert _open(page)
    page.locator("#unsaved-dialog [data-unsaved-stay]").click()
    assert "/apartments/" in page.url and page.input_value("#internal_name") == "Rail O1 draft"
    # An in-page aside link into Police keeps the draft and does not ask.
    _section_opener(page, "police").click()
    assert not _open(page) and "sec-police" in _open_sections(page)
    assert page.input_value("#internal_name") == "Rail O1 draft"
    # Discard via the rail leaves the page without the native prompt.
    page.native_dialogs.clear()
    page.locator(".me-menu > summary").click()  # 0896: Settings lives in the profile menu
    page.locator('.me-menu-list a[href="/settings"]').click()
    with page.expect_navigation():
        page.locator("#unsaved-dialog [data-unsaved-discard]").click()
    assert page.url.split("?")[0].endswith("/settings")
    assert page.native_dialogs == []
    assert _stored(host, "internal_name") != "Rail O1 draft"
    page.context.close()


@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_save_bar_discard_changes_button(browser, base, host, lang, width, height):
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host, width, height)
    page.goto(f"{url}?view=settings&section=guests&lang={lang}")
    reset = page.locator(".savebar[data-for='property-settings-form'] [data-unsaved-reset]")
    loaded_message = page.input_value("#guest_message")
    assert not page.locator(".savebar[data-for='property-settings-form']").is_visible()
    page.fill("#guest_message", "Typed welcome to discard")
    # 0096: the door-code switch lives in its own Door lock group.
    # 0736: inner_text() is "" inside a closed <details>, so read the status
    # after the section opens and use text_content(), which holds the saved text.
    # 0955: the outside-control leg (door-code switch) needs a connected lock; it moved to the matrix test.
    assert page.locator(".savebar[data-for='property-settings-form']").is_visible()
    box = reset.bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= width + 1
    _shot(page, f"property-discard-button-{lang}-{width}")
    reset.click()
    assert page.input_value("#guest_message") == loaded_message
    assert not page.locator(".savebar[data-for='property-settings-form']").is_visible()
    _section_opener(page, "calendars").click()
    assert not _open(page) and "sec-calendars" in _open_sections(page)
    page.context.close()


def test_keyboard_only_flow(browser, base, host):
    leave = 'a.airbnb-back'
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    page.focus("#internal_name")
    page.keyboard.press("End")
    page.keyboard.type(" keyed")
    typed = page.input_value("#internal_name")
    page.focus("a.airbnb-back")
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
    assert not _open(page) and _focus_is(page, leave)
    assert page.input_value("#internal_name") == typed
    page.keyboard.press("Enter")
    page.keyboard.press("Tab")
    with page.expect_navigation():
        page.keyboard.press("Enter")  # Discard
    assert urlparse(page.url).path.rstrip("/") == "/apartments"
    assert _stored(host, "internal_name") != typed
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
    assert page.locator(".savebar[data-for='property-settings-form']").is_visible()
    page.fill("#internal_name", "No JS O1 name")
    with page.expect_navigation():
        page.locator(".savebar button[type=submit]").click()
    assert _stored(host, "internal_name") == "No JS O1 name"
    page.goto(f"{url}?view=settings&section=property&lang=en")
    page.fill("#internal_name", "No JS cancel")
    with page.expect_navigation():
        page.locator(".savebar a[data-unsaved-reset]").click()
    assert page.input_value("#internal_name") == "No JS O1 name"
    assert page.url.split("?")[0].endswith(f"/apartments/{host['apartment']}")
    # 1099: sections start closed on a bare /apartments/N; open Basic details by its link.
    page.goto(f"{url}?view=settings&section=property&lang=en")
    page.fill("#internal_name", "No JS unsaved")
    with page.expect_navigation():
        page.locator('a.airbnb-back[href="/apartments"]').click()
    assert urlparse(page.url).path.rstrip("/") == "/apartments"
    assert _stored(host, "internal_name") == "No JS O1 name"
    page.context.close()
    db.execute("UPDATE apartment SET internal_name = ? WHERE id = ?", (NAME, host["apartment"]))


@pytest.mark.parametrize("width,height", SIZES)
def test_outside_lock_control_counts_and_the_lock_buttons_do_not(browser, base, host, width, height):
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host, width, height)
    page.goto(f"{url}?view=settings&section=lock&lang=en")
    bar = page.locator(".savebar[data-for='property-settings-form']")
    cancel = page.locator(".savebar[data-for='property-settings-form'] [data-unsaved-reset]")
    assert not bar.is_visible()
    # The Turn on / Turn off buttons submit their own forms: focusing them is no edit of the property form.
    page.locator(".lock-state-form button").first.focus()
    assert page.get_attribute("#property-settings-form", "data-dirty") is None
    assert not bar.is_visible()
    loaded = page.input_value("#lock_checkin_hour")
    page.select_option("#lock_checkin_hour", "23" if loaded != "23" else "22")
    assert page.get_attribute("#property-settings-form", "data-dirty") == "1"
    assert bar.is_visible()
    cancel.click()
    assert page.input_value("#lock_checkin_hour") == loaded
    assert not bar.is_visible()
    assert page.url.split("#")[0] == f"{url}?view=settings&section=lock&lang=en"
    assert int(_stored(host, "checkin_hour")) == 15
    page.context.close()


# 1100 step 5: Stay, Discard and Save on the property editor, including a page that
# loads dirty (no-JS letter read), a Turbo visit after a Save, and a paste fill.
LEAVE = "a.airbnb-back"
SAVE_ROW_1100 = ".savebar[data-for='property-settings-form']"
POLICE_COLUMNS = ("uby_idub", "uby_ws_user", "uby_mark", "uby_name")


def _police_reset(host):
    db.execute(
        "UPDATE apartment SET internal_name = ?, uby_idub = NULL, uby_ws_user = NULL, uby_mark = NULL, "
        "uby_name = NULL WHERE id = ?",
        (NAME, host["apartment"]),
    )


def _police_stored(host):
    row = db.query_one(f"SELECT {', '.join(POLICE_COLUMNS)} FROM apartment WHERE id = ?", (host["apartment"],))
    return {name: row[name] for name in POLICE_COLUMNS}


def _open_police(page):
    page.evaluate("() => { for (const d of document.querySelectorAll("
                  "'#sec-police, details.police-letter-paste')) d.open = true; }")


def _discard_leaves(page):
    """Click the crumb, see the dialog, press Discard: the page must reach /apartments."""
    page.locator(LEAVE).click()
    try:
        page.wait_for_function("() => document.getElementById('unsaved-dialog').open", timeout=3000)
    except Exception as exc:
        state = page.evaluate("() => ({url: location.href, dirty: [...document.querySelectorAll('form[data-unsaved-guard]')].map(f => f.id + ':' + f.dataset.dirty), n: document.querySelectorAll('#unsaved-dialog').length})")
        raise AssertionError(f"the leave dialog did not open: {state}") from exc
    page.locator("#unsaved-dialog [data-unsaved-discard]").click()
    page.wait_for_url(lambda u: urlparse(u).path.rstrip("/") == "/apartments", timeout=5000)


@pytest.mark.parametrize("width", [390, 1280])
def test_1100_stay_discard_save_on_the_property_editor(browser, base, host, width):
    """(a) Stay keeps the edit and the focus, (b) Discard leaves unsaved, (c) Save saves and leaves."""
    _police_reset(host)
    url = f"{base}/apartments/{host['apartment']}?view=settings&section=property&lang=en"
    page = _page(browser, base, host, width, 900)
    page.goto(url)
    page.fill("#internal_name", "Typed 1100 draft")
    page.locator(LEAVE).click()
    assert _open(page)
    page.locator("#unsaved-dialog [data-unsaved-stay]").click()
    assert not _open(page) and page.input_value("#internal_name") == "Typed 1100 draft"
    assert _focus_is(page, LEAVE)

    _discard_leaves(page)
    assert _stored(host, "internal_name") == NAME
    page.goto(url)
    assert page.input_value("#internal_name") == NAME

    page.fill("#internal_name", f"Saved 1100 {width}")
    page.locator(LEAVE).click()
    assert _open(page)
    with page.expect_navigation():
        page.locator("#unsaved-dialog [data-unsaved-save]").click()
    assert _stored(host, "internal_name") == f"Saved 1100 {width}"
    assert page.native_dialogs == []
    page.context.close()


@pytest.mark.parametrize("width", [390, 1280])
def test_1100_discard_leaves_a_page_that_loads_dirty(browser, base, host, width):
    """(d) The no-JS letter read answer (data-dirty-start="1") opened with JS: Discard still leaves."""
    from tests.test_police_letter_flow import LETTER

    _police_reset(host)
    page = _page(browser, base, host, width, 900)
    page.goto(f"{base}/apartments/{host['apartment']}?view=settings&section=reporting&lang=en#ubyport")
    assert not page.locator("[data-letter-read]").is_visible()
    page.evaluate("(text) => { document.getElementById('letter_text').value = text; }", LETTER)
    with page.expect_navigation():
        page.evaluate("() => HTMLFormElement.prototype.submit.call(document.getElementById('police-letter-form'))")
    assert page.locator("#property-settings-form").get_attribute("data-dirty-start") == "1"
    assert page.input_value("#uby_idub")
    _discard_leaves(page)
    assert _police_stored(host) == dict.fromkeys(POLICE_COLUMNS)
    assert page.native_dialogs == []
    page.context.close()


@pytest.mark.parametrize("width", [390, 1280])
def test_1100_discard_leaves_after_a_turbo_visit_that_followed_a_save(browser, base, host, width):
    """(e) Save the business editor once, reach the property editor by an in-app Turbo link, edit, Discard."""
    _police_reset(host)
    page = _page(browser, base, host, width, 900)
    page.goto(f"{base}/entities?edit={host['entity']}&lang=en")
    page.fill("#edit_contact_phone", "+420 111 000 222")
    page.locator("#entity-edit button[type=submit]").first.click()
    page.wait_for_function("() => !location.search.includes('edit=')", timeout=5000)
    page.wait_for_load_state()
    page.evaluate("() => { window.__uby1100 = 1; }")
    link = page.locator(f'a[href^="/apartments/{host["apartment"]}?view=settings"]').first
    link.click()
    page.wait_for_selector("#property-settings-form #internal_name")
    # Turbo swaps the body before turbo:load wires the form; a person cannot type in between.
    page.wait_for_function("() => !!document.getElementById('property-settings-form')._ubyBase")
    assert page.evaluate("() => window.__uby1100") == 1, "the property editor must be reached by a Turbo visit"
    page.evaluate("() => { document.getElementById('sec-basics').open = true; }")
    page.fill("#internal_name", "Turbo 1100 draft")
    _discard_leaves(page)
    assert _stored(host, "internal_name") == NAME
    db.execute("UPDATE legal_entity SET contact_phone = ? WHERE id = ?", (PHONE, host["entity"]))
    page.context.close()


@pytest.mark.parametrize("width", [390, 1280])
def test_1100_discard_leaves_after_a_paste_fill(browser, base, host, width):
    """(f) Paste fills the boxes, then Discard leaves and the reloaded page shows the stored values."""
    from app.ubyport_sample_pdf import SAMPLE_IDUB
    from tests.test_police_letter_flow import LETTER

    _police_reset(host)
    url = f"{base}/apartments/{host['apartment']}?view=settings&section=reporting&lang=en#ubyport"
    page = _page(browser, base, host, width, 900)
    page.goto(url)
    _open_police(page)
    page.fill("#letter_text", LETTER)
    page.dispatch_event("#letter_text", "paste")
    page.wait_for_function(f"() => document.getElementById('uby_idub').value === '{SAMPLE_IDUB}'", timeout=3000)
    assert page.locator(SAVE_ROW_1100).is_visible()
    _discard_leaves(page)
    assert _police_stored(host) == dict.fromkeys(POLICE_COLUMNS)
    page.goto(url)
    assert page.input_value("#uby_idub") == ""
    assert page.native_dialogs == []
    page.context.close()
