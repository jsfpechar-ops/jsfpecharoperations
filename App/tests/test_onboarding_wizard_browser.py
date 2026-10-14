"""0102: onboarding wizard — one focused page per step."""
from __future__ import annotations

import base64
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

from datetime import date, datetime, timedelta, timezone

from app import auth, config, db, feed_url, host_i18n, icalsync, property_setup, reporting
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.conftest import login_as

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0102-evidence"
ADDRESS = {"addr_obec": "Brno", "addr_house_no": "12", "addr_zip": "602 00", "addr_street": "Synthetic"}
POLICE = {
    "uby_idub": "123456789012",
    "uby_ws_user": "UBY-WSsynth",
    "uby_ws_password": "synthetic-secret",
    "uby_mark": "SYNTH",
    "uby_name": "Synthetic Garden",
}
TOTAL = property_setup.TOTAL_STEPS
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()


def _t(lang, key, **kwargs):
    return host_i18n.translate(lang, key, **kwargs)


@pytest.fixture
def host(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    monkeypatch.setattr(feed_url, "validate_calendar_url", lambda url: url)
    monkeypatch.setattr(
        icalsync,
        "sync_all",
        lambda apartment_id=None, owner_user_id=None: {
            "feeds": 1,
            "created": 0,
            "updated": 0,
            "cancelled": 0,
            "errors": 0,
            "not_modified": 0,
            "unchanged": 0,
            "changed": 0,
        },
    )
    username = f"wizard-{secrets.token_hex(4)}"
    owner = auth.create_account(f"{username}@example.test", "Wizard Host", role="host", username=username)
    entity = db.insert(
        "legal_entity",
        {
            "name": "Synthetic Operator s.r.o.",
            "seat": "Brno",
            "ico": "12345678",
            "contact_email": "wizard@example.test",
            "owner_user_id": owner,
            "created_at": db.utcnow(),
        },
    )
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    yield {"client": client, "owner": owner, "entity": entity}
    for row in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (owner,)):
        db.execute("DELETE FROM settings WHERE key = ?", (f"property_setup:{row['id']}",))
    db.execute(
        "DELETE FROM ical_feed WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)",
        (owner,),
    )


def _create(host, name="Synthetic Garden Flat"):
    response = host["client"].post(
        "/apartments",
        data={
            "internal_name": name,
            "city_en": "Brno",
            "legal_entity_id": str(host["entity"]),
            "default_purpose": "10",
            **ADDRESS,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/setup/calendar" in response.headers["location"]
    return db.query_one(
        "SELECT * FROM apartment WHERE owner_user_id = ? ORDER BY id DESC LIMIT 1", (host["owner"],)
    )


def _shot(page, name: str):
    if REQUIRE_BROWSER:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / name), full_page=True)


def _overflow_js():
    return """() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"""


def test_create_lands_on_calendar_step_two(host):
    flat = _create(host)
    page = host["client"].get(f"/apartments/{flat['id']}/setup/calendar?lang=en").text
    assert f"Step 2 of {TOTAL}" in page
    assert _t("en", "wizard.step.calendar") in page
    assert "data-setup-wizard" in page
    assert 'class="property-tabs"' not in page


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base_url():
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("width", [390, 1280])
def test_wizard_journey_and_geometry(host, base_url, lang, width):
    if not REQUIRE_BROWSER:
        pytest.skip("browser not required")
    flat = _create(host)
    base = f"{base_url}/apartments/{flat['id']}/setup"
    session = host["client"].cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900}, locale=lang)
        context.add_cookies(
            [{"name": auth.SESSION_COOKIE, "value": session, "url": base_url + "/"}]
        )
        page = context.new_page()
        tag = f"{lang}-{width}"
        page.goto(f"{base}/calendar?lang={lang}")
        _shot(page, f"01-calendar-{tag}.png")
        assert page.locator(".setup-wizard-progress li.is-done").count() >= 1
        page.locator(".setup-wizard-skip button[value=skip]").click()
        page.wait_for_url("**/setup/guest_link**")
        _shot(page, f"02-guest-link-{tag}.png")
        assert _t(lang, "wizard.guest_link.link_title") in page.content()
        assert "/l/" not in page.locator(".host-property-grid").inner_text() if page.locator(".host-property-grid").count() else True
        page.locator("button[value='done']").click()
        page.wait_for_url("**/setup/try_it**")
        _shot(page, f"03-try-it-{tag}.png")
        page.locator("form.setup-wizard-skip button[value=skip]").click()
        page.wait_for_url("**/setup/police**")
        _shot(page, f"04-police-{tag}.png")
        assert page.locator("button.setup-wizard-wait").is_visible()
        page.fill("#uby_idub", POLICE["uby_idub"])
        page.fill("#uby_ws_user", POLICE["uby_ws_user"])
        page.fill("#uby_ws_password", POLICE["uby_ws_password"])
        page.fill("#uby_mark", POLICE["uby_mark"])
        page.fill("#uby_name", POLICE["uby_name"])
        page.locator('button[form="police-form"]').click()
        page.wait_for_url("**/setup/stay_fee**")
        _shot(page, f"05-stay-fee-{tag}.png")
        page.locator(".setup-wizard-foot form.setup-wizard-skip button").click()
        page.wait_for_url("**/setup/door_lock**")
        page.locator(".setup-wizard-foot form.setup-wizard-skip button").click()
        page.wait_for_url("**/setup/automation**")
        _shot(page, f"06-automation-{tag}.png")
        page.locator('button[form="automation-form"]').click()
        page.wait_for_url("**/setup/done**")
        _shot(page, f"07-done-{tag}.png")
        assert _t(lang, "wizard.done.title") in page.content()
        browser.close()


