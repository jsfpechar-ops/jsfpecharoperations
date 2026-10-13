"""0096/0100: guided setup of a property, one step and one primary action at a time.

0100 added the beginner walk-through (guest link, PIN, a demo stay to try the
guest form), the "still waiting for my police login" path, the guide for
properties made before it, and Hide/Show.
"""
from __future__ import annotations

import base64
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

from app import auth, config, db, demo, feed_url, guest_slug, host_i18n, icalsync, property_setup, reporting
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as
from tests.test_guest_browser_e2e import Guest

CAPTURE = os.environ.get("UBYHOST_CAPTURE_0100") == "1"
EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0100-evidence"
ADDRESS = {"addr_obec": "Brno", "addr_house_no": "12", "addr_zip": "602 00", "addr_street": "Synthetic"}
POLICE = {"uby_idub": "123456789012", "uby_ws_user": "UBY-WSsynth", "uby_ws_password": "synthetic-secret",
          "uby_mark": "SYNTH", "uby_name": "Synthetic Garden"}
TITLES = property_setup.STEPS
TOTAL = len(TITLES)  # door codes are on in these tests
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
FAKE_GUEST = ("Testa", "Probeperson", "14031988", "C01X00T47")


def _t(lang, key, **kwargs):
    return host_i18n.translate(lang, key, **kwargs)


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    # Door codes exist on this deployment, so the guide has all eight steps.
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


def _legacy(host, name, police=True, **extra):
    """A property made before the guide: no stored guide state."""
    values = {"internal_name": name, "owner_user_id": host["owner"], "legal_entity_id": host["entity"],
              "permalink_token": f"lg{secrets.token_hex(5)}", "permalink_pin": "135790", "active": 1,
              "created_at": db.utcnow(), **ADDRESS, **extra}
    if police:
        values.update({k: v for k, v in POLICE.items() if k != "uby_ws_password"})
        values["uby_ws_password_enc"] = db.encrypt_secret("x")
    apartment_id = db.insert("apartment", values)
    assert property_setup.load(apartment_id) is None
    return apartment_id


def _add_stay(apartment_id, source="manual", guest_by=None):
    now = db.utcnow()
    stay = db.insert("reservation", {"apartment_id": apartment_id, "source": source, "uid": f"t-{secrets.token_hex(6)}",
                                     "date_from": "2026-12-01", "date_to": "2026-12-03", "status": "active",
                                     "created_at": now, "updated_at": now})
    if guest_by:
        db.insert("guest", {"reservation_id": stay, "surname": "Probe", "first_name": "Synthetic",
                            "birth_date": "01011990", "nationality": "DEU", "doc_number": "C01X00T47",
                            "res_street": "Street 1", "res_city": "Berlin", "res_country": "DEU", "purpose": "10",
                            "is_lead": 1, "entered_by": guest_by, "signature_png": SIGNATURE, "signed_at": now,
                            "submit_state": reporting.PENDING, "created_at": now, "updated_at": now})
    return stay


def _step(html):
    """The guide's current step key, or None."""
    if "data-setup-guide" not in html:
        return None
    text = html.replace("&#39;", "'")
    for key in TITLES:
        for lang in ("en", "cs"):
            if f"· {_t(lang, f'setup_guide.{key}.title')}</h2>" in text:
                return key
    for lang in ("en", "cs"):
        if f"· {_t(lang, 'setup_guide.try.registered_title')}</h2>" in text:
            return "try"
    raise AssertionError("guide without a known step")


def _police_form(flat, host, step, section="reporting"):
    """The whole Settings form as the browser posts it, police details filled."""
    base = f"/apartments/{flat['id']}"
    return host["client"].post(base, data={
        "internal_name": flat["internal_name"], "legal_entity_id": str(host["entity"]), "city_en": "Brno",
        "default_purpose": "10", **ADDRESS, **POLICE, "setup_step": step,
        "return_to": f"{base}?view=settings&section={section}"}, follow_redirects=False)


