"""0096: guided setup of a new property, one step and one primary action at a time."""
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

from app import auth, config, db, feed_url, guest_slug, host_i18n, icalsync, property_setup
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0096-evidence"
ADDRESS = {"addr_obec": "Brno", "addr_house_no": "12", "addr_zip": "602 00", "addr_street": "Synthetic"}
POLICE = {"uby_idub": "123456789012", "uby_ws_user": "UBY-WSsynth", "uby_ws_password": "synthetic-secret",
          "uby_mark": "SYNTH", "uby_name": "Synthetic Garden"}
TITLES = ("calendar", "guest_links", "reporting", "fee", "lock", "automation")


def _t(lang, key, **kwargs):
    return host_i18n.translate(lang, key, **kwargs)


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    # Door codes exist on this deployment, so the guide has all six steps.
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    # A calendar is "connected" without the network: synthetic URL, no fetch.
    monkeypatch.setattr(feed_url, "validate_calendar_url", lambda url: url)
    monkeypatch.setattr(icalsync, "sync_all", lambda apartment_id=None, owner_user_id=None: {
        "feeds": 1, "created": 0, "updated": 0, "cancelled": 0, "errors": 0,
        "not_modified": 0, "unchanged": 0, "changed": 0})
    username = f"guide-{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Guide Host", role="host", username=username)
    entity = db.insert("legal_entity", {"name": "Synthetic Operator s.r.o.", "seat": "Brno", "ico": "12345678",
                                        "contact_email": "guide@example.test", "owner_user_id": owner,
                                        "created_at": db.utcnow()})
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"client": client, "owner": owner, "entity": entity}
    for row in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (owner,)):
        db.execute("DELETE FROM settings WHERE key = ?", (f"property_setup:{row['id']}",))
    db.execute("DELETE FROM ical_feed WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (owner,))


def _create(host, name="Synthetic Garden Flat"):
    response = host["client"].post("/apartments", data={
        "internal_name": name, "city_en": "Brno", "legal_entity_id": str(host["entity"]),
        "default_purpose": "10", **ADDRESS}, follow_redirects=False)
    assert response.status_code == 303, response.text
    return db.query_one("SELECT * FROM apartment WHERE owner_user_id = ? ORDER BY id DESC LIMIT 1", (host["owner"],))


def _step(html):
    """The guide's current step key, or None."""
    if "data-setup-guide" not in html:
        return None
    for key in TITLES:
        for lang in ("en", "cs"):
            if f"· {_t(lang, f'setup_guide.{key}.title')}</h2>" in html.replace("&#39;", "'"):
                return key
    raise AssertionError("guide without a known step")


# --- server: state, order, refusals ----------------------------------------


def test_create_starts_the_guide_and_old_properties_never_see_it(host):
    flat = _create(host)
    assert property_setup.load(flat["id"]) == {"steps": {}, "finished": False}
    page = host["client"].get(f"/apartments/{flat['id']}?lang=en").text
    assert _step(page) == "calendar"
    assert "Step 1 of 6 · Connect your calendar" in page
    assert "property-first-use" not in page and _t("en", "property_create.created_title") not in page
    # A property from before 0096 (no stored state) never shows the guide, set up or not.
    legacy = db.insert("apartment", {"internal_name": "Legacy Flat", "owner_user_id": host["owner"],
                                     "legal_entity_id": host["entity"], **ADDRESS, **{k: v for k, v in POLICE.items() if k != "uby_ws_password"},
                                     "uby_ws_password_enc": db.encrypt_secret("x"), "permalink_token": f"lg{secrets.token_hex(5)}",
                                     "permalink_pin": "135790", "active": 1, "created_at": db.utcnow()})
    legacy_page = host["client"].get(f"/apartments/{legacy}?lang=en").text
    assert _step(legacy_page) is None
    assert 'class="panel host-setup-complete"' in legacy_page or "host-checklist" in legacy_page
    bare = db.insert("apartment", {"internal_name": "Bare Legacy", "owner_user_id": host["owner"],
                                   "permalink_token": f"lb{secrets.token_hex(5)}", "active": 1, "created_at": db.utcnow()})
    assert _step(host["client"].get(f"/apartments/{bare}").text) is None


def test_steps_answer_only_the_step_on_screen(host):
    flat = _create(host)
    client, base = host["client"], f"/apartments/{flat['id']}"
    # Reporting has no skip; a step that is not on screen cannot be answered.
    for step, action in (("reporting", "skip"), ("guest_links", "done"), ("automation", "keep"), ("calendar", "done")):
        response = client.post(f"{base}/setup", data={"step": step, "action": action}, follow_redirects=False)
        assert response.status_code == 303
        assert property_setup.load(flat["id"])["steps"] == {}, (step, action)
    skipped = client.post(f"{base}/setup", data={"step": "calendar", "action": "skip"}, follow_redirects=False)
    assert skipped.headers["location"] == f"{base}?view=overview#property-setup"
    assert property_setup.load(flat["id"])["steps"] == {"calendar": "skipped"}
    assert client.post(f"{base}/setup", data={"step": "guest_links", "action": "skip"}, follow_redirects=False)
    assert "guest_links" not in property_setup.load(flat["id"])["steps"]
    done = client.post(f"{base}/setup", data={"step": "guest_links", "action": "done"}, follow_redirects=False)
    assert done.headers["location"] == f"{base}?view=settings&section=reporting#ubyport"
    # A save from another section during the fee step does not count as the fee.
    for key, value in POLICE.items():
        db.update("apartment", flat["id"], {key: value} if key != "uby_ws_password" else {"uby_ws_password_enc": db.encrypt_secret(value)})
    page = client.get(f"{base}?lang=en").text
    assert _step(page) == "fee"
    assert '<input type="hidden" name="setup_step" value="fee">' in page
    saved = client.post(base, data={"internal_name": flat["internal_name"], "legal_entity_id": str(host["entity"]),
                                    "setup_step": "fee", "return_to": f"{base}?view=settings&section=property"},
                        follow_redirects=False)
    assert saved.headers["location"].startswith(f"{base}?view=settings&section=reporting")
    assert "fee" not in property_setup.load(flat["id"])["steps"]
    # Another host cannot touch it.
    other = auth.create_account(f"guide-other-{secrets.token_hex(3)}@example.test", "Other", role="host",
                                username=f"guide-other-{secrets.token_hex(3)}")
    stranger = TestClient(app)
    login_as(stranger, db.query_one("SELECT username FROM user_account WHERE id = ?", (other,))["username"])
    stranger.post(f"{base}/setup", data={"step": "fee", "action": "skip"}, follow_redirects=False)
    assert "fee" not in property_setup.load(flat["id"])["steps"]


def test_a_finished_guide_stays_finished(host):
    flat = _create(host)
    db.set_setting(f"property_setup:{flat['id']}", json.dumps({"steps": {}, "finished": True}))
    assert _step(host["client"].get(f"/apartments/{flat['id']}").text) is None
    db.set_setting(f"property_setup:{flat['id']}", "not json")
    assert _step(host["client"].get(f"/apartments/{flat['id']}").text) is None


def test_door_lock_is_its_own_settings_group_and_old_links_land_there(host):
    flat = _create(host)
    property_setup.finish(flat["id"])
    page = host["client"].get(f"/apartments/{flat['id']}?view=settings&section=lock&lang=en").text
    nav = page[page.index('class="property-settings-nav"'):page.index("</nav>", page.index('class="property-settings-nav"'))]
    labels = [_t("en", f"property_nav.group.{k}") for k in ("property", "guests", "reporting", "lock", "automation")]
    positions = [nav.index(label.replace("&", "&amp;")) for label in labels]
    assert positions == sorted(positions)
    # The group sits where the lock section always was in the page (before
    # Reporting); the sub-nav above puts it in its place in the list.
    lock = page[page.index('id="settings-lock"'):page.index('id="settings-reporting"')]
    assert 'class="property-settings-group is-active" data-settings-group="lock"' in page
    assert 'id="door-code"' in lock and _t("en", "property_nav.lock_intro").replace("'", "&#39;") in lock
    assert "TTLock locks that have a gateway" in lock
    guests = page[page.index('id="settings-guests"'):page.index('id="settings-lock"')]
    assert 'id="door-code"' not in guests
    # The lock page's way back still names #door-code, which now opens this group.
    assert f"return_to=/apartments/{flat['id']}%23door-code" in lock
    # Without door codes on the deployment there is no Door lock group or step.
    config.DOOR_CODES_ENABLED = False
    try:
        off = host["client"].get(f"/apartments/{flat['id']}?view=settings&section=lock").text
        assert 'data-settings-group="lock"' not in off
        assert 'class="property-settings-group is-active" data-settings-group="property"' in off
    finally:
        config.DOOR_CODES_ENABLED = True


# --- browser ----------------------------------------------------------------


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base():
    db.init_db()
    port = _free_port()
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


def _context(browser, base, host, width=1280, **kwargs):
    context = browser.new_context(viewport={"width": width, "height": 900}, **kwargs)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": host["client"].cookies.get(auth.SESSION_COOKIE), "url": base + "/"}])
    return context


def _shot(page, name):
    if os.environ.get("UBYHOST_CAPTURE_GUIDE") == "1":
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f"{name}.png"), full_page=True)


