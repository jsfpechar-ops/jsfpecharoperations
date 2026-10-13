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

from app import auth, config, db, feed_url, host_i18n, icalsync, property_setup
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
        page.locator("button.setup-wizard-wait").click()
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
        assert _t(lang, "setup_guide.reporting.waiting_item") in page.content()
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