def _walk_to_reporting(host, flat):
    client, base = host["client"], f"/apartments/{flat['id']}/setup"
    for step, action in (("calendar", "skip"), ("guest_links", "done"), ("pin", "done"), ("try", "skip")):
        assert client.post(base, data={"step": step, "action": action}, follow_redirects=False).status_code == 303
    assert _step(client.get(f"/apartments/{flat['id']}?lang=en").text) == "reporting"


# --- server: state, order, refusals ----------------------------------------


def test_create_starts_the_guide_and_existing_properties_get_it_until_set_up(host):
    flat = _create(host)
    assert property_setup.load(flat["id"]) == {"steps": {}, "finished": False, "hidden": False, "legacy": False}
    page = host["client"].get(f"/apartments/{flat['id']}?lang=en").text
    assert _step(page) == "calendar"
    assert f"Step 1 of {TOTAL} · Connect your calendar" in page
    assert "property-first-use" not in page and _t("en", "property_create.created_title") not in page

    # 0100: a property from before the guide gets it while it is not set up,
    # with the steps its record already answers counted as done.
    bare = _legacy(host, "Bare Legacy", police=False)
    assert _step(host["client"].get(f"/apartments/{bare}?lang=en").text) == "calendar"
    no_stays = _legacy(host, "Legacy Without Stays")
    assert _step(host["client"].get(f"/apartments/{no_stays}?lang=en").text) == "calendar"
    # Stays and a guest who registered through the link answer the calendar,
    # guest link, PIN and try-out steps; Automation was chosen long ago.
    in_use = _legacy(host, "Legacy In Use", police=False)
    _add_stay(in_use, guest_by="guest")
    page = host["client"].get(f"/apartments/{in_use}?lang=en").text
    assert _step(page) == "reporting"
    assert f"Step 5 of {TOTAL}" in page
    assert property_setup.load(in_use) is None  # nothing is written by looking

    # A set-up property shows nothing: police details complete and stays on the way.
    done = _legacy(host, "Legacy Set Up")
    _add_stay(done)
    done_page = host["client"].get(f"/apartments/{done}?lang=en").text
    assert _step(done_page) is None
    assert 'class="panel host-setup-complete"' in done_page
    # Archived and switched-off properties never show it.
    archived = _legacy(host, "Legacy Archived", police=False, archived_at=db.utcnow(), active=0)
    assert _step(host["client"].get(f"/apartments/{archived}").text) is None


def test_a_legacy_property_is_set_up_by_saving_its_police_details(host):
    """For a property from before the guide, "set up" is the same bar whether
    or not its state was ever stored: police details and stays. Stay fee and
    Door lock are optional, so they do not hold the guide open."""
    flat_id = _legacy(host, "Legacy Unstored", police=False)
    _add_stay(flat_id, guest_by="guest")
    flat = db.query_one("SELECT * FROM apartment WHERE id = ?", (flat_id,))
    page = host["client"].get(f"/apartments/{flat_id}?lang=en").text
    # Its pages behave as before: Overview with its checklist, saves stay put.
    assert _step(page) == "reporting" and "host-checklist" in page
    assert 'name="setup_step"' not in page
    assert 'class="property-view is-active" data-property-view="overview"' in page
    saved = _police_form(flat, host, "")
    assert saved.headers["location"].startswith(f"/apartments/{flat_id}?view=settings&section=reporting")
    assert _step(host["client"].get(f"/apartments/{flat_id}").text) is None
    # The same property with its state stored (the host had hidden and shown it).
    stored_id = _legacy(host, "Legacy Stored", police=False)
    _add_stay(stored_id, guest_by="guest")
    client = host["client"]
    client.post(f"/apartments/{stored_id}/setup", data={"action": "hide"}, follow_redirects=False)
    client.post(f"/apartments/{stored_id}/setup", data={"action": "show"}, follow_redirects=False)
    assert property_setup.load(stored_id)["legacy"] is True
    _police_form(db.query_one("SELECT * FROM apartment WHERE id = ?", (stored_id,)), host, "")
    assert _step(client.get(f"/apartments/{stored_id}").text) is None
    assert property_setup.load(stored_id)["finished"] is True