_PRIMARIES_JS = """() => [...document.querySelectorAll('#main-content .btn.primary')]
  .filter(el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
                  return r.width > 0 && r.height > 0 && s.visibility !== 'hidden'; })
  .map(el => el.textContent.trim())"""
_FIT_JS = """() => { const vw = document.documentElement.clientWidth;
  const bad = [...document.querySelectorAll('#property-setup *, #main-content .btn')].filter(el => {
    const r = el.getBoundingClientRect(); return r.width && (r.right > vw + 1 || r.left < -1); })
    .map(el => el.textContent.trim().slice(0, 30));
  return {scroll: document.documentElement.scrollWidth, vw, bad}; }"""


def _check_step(page, lang, number, key, primary, name, js=True):
    heading = page.locator("#property-setup-title")
    assert heading.is_visible()
    expected = f"{_t(lang, 'setup_guide.count', n=number, total=6)} · {_t(lang, f'setup_guide.{key}.title')}"
    assert heading.inner_text().strip() == expected
    primaries = page.evaluate(_PRIMARIES_JS)
    assert primaries == [primary], (key, primaries)
    skip = page.locator("#property-setup button[value='skip']")
    assert skip.count() == (1 if key in ("fee", "lock") else 0), key
    fit = page.evaluate(_FIT_JS)
    assert fit["scroll"] <= fit["vw"] + 1 and not fit["bad"], (key, fit)
    _shot(page, name)