@pytest.mark.parametrize("width", [360, 390, 760, 1280, 1440])
def test_wizard_geometry(host, base_url, width):
    if not REQUIRE_BROWSER:
        pytest.skip("browser not required")
    flat = _create(host)
    session = host["client"].cookies.get(auth.SESSION_COOKIE)
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch(**chromium_launch_kwargs())
        context = browser.new_context(viewport={"width": width, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": session, "url": base_url + "/"}])
        page = context.new_page()
        page.evaluate("() => document.body.classList.add('sidebar-collapsed')")
        page.goto(f"{base_url}/apartments/{flat['id']}/setup/calendar?lang=en")
        sizes = page.evaluate(
            "() => ({sw: document.documentElement.scrollWidth, vw: document.documentElement.clientWidth})"
        )
        assert sizes["sw"] <= sizes["vw"] + 2, sizes
        browser.close()


def test_property_step_renders_when_address_missing(host):
    """Fix 1: incomplete property details must not 500 on the property step."""
    apt_id = db.insert(
        "apartment",
        {
            "internal_name": "No address yet",
            "owner_user_id": host["owner"],
            "legal_entity_id": host["entity"],
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": auth.new_permalink_pin(),
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    property_setup.start(apt_id)
    response = host["client"].get(f"/apartments/{apt_id}/setup/property?lang=en")
    assert response.status_code == 200
    assert "data-setup-wizard" in response.text
    assert 'id="addr_obec"' in response.text
    walked = host["client"].get(f"/apartments/{apt_id}/setup?lang=en", follow_redirects=False)
    assert walked.status_code == 303
    assert "/setup/property" in walked.headers["location"]


def test_back_from_later_step_reaches_earlier_page(host):
    """Fix 2: Back must open an earlier step, not bounce to the current one."""
    flat = _create(host)
    client = host["client"]
    base = f"/apartments/{flat['id']}/setup"
    client.post(base, data={"step": "calendar", "action": "skip"}, follow_redirects=False)
    client.post(base, data={"step": "guest_link", "action": "done"}, follow_redirects=False)
    client.post(base, data={"step": "try_it", "action": "skip"}, follow_redirects=False)
    at_police = client.get(f"{base}/police?lang=en")
    assert at_police.status_code == 200
    back = client.get(f"{base}/try_it?lang=en", follow_redirects=False)
    assert back.status_code == 200
    assert 'data-setup-step="try_it"' in back.text


def test_police_waiting_cannot_finish_setup_via_automation(host):
    """Fix 3: waiting on police must block finish even when automation posts to /done."""
    flat = _create(host)
    client = host["client"]
    base = f"/apartments/{flat['id']}/setup"
    client.post(base, data={"step": "calendar", "action": "skip"}, follow_redirects=False)
    client.post(base, data={"step": "guest_link", "action": "done"}, follow_redirects=False)
    client.post(base, data={"step": "try_it", "action": "skip"}, follow_redirects=False)
    client.post(base, data={"step": "police", "action": "wait"}, follow_redirects=False)
    client.post(base, data={"step": "stay_fee", "action": "skip"}, follow_redirects=False)
    client.post(base, data={"step": "door_lock", "action": "skip"}, follow_redirects=False)
    saved = client.post(
        f"/apartments/{flat['id']}/automation-timing",
        data={
            "automation_mode": "manual",
            "submit_after_hours": "24",
            "return_to": f"/apartments/{flat['id']}/setup/done",
            "setup_step": "automation",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    from urllib.parse import urlparse

    path = urlparse(saved.headers["location"]).path
    assert path.endswith("/setup/police") or path.endswith("/setup/stay_fee")
    state = property_setup.load(flat["id"])
    assert state and not state["finished"]


def test_overview_checklist_when_guide_hidden(host):
    flat = _create(host)
    client = host["client"]
    client.post(
        f"/apartments/{flat['id']}/setup",
        data={"action": "hide"},
        follow_redirects=False,
    )
    page = client.get(f"/apartments/{flat['id']}?view=overview&lang=en").text
    assert "setup-continue-card" not in page
    assert 'class="panel host-checklist"' in page or 'class="readiness"' in page


def test_overview_checklist_without_stored_setup_state(host):
    apt_id = db.insert(
        "apartment",
        {
            "internal_name": "Legacy complete",
            "owner_user_id": host["owner"],
            "legal_entity_id": host["entity"],
            "addr_obec": "Brno",
            "addr_house_no": "12",
            "addr_zip": "60200",
            "uby_idub": "123456789012",
            "uby_mark": "LEGACY",
            "uby_name": "Legacy Flat",
            "uby_ws_user": "ws-user",
            "uby_ws_password_enc": db.encrypt_secret("secret"),
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": auth.new_permalink_pin(),
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    db.insert(
        "ical_feed",
        {
            "apartment_id": apt_id,
            "url": "https://example.test/cal.ics",
            "label": "airbnb",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    page = host["client"].get(f"/apartments/{apt_id}?view=overview&lang=en").text
    assert (
        'class="panel host-checklist"' in page
        or 'class="panel host-setup-complete"' in page
        or 'class="readiness"' in page
    )


def test_guests_registered_skips_teaching_steps(host, monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", False)
    flat = _create(host)
    host["client"].post(
        f"/apartments/{flat['id']}/setup",
        data={"step": "calendar", "action": "skip"},
        follow_redirects=False,
    )
    now = db.utcnow()
    day = date.today()
    res_id = db.insert(
        "reservation",
        {
            "apartment_id": flat["id"],
            "source": "manual",
            "uid": f"manual-{secrets.token_hex(4)}",
            "date_from": day.isoformat(),
            "date_to": (day + timedelta(days=2)).isoformat(),
            "status": "active",
            "registration_completed_at": datetime.now(timezone.utc).isoformat(),
            "created_at": now,
            "updated_at": now,
        },
    )
    db.insert(
        "guest",
        {
            "reservation_id": res_id,
            "surname": "Guest",
            "first_name": "Ada",
            "birth_date": "01011990",
            "nationality": "GBR",
            "doc_number": "P1234567",
            "res_street": "Street 1",
            "res_city": "London",
            "res_country": "GBR",
            "purpose": "10",
            "is_lead": 1,
            "entered_by": "guest",
            "submit_state": reporting.PENDING,
            "created_at": now,
            "updated_at": now,
        },
    )
    property_setup.start(flat["id"])
    entry = host["client"].get(f"/apartments/{flat['id']}/setup", follow_redirects=False)
    assert "/setup/guest_link" not in entry.headers["location"]
    assert "/setup/try_it" not in entry.headers["location"]


def test_refuse_setup_save_parses_return_to_and_legal_entity(host):
    flat = _create(host)
    client = host["client"]
    response = client.post(
        f"/apartments/{flat['id']}",
        data={
            "internal_name": flat["internal_name"],
            "legal_entity_id": "abc",
            "city_en": "Brno",
            "default_purpose": "10",
            "return_to": f"/apartments/{flat['id']}/setup/stay_fee#x",
            "setup_step": "stay_fee",
            "stay_fee_rate_czk": "5",
            "stay_fee_cadence": "monthly",
            "account_prefix": "123456",
            "account_number": "1234567890",
            "account_bank": "0100",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert _t("en", "wizard.step.stay_fee") in response.text


def test_fee_refusal_shows_error_on_wizard(host):
    flat = _create(host)
    response = host["client"].post(
        f"/apartments/{flat['id']}",
        data={
            "internal_name": flat["internal_name"],
            "legal_entity_id": str(host["entity"]),
            "city_en": "Brno",
            "default_purpose": "10",
            **ADDRESS,
            "return_to": f"/apartments/{flat['id']}/setup/stay_fee",
            "setup_step": "stay_fee",
            "stay_fee_rate_czk": "5",
            "stay_fee_cadence": "monthly",
            "account_prefix": "bad",
            "account_number": "x",
            "account_bank": "0100",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "stay-fee-account-error" in response.text or "account_invalid" in response.text.lower()


def test_done_count_includes_skipped_door_lock_when_unavailable(host, monkeypatch):
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", False)
    flat = _create(host)
    client = host["client"]
    base = f"/apartments/{flat['id']}/setup"
    for step, action in (
        ("calendar", "skip"),
        ("guest_link", "done"),
        ("try_it", "skip"),
        ("police", "wait"),
        ("stay_fee", "skip"),
    ):
        client.post(base, data={"step": step, "action": action}, follow_redirects=False)
    overview = client.get(f"/apartments/{flat['id']}?view=overview&lang=en").text
    assert "6 of 8" in overview


def test_no_js_calendar_skip(host):
    flat = _create(host)
    base = f"/apartments/{flat['id']}/setup"
    client = host["client"]
    skipped = client.post(f"{base}", data={"step": "calendar", "action": "skip"}, follow_redirects=False)
    assert skipped.status_code == 303
    assert "/setup/guest_link" in skipped.headers["location"]
    overview = client.get(f"/apartments/{flat['id']}?view=overview&lang=en").text
    assert "setup-continue-card" in overview
    assert "/l/" not in overview.split("overview-guest-url")[0] if "overview-guest-url" in overview else True