def test_steps_answer_only_the_step_on_screen(host):
    flat = _create(host)
    client, base = host["client"], f"/apartments/{flat['id']}"
    # Reporting has no skip; a step that is not on screen cannot be answered.
    for step, action in (("reporting", "skip"), ("reporting", "wait"), ("guest_links", "done"),
                         ("automation", "keep"), ("calendar", "done"), ("try", "demo")):
        response = client.post(f"{base}/setup", data={"step": step, "action": action}, follow_redirects=False)
        assert response.status_code == 303
        assert property_setup.load(flat["id"])["steps"] == {}, (step, action)
    assert demo.demo_stay_for(flat["id"]) is None
    skipped = client.post(f"{base}/setup", data={"step": "calendar", "action": "skip"}, follow_redirects=False)
    assert skipped.headers["location"] == f"{base}?view=overview#property-setup"
    assert property_setup.load(flat["id"])["steps"] == {"calendar": "skipped"}
    assert client.post(f"{base}/setup", data={"step": "guest_links", "action": "skip"}, follow_redirects=False)
    assert "guest_links" not in property_setup.load(flat["id"])["steps"]
    done = client.post(f"{base}/setup", data={"step": "guest_links", "action": "done"}, follow_redirects=False)
    assert done.headers["location"] == f"{base}?view=overview#property-setup"
    assert _step(client.get(f"{base}?lang=en").text) == "pin"
    client.post(f"{base}/setup", data={"step": "pin", "action": "done"}, follow_redirects=False)
    assert _step(client.get(f"{base}?lang=en").text) == "try"
    # "Delete demo stay" only follows a test registration.
    client.post(f"{base}/setup", data={"step": "try", "action": "done"}, follow_redirects=False)
    assert "try" not in property_setup.load(flat["id"])["steps"]
    client.post(f"{base}/setup", data={"step": "try", "action": "demo"}, follow_redirects=False)
    stay = demo.demo_stay_for(flat["id"])
    assert stay and stay["source"] == demo.DEMO_STAY_SOURCE
    client.post(f"{base}/setup", data={"step": "try", "action": "done"}, follow_redirects=False)
    assert "try" not in property_setup.load(flat["id"])["steps"] and demo.demo_stay_for(flat["id"])
    # Skip deletes the demo stay and moves on.
    to_reporting = client.post(f"{base}/setup", data={"step": "try", "action": "skip"}, follow_redirects=False)
    location = to_reporting.headers["location"]
    assert location.startswith(f"{base}?view=settings&section=reporting&") and location.endswith("#ubyport")
    assert "msg=" in location  # "Demo stay deleted."
    assert demo.demo_stay_for(flat["id"]) is None
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
    stranger.post(f"{base}/setup", data={"action": "hide"}, follow_redirects=False)
    assert "fee" not in property_setup.load(flat["id"])["steps"]
    assert property_setup.load(flat["id"])["hidden"] is False