def _journey(page, base, host, lang, width, js=True):
    tag = f"{width}-{lang}" + ("" if js else "-nojs")
    page.goto(f"{base}/apartments/new?lang={lang}")
    page.fill("#internal_name", f"Synthetic Guide Flat {lang} {width} {'js' if js else 'nojs'}")
    for field, value in ADDRESS.items():
        page.fill(f"#{field}", value)
    page.locator(".property-create-actions .btn.primary").click()
    page.wait_for_load_state()
    flat = db.query_one("SELECT * FROM apartment WHERE owner_user_id = ? ORDER BY id DESC LIMIT 1", (host["owner"],))
    assert f"/apartments/{flat['id']}?view=bookings" in page.url

    # 1. Calendar: only the connect form, one primary, one quiet way past it.
    _check_step(page, lang, 1, "calendar", _t(lang, "property_nav.add_calendar"), f"1-calendar-{tag}", js)
    assert page.locator("#calendar-add #url").is_visible()
    assert not page.locator(".property-view.is-active .property-view-head").count()
    assert not page.locator(".property-first-use").count()
    skip_link = page.locator(".property-setup-skip .link-button")
    assert skip_link.inner_text().strip() == _t(lang, "setup_guide.calendar.skip")
    if lang == "en":
        page.select_option("#label", "airbnb")
        page.fill("#url", "https://www.airbnb.example/calendar/ical/synthetic.ics")
        page.locator("#calendar-add .btn.primary").click()
    else:
        skip_link.click()
    page.wait_for_load_state()

    # 2. Guest links: link and PIN as one ready message, one Copy, one Done.
    flat = db.query_one("SELECT * FROM apartment WHERE id = ?", (flat["id"],))
    _check_step(page, lang, 2, "guest_links", _t(lang, "setup_guide.guest_links.done"), f"2-guest-links-{tag}", js)
    snippet = page.locator("#setup-guest-snippet").input_value()
    link_key = guest_slug.current(flat["id"])
    assert snippet == _t(lang, "setup_guide.guest_links.snippet", url=f"{config.PUBLIC_BASE_URL}/l/{link_key}", pin=flat["permalink_pin"])
    copy = page.locator("#property-setup [data-copy='setup-guest-snippet']")
    assert copy.inner_text().strip() == _t(lang, "setup_guide.guest_links.copy")
    if js:
        copy.click()
        assert page.evaluate("() => navigator.clipboard.readText()") == snippet
    page.locator("#property-setup .btn.primary").click()
    page.wait_for_load_state()

    # 3. Police reporting: the Settings group with Save as the one primary.
    _check_step(page, lang, 3, "reporting", _t(lang, "common.save_changes"), f"3-reporting-{tag}", js)
    assert page.locator("#ubyport").is_visible()
    for field, value in POLICE.items():
        page.fill(f"#{field}", value)
    page.locator(".host-property-save .btn.primary").click()
    page.wait_for_load_state()

    # 4. Stay fee (optional): Skip.
    _check_step(page, lang, 4, "fee", _t(lang, "common.save_changes"), f"4-fee-{tag}", js)
    assert page.locator("#stay-fee-settings").is_visible()
    page.locator("#property-setup button[value='skip']").click()
    page.wait_for_load_state()

    # 5. Door lock (optional): its own group, Skip.
    _check_step(page, lang, 5, "lock", _t(lang, "common.save_changes"), f"5-lock-{tag}", js)
    assert page.locator('[data-settings-group="lock"] #door-code').is_visible()
    assert page.locator('[data-property-section-link="lock"][aria-current]').is_visible()
    page.locator("#property-setup button[value='skip']").click()
    page.wait_for_load_state()

    # 6. Automation: Save once (EN) or keep manual sending (CS).
    _check_step(page, lang, 6, "automation", _t(lang, "common.save_changes"), f"6-automation-{tag}", js)
    assert page.locator("#automation").is_visible()
    keep = page.locator("#property-setup button[value='keep']")
    assert keep.inner_text().strip() == _t(lang, "setup_guide.automation.keep_manual")
    if lang == "en":
        page.locator(".host-property-save .btn.primary").click()
    else:
        keep.click()
    page.wait_for_load_state()

    # Done: one compact status, no guide.
    assert "view=overview" in page.url
    assert not page.locator("#property-setup").count()
    assert page.locator(".host-setup-complete").is_visible()
    assert not page.locator(".host-checklist").count()
    assert property_setup.load(flat["id"])["finished"] is True
    marks = property_setup.load(flat["id"])["steps"]
    assert marks == {**({"calendar": "skipped"} if lang == "cs" else {}), "guest_links": "done",
                     "fee": "skipped", "lock": "skipped", "automation": "done"}
    _shot(page, f"7-complete-{tag}")
    return flat


