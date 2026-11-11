"""1099: the short property editor in a real browser (390, 768, 1280; with and without JavaScript)."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest

from app import auth, property_setup
from app.main import app
from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.test_first_setup_open_section import PASSWORD_TYPED, _apt, _basics, _police, fake, host  # noqa: F401

if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

WIDTHS = [390, 768, 1280]
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-1099"
TEST_BUTTON = 'button[formaction$="/test-connection"]'
SAVE_BUTTON = '.savebar button[form="property-settings-form"]'


@pytest.fixture
def live(host):  # noqa: F811
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started
    base = f"http://127.0.0.1:{port}"

    class Live:
        client = host
        url = f"{base}/apartments/{_apt()['id']}?view=settings"

        def open(self, width, js=True):
            context = browser.new_context(viewport={"width": width, "height": 900}, java_script_enabled=js)
            context.add_cookies(
                [{"name": auth.SESSION_COOKIE, "value": host.cookies.get(auth.SESSION_COOKIE), "url": base + "/"}]
            )
            return context.new_page()

    try:
        with sync_api.sync_playwright() as playwright:
            browser = playwright.chromium.launch(**chromium_launch_kwargs())
            yield Live()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _shot(page, name, width):
    SHOTS.mkdir(parents=True, exist_ok=True)
    settle_motion(page)
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS / f"{name}-{width}.png"), full_page=True)


def _state(page):
    return page.evaluate(
        """() => ({
          open: [...document.querySelectorAll('details.prop-sec')].filter(d => d.open).map(d => d.id),
          visible: [...document.querySelectorAll('details.prop-sec')]
            .filter(d => d.getBoundingClientRect().height > 0 && getComputedStyle(d).display !== 'none').map(d => d.id),
          fits: document.documentElement.scrollWidth <= window.innerWidth,
          summaries: [...document.querySelectorAll('details.prop-sec > summary')].map(s => s.getBoundingClientRect().height),
          states: [...document.querySelectorAll('details.prop-sec .sec-state')].map(s => s.textContent.trim()),
        })"""
    )


def _save_police(live):
    response = live.client.post(f"/apartments/{_apt()['id']}", data=_police(), follow_redirects=False)
    assert response.status_code == 303


@pytest.mark.parametrize("width", WIDTHS)
def test_new_property(live, width):
    page = live.open(width)
    page.goto(live.url)
    state = _state(page)
    assert state["open"] == ["sec-police"], state
    assert state["fits"]
    if width < 768:
        assert all(h >= 44 for h in state["summaries"]), state
        assert any("min" in text for text in state["states"])
    else:
        assert state["visible"] == ["sec-police"], state
    # The letter comes first: the picture sits above any "Missing" list in the police section.
    order = page.evaluate(
        """() => ({
          figure: document.querySelector('#sec-police details.police-letter-find').getBoundingClientRect().top,
          missing: [...document.querySelectorAll('#sec-police .prop-sec-missing')]
            .filter(el => el.getBoundingClientRect().height > 0).map(el => el.getBoundingClientRect().top),
        })"""
    )
    assert all(order["figure"] < top for top in order["missing"]), order
    _shot(page, "new", width)


@pytest.mark.parametrize("width", WIDTHS)
def test_mid_setup(live, fake, width):  # noqa: F811
    _save_police(live)
    page = live.open(width)
    page.goto(live.url)
    state = _state(page)
    assert state["open"] == ["sec-police"] and state["fits"], state
    assert page.locator("#sec-police .sec-state").text_content().startswith("Saved, not tested yet")
    _shot(page, "mid", width)


@pytest.mark.parametrize("width", WIDTHS)
def test_ready_card(live, fake, width):  # noqa: F811
    _save_police(live)
    property_setup.mark_tested(_apt()["id"])
    page = live.open(width)
    page.goto(live.url)
    assert page.locator("[data-ready-card]").count() == 1
    box = page.evaluate(
        """() => {
          const r = (s) => document.querySelector(s).getBoundingClientRect();
          const img = document.querySelector('.ready-card-qr');
          return {card: r('[data-ready-card]'), qr: r('.ready-card-qr'), natural: img.naturalWidth,
                  copy: r('.ready-card-copy'), vw: window.innerWidth,
                  fits: document.documentElement.scrollWidth <= window.innerWidth};
        }"""
    )
    assert box["fits"] and box["natural"] >= 120, box
    assert box["qr"]["width"] >= 120 and box["qr"]["right"] <= box["vw"], box
    assert box["qr"]["left"] >= box["card"]["left"] and box["qr"]["right"] <= box["card"]["right"], box
    qr, copy = box["qr"], box["copy"]
    beside = copy["left"] >= qr["right"] + 12 - 0.5
    below = copy["top"] >= qr["bottom"] + 12 - 0.5
    assert beside or below, box
    assert page.locator(".ready-card-link").is_visible() and page.locator(".ready-card-pin").is_visible()
    card = page.evaluate(
        """() => {
          const c = getComputedStyle(document.querySelector('[data-ready-card]'));
          return {bg: c.backgroundColor, border: c.borderTopWidth,
                  primary: document.querySelectorAll('[data-ready-card] .ui-btn-primary, [data-ready-card] .btn').length};
        }"""
    )
    assert card["primary"] == 0, card
    if width >= 768:  # ui-section-card is a bordered card from 768 px; flat on the phone, like the other section cards
        assert card["bg"] == "rgb(255, 255, 255)" and card["border"] == "1px", card
    # At 768 and up the tabs show one section (app.js opens it); the phone accordion stays closed.
    assert _state(page)["open"] == ([] if width < 768 else ["sec-basics"])
    _shot(page, "ready", width)


@pytest.mark.parametrize("width", WIDTHS)
def test_later_edit(live, fake, width):  # noqa: F811
    _save_police(live)
    property_setup.finish(_apt()["id"])
    page = live.open(width)
    page.goto(live.url)
    state = _state(page)
    assert state["fits"], state
    if width < 768:
        assert state["open"] == [], state
    else:
        assert state["visible"] == ["sec-basics"], state
    _shot(page, "edit", width)


def test_js_save_of_basics_opens_police(live):
    page = live.open(390)
    page.goto(live.url)
    page.locator("#sec-basics > summary").click()
    page.fill("#internal_name", "Short Flat Renamed")
    with page.expect_navigation():
        page.locator(SAVE_BUTTON).click()
    page.wait_for_load_state()
    assert "saved=1" in page.url
    state = _state(page)
    assert "sec-police" in state["open"] and "sec-basics" not in state["open"], (page.url, state)


@pytest.mark.parametrize("width", [390, 1280])
def test_no_javascript_flow(live, fake, width):  # noqa: F811
    page = live.open(width, js=False)
    page.goto(live.url)
    assert _state(page)["open"] == ["sec-police"]
    assert page.locator("#sec-police .help-tip, #sec-police [aria-describedby], #sec-police .tip").count() > 0
    data = _police()
    for name in ("uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user", "uby_ws_password"):
        page.fill(f"#{name}", data[name])
    with page.expect_navigation():
        page.locator(TEST_BUTTON).click()
    page.wait_for_load_state()
    assert page.locator("[data-ready-card]").count() == 1, page.url
    for sel in (".ready-card-link", ".ready-card-pin", ".ready-card-qr"):
        assert page.locator(sel).is_visible(), sel
    assert PASSWORD_TYPED not in page.content()