def test_waiting_for_the_police_login_moves_on_but_never_finishes_early(host):
    flat = _create(host)
    client, base = host["client"], f"/apartments/{flat['id']}"
    _walk_to_reporting(host, flat)
    page = client.get(f"{base}?lang=en").text
    assert _t("en", "setup_guide.reporting.wait").replace("'", "&#39;") in page
    waited = client.post(f"{base}/setup", data={"step": "reporting", "action": "wait"}, follow_redirects=False)
    assert waited.headers["location"].startswith(f"{base}?view=settings&section=reporting#stay-fee-settings")
    assert property_setup.load(flat["id"])["steps"]["reporting"] == "waiting"
    for step, action in (("fee", "skip"), ("lock", "skip")):
        page = client.get(f"{base}?lang=en").text
        assert _step(page) == step
        # The put-off step stays on top of the guide, with a way back to it.
        assert "data-setup-waiting" in page and _t("en", "setup_guide.reporting.waiting_item") in page
        assert f'href="{base}?view=settings&amp;section=reporting#ubyport"' in page or \
            f'href="{base}?view=settings&section=reporting#ubyport"' in page
        client.post(f"{base}/setup", data={"step": step, "action": action}, follow_redirects=False)
    assert _step(client.get(f"{base}?lang=en").text) == "automation"
    kept = client.post(f"{base}/setup", data={"step": "automation", "action": "keep"}, follow_redirects=False)
    # Everything else is done, and the guide comes back to the police login
    # instead of saying "Setup complete".
    assert kept.headers["location"].startswith(f"{base}?view=settings&section=reporting#ubyport")
    assert "msg=" not in kept.headers["location"]
    state = property_setup.load(flat["id"])
    assert state["finished"] is False and state["steps"]["reporting"] == "waiting"
    page = client.get(f"{base}?lang=en").text
    assert _step(page) == "reporting" and f"Step 5 of {TOTAL}" in page
    assert _t("en", "property_nav.setup_complete") not in page and "host-setup-complete" not in page
    assert 'value="wait"' not in page  # already waiting: the note stays, the button goes
    assert _t("en", "setup_guide.reporting.wait_deadline") in page
    # Waiting again, or any other answer, changes nothing.
    client.post(f"{base}/setup", data={"step": "reporting", "action": "wait"}, follow_redirects=False)
    client.post(f"{base}/setup", data={"step": "reporting", "action": "done"}, follow_redirects=False)
    assert property_setup.load(flat["id"])["finished"] is False
    # The login arrives: one save finishes the setup, with the flash.
    saved = _police_form(db.query_one("SELECT * FROM apartment WHERE id = ?", (flat["id"],)), host, "reporting")
    assert saved.headers["location"].startswith(f"{base}?view=overview")
    assert "msg=" in saved.headers["location"]
    assert property_setup.load(flat["id"])["finished"] is True
    assert _step(client.get(f"{base}?lang=en").text) is None


def test_hide_and_show_the_guide(host):
    flat = _create(host)
    client, base = host["client"], f"/apartments/{flat['id']}"
    page = client.get(f"{base}?lang=en").text
    assert _t("en", "setup_guide.hide") in page
    hidden = client.post(f"{base}/setup", data={"action": "hide"}, follow_redirects=False)
    assert hidden.headers["location"].startswith(f"{base}?view=overview")
    assert property_setup.load(flat["id"])["hidden"] is True
    page = client.get(f"{base}?lang=en").text
    assert _step(page) is None and 'value="show"' in page
    # A hidden guide never counts as finished, whatever happens meanwhile.
    assert property_setup.load(flat["id"])["finished"] is False
    shown = client.post(f"{base}/setup", data={"action": "show"}, follow_redirects=False)
    assert shown.headers["location"] == f"{base}?view=bookings#calendar-connect"
    assert _step(client.get(f"{base}?lang=en").text) == "calendar"
    # A legacy property can be hidden too (its state is written on the click).
    legacy = _legacy(host, "Legacy Hidden", police=False)
    client.post(f"/apartments/{legacy}/setup", data={"action": "hide"}, follow_redirects=False)
    assert property_setup.load(legacy)["hidden"] is True and property_setup.load(legacy)["legacy"] is True
    assert _step(client.get(f"/apartments/{legacy}").text) is None