@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("width", [1280, 360])
def test_first_time_journey_in_browser(host, base, lang, width):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = _context(browser, base, host, width=width)
        context.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        page = context.new_page()
        flat = _journey(page, base, host, lang, width)
        # Leaving and coming back never brings the guide back.
        page.goto(f"{base}/apartments/{flat['id']}?lang={lang}")
        assert not page.locator("#property-setup").count()
        browser.close()


def test_guide_continue_follows_tab_switches_in_browser(host, base):
    flat = _create(host)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        page.goto(f"{base}/apartments/{flat['id']}?lang=en")
        cont = page.locator("#property-setup [data-setup-continue]")
        assert "view=bookings" in page.url or page.locator("#calendar-add").is_visible()
        assert not cont.is_visible()
        page.locator('.property-tabs a[data-property-tab="overview"]').click()
        assert cont.is_visible() and page.evaluate(_PRIMARIES_JS) == ["Continue"]
        cont.click()
        page.wait_for_load_state()
        assert page.locator("#calendar-add").is_visible() and not cont.is_visible()
        browser.close()


def test_first_time_journey_without_javascript(host, base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host, java_script_enabled=False).new_page()
        _journey(page, base, host, "cs", 1280, js=False)
        browser.close()


def test_slug_follows_a_rename_and_the_old_link_redirects_in_browser(host, base):
    flat = _create(host, "Synthetic Old Name")
    property_setup.finish(flat["id"])
    old = guest_slug.current(flat["id"])
    assert old.startswith("synthetic-old-name-")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host).new_page()
        page.goto(f"{base}/apartments/{flat['id']}?view=settings&section=guests&lang=en")
        assert not page.locator("#guest_link_name").count()
        page.locator('[data-property-section-link="property"]').click()
        page.fill("#internal_name", "Synthetic New Name")
        page.locator(".host-property-save .btn.primary").click()
        page.wait_for_load_state()
        new = guest_slug.current(flat["id"])
        assert new == "synthetic-new-name-" + guest_slug.code_of(old)
        page.goto(f"{base}/apartments/{flat['id']}?view=settings&section=guests&lang=en")
        assert page.locator("#permalink").input_value().endswith(f"/l/{new}")
        guest = browser.new_context().new_page()
        guest.goto(f"{base}/l/{old}?lang=en")
        assert guest.url == f"{base}/l/{new}?lang=en"
        browser.close()