def test_a_finished_guide_stays_finished(host):
    flat = _create(host)
    db.set_setting(f"property_setup:{flat['id']}", json.dumps({"steps": {}, "finished": True}))
    assert _step(host["client"].get(f"/apartments/{flat['id']}").text) is None
    db.set_setting(f"property_setup:{flat['id']}", "not json")
    # Unreadable state reads like no state: the property is not set up, so
    # the guide starts again rather than hiding the setup.
    assert _step(host["client"].get(f"/apartments/{flat['id']}").text) == "calendar"


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


def _shot(page, name, width):
    """0100 evidence: every step at 390 and 1280, behind UBYHOST_CAPTURE_0100=1."""
    if CAPTURE and width in (390, 1280):
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


def _check_step(page, lang, number, key, primary, name, width, skip=None, title=None):
    heading = page.locator("#property-setup-title")
    assert heading.is_visible()
    expected = f"{_t(lang, 'setup_guide.count', n=number, total=TOTAL)} · {title or _t(lang, f'setup_guide.{key}.title')}"
    assert heading.inner_text().strip() == expected
    primaries = page.evaluate(_PRIMARIES_JS)
    assert primaries == [primary], (key, primaries)
    skips = page.locator("#property-setup button[value='skip']")
    assert skips.count() == (1 if (skip if skip is not None else key in ("fee", "lock", "try")) else 0), key
    # Hide is always there, and always quiet.
    assert page.locator("#property-setup button[value='hide']").is_visible()
    fit = page.evaluate(_FIT_JS)
    assert fit["scroll"] <= fit["vw"] + 1 and not fit["bad"], (key, fit)
    _shot(page, name, width)


def _fill_police(page):
    for field, value in POLICE.items():
        page.fill(f"#{field}", value)
    page.locator(".host-property-save .btn.primary").click()
    page.wait_for_load_state()


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
    _check_step(page, lang, 1, "calendar", _t(lang, "property_nav.add_calendar"), f"01-calendar-{tag}", width)
    assert page.locator("#calendar-add #url").is_visible()
    assert not page.locator(".property-view.is-active .property-view-head").count()
    assert not page.locator(".property-first-use").count()
    skip_link = page.locator(".property-setup-skip .link-button").first
    assert skip_link.inner_text().strip() == _t(lang, "setup_guide.calendar.skip")
    if lang == "en":
        page.select_option("#label", "airbnb")
        page.fill("#url", "https://www.airbnb.example/calendar/ical/synthetic.ics")
        page.locator("#calendar-add .btn.primary").click()
    else:
        skip_link.click()
    page.wait_for_load_state()

    # 2. This is your guest link: the ready message, one Copy, one Done.
    flat = db.query_one("SELECT * FROM apartment WHERE id = ?", (flat["id"],))
    _check_step(page, lang, 2, "guest_links", _t(lang, "setup_guide.guest_links.done"), f"02-guest-link-{tag}", width)
    snippet = page.locator("#setup-guest-snippet").input_value()
    link_key = guest_slug.current(flat["id"])
    assert snippet == _t(lang, "setup_guide.guest_links.snippet", url=f"{config.PUBLIC_BASE_URL}/l/{link_key}", pin=flat["permalink_pin"])
    assert page.locator(".property-setup-text").inner_text().strip() == _t(lang, "setup_guide.guest_links.text")
    copy = page.locator("#property-setup [data-copy='setup-guest-snippet']")
    assert copy.inner_text().strip() == _t(lang, "setup_guide.guest_links.copy")
    if js:
        copy.click()
        assert page.evaluate("() => navigator.clipboard.readText()") == snippet
    page.locator("#property-setup .btn.primary").click()
    page.wait_for_load_state()

    # 3. This is your PIN: why guests need it, the PIN itself, the same snippet.
    _check_step(page, lang, 3, "pin", _t(lang, "setup_guide.pin.done"), f"03-pin-{tag}", width)
    assert page.locator("[data-setup-pin]").inner_text().strip() == flat["permalink_pin"]
    assert page.locator("#setup-guest-snippet").input_value() == snippet
    assert page.locator(".property-setup-text").inner_text().strip() == _t(lang, "setup_guide.pin.text")
    page.locator("#property-setup .btn.primary").click()
    page.wait_for_load_state()

    # 4. Try it out: make a demo stay, open the guest form as a guest would.
    _check_step(page, lang, 4, "try", _t(lang, "setup_guide.try.create"), f"04-try-{tag}", width)
    page.locator("#property-setup .btn.primary").click()
    page.wait_for_load_state()
    stay = demo.demo_stay_for(flat["id"])
    assert stay and stay["source"] == "demo"
    _check_step(page, lang, 4, "try", _t(lang, "setup_guide.try.open"), f"05-try-open-{tag}", width)
    form_link = page.locator("[data-setup-demo-form]")
    assert form_link.get_attribute("target") == "_blank"
    assert form_link.get_attribute("href") == f"/l/{link_key}/{stay['id']}?lang={lang}"
    if js:
        with page.context.expect_page() as opened:
            form_link.click()
        guest_page = opened.value
        guest_page.wait_for_load_state()
        assert f"/l/{link_key}/{stay['id']}/new" in guest_page.url
        guest = Guest(guest_page, width, lang)
        guest.fill_form(1, 1, FAKE_GUEST)
        _shot(guest_page, f"06-guest-form-sent-{tag}", width)
        guest_page.close()
    else:
        # The guest form itself needs JavaScript (signature pad); the no-JS
        # host path is the guide around it, so the test registration is typed in.
        _add_guest = db.insert("guest", {
            "reservation_id": stay["id"], "surname": FAKE_GUEST[1], "first_name": FAKE_GUEST[0],
            "birth_date": FAKE_GUEST[2], "nationality": "DEU", "doc_number": FAKE_GUEST[3],
            "res_street": "Street 1", "res_city": "Berlin", "res_country": "DEU", "purpose": "10",
            "is_lead": 1, "entered_by": "guest", "signature_png": SIGNATURE, "signed_at": db.utcnow(),
            "submit_state": reporting.PENDING, "created_at": db.utcnow(), "updated_at": db.utcnow()})
        assert _add_guest
    page.locator(".property-setup-quiet").click()  # "I've sent the form"
    page.wait_for_load_state()

    # "This is what you see when a guest registers": status and guests.
    _check_step(page, lang, 4, "try", _t(lang, "setup_guide.try.delete"), f"07-try-registered-{tag}", width,
                skip=False, title=_t(lang, "setup_guide.try.registered_title"))
    shown = page.locator("[data-setup-demo]")
    assert _t(lang, "status.demo_preview") in shown.inner_text()
    stay_link = shown.locator("a").first
    assert stay_link.inner_text().strip() == _t(lang, "setup_guide.try.open_stay")
    # The stay page: marked as a demo, Preview only, nothing to send.
    guide_url = page.url
    stay_link.click()
    page.wait_for_load_state()
    assert page.locator("#demo-stay").is_visible()
    assert _t(lang, "status.demo_preview") in page.locator("#now").inner_text() or \
        _t(lang, "status.demo_preview") in page.content()
    assert not page.locator(f"form[action='/reservations/{stay['id']}/submit']").count()
    assert FAKE_GUEST[1].upper() in page.content().upper()
    _shot(page, f"08-demo-stay-page-{tag}", width)
    page.goto(guide_url)
    page.locator("#property-setup .btn.primary").click()  # Delete demo stay
    page.wait_for_load_state()
    assert demo.demo_stay_for(flat["id"]) is None
    assert not db.query_one("SELECT 1 AS n FROM reservation WHERE id = ?", (stay["id"],))

    # 5. Police reporting: Save is the primary; the quiet "still waiting" path.
    _check_step(page, lang, 5, "reporting", _t(lang, "common.save_changes"), f"09-reporting-{tag}", width)
    assert page.locator("#ubyport").is_visible()
    wait = page.locator("#property-setup button[value='wait']")
    assert wait.is_visible() and wait.inner_text().strip() == _t(lang, "setup_guide.reporting.wait")
    note = page.locator("#setup-waiting-note").inner_text()
    assert _t(lang, "setup_guide.reporting.wait_then_manual") in note  # a new property starts on manual
    assert page.locator("#property-setup a[href='/guide#manual-filing']").is_visible()
    waiting = lang == "cs"
    if waiting:
        wait.click()
        page.wait_for_load_state()
    else:
        _fill_police(page)

    # 6. Stay fee (optional): Skip. 7. Door lock (optional): Skip.
    for number, key, shot in ((6, "fee", "10-fee"), (7, "lock", "11-lock")):
        _check_step(page, lang, number, key, _t(lang, "common.save_changes"), f"{shot}-{tag}", width)
        assert page.locator("[data-setup-waiting]").count() == (1 if waiting else 0)
        if key == "lock":
            assert page.locator('[data-settings-group="lock"] #door-code').is_visible()
            assert page.locator('[data-property-section-link="lock"][aria-current]').is_visible()
        page.locator("#property-setup button[value='skip']").click()
        page.wait_for_load_state()

    # 8. Automation: Save once (EN) or keep manual sending (CS).
    _check_step(page, lang, 8, "automation", _t(lang, "common.save_changes"), f"12-automation-{tag}", width)
    assert page.locator("#automation").is_visible()
    keep = page.locator("#property-setup button[value='keep']")
    assert keep.inner_text().strip() == _t(lang, "setup_guide.automation.keep_manual")
    if lang == "en":
        page.locator(".host-property-save .btn.primary").click()
    else:
        keep.click()
    page.wait_for_load_state()

    if waiting:
        # Back at the police login, still unfinished: never "Setup complete".
        _check_step(page, lang, 5, "reporting", _t(lang, "common.save_changes"), f"13-reporting-waiting-{tag}", width)
        assert page.locator("#property-setup .pill.amber").inner_text().strip() == _t(lang, "setup_guide.reporting.waiting_item")
        assert not page.locator("#property-setup button[value='wait']").count()
        assert not page.locator(".host-setup-complete").count()
        assert _t(lang, "flash.setup.complete") not in page.content()
        assert property_setup.load(flat["id"])["finished"] is False
        _fill_police(page)

    # Done: one compact status, no guide.
    assert "view=overview" in page.url
    assert not page.locator("#property-setup").count()
    assert page.locator(".host-setup-complete").is_visible()
    assert not page.locator(".host-checklist").count()
    assert property_setup.load(flat["id"])["finished"] is True
    marks = property_setup.load(flat["id"])["steps"]
    assert marks == {**({"calendar": "skipped", "reporting": "waiting"} if lang == "cs" else {}),
                     "guest_links": "done", "pin": "done", "try": "done",
                     "fee": "skipped", "lock": "skipped", "automation": "done"}
    _shot(page, f"14-complete-{tag}", width)
    return flat


_WIDTHS = [1280, 360] + ([390] if CAPTURE else [])


@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("width", _WIDTHS)
def test_beginner_journey_in_browser(host, base, lang, width):
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


def test_hide_and_show_in_browser(host, base):
    legacy = _legacy(host, "Synthetic Legacy Browser", police=False)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        page = _context(browser, base, host, width=360).new_page()
        page.goto(f"{base}/apartments/{legacy}?lang=en")
        assert page.locator("#property-setup").is_visible()
        page.locator("#property-setup button[value='hide']").click()
        page.wait_for_load_state()
        assert not page.locator("#property-setup").count()
        show = page.locator(".property-setup-show button[value='show']")
        assert show.is_visible() and show.inner_text().strip() == _t("en", "setup_guide.show")
        show.click()
        page.wait_for_load_state()
        assert page.locator("#property-setup").is_visible()
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


def test_beginner_journey_without_javascript(host, base):
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
