"""0314: Havel's confirm cards in a real browser at 390 and 1280 (rule 7)."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import ai, auth, config
from app.main import app
from tests.ai_fake import FakeClient
from tests.browser_support import chromium_launch_kwargs
from tests.test_havel_actions import LATER, SOON, _action, _reply, ready  # noqa: F401
from tests.test_submission_retry_cap import host as host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0314"


@pytest.fixture
def origin(ready, monkeypatch):  # noqa: F811
    host, pid = ready
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(.05)
    assert server.started
    yield f"http://127.0.0.1:{port}", host.cookies.get(auth.SESSION_COOKIE), pid
    server.should_exit = True
    thread.join(timeout=5)
    ai.set_client_for_tests(None)


def _context(playwright, origin, width, js=True):
    try:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for the Havel card browser test")
    context = browser.new_context(viewport={"width": width, "height": 900}, java_script_enabled=js)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": origin[1], "url": origin[0] + "/"}])
    return browser, context


def test_cards_at_390_and_1280(origin):
    url, _cookie, pid = origin
    stay = _reply(_action(property_id=pid, date_from=SOON, date_to=LATER))
    SHOTS.mkdir(parents=True, exist_ok=True)
    for width in (390, 1280):
        ai.set_client_for_tests(FakeClient([stay]))
        with sync_api.sync_playwright() as pw:
            browser, context = _context(pw, origin, width)
            page = context.new_page()
            page.goto(url + "/havel?lang=en")
            page.fill("#havel-message", "Add a stay from Friday to Sunday for 3 guests")
            page.keyboard.press("Enter")
            page.locator("[data-havel-card='create_stay']").wait_for()
            card = page.locator("[data-havel-card='create_stay']")
            assert card.locator("form[action='/reservations'] input[name='_csrf']").count() == 1
            assert not card.locator("input[name='date_from']").is_visible()
            card.locator("summary").click()
            assert card.locator("input[name='date_from']").is_visible()
            assert page.evaluate("document.documentElement.scrollWidth") <= width
            page.screenshot(path=str(SHOTS / f"card-stay-{width}.png"), full_page=True)
            card.locator("[data-havel-cancel]").click()
            assert page.locator("[data-havel-card='create_stay']").count() == 0
            assert page.evaluate("document.activeElement.id") == "havel-message"
            browser.close()


def test_pin_card_confirm_lands_on_the_guest_links_card(origin):
    url, _cookie, pid = origin
    ai.set_client_for_tests(FakeClient([_reply(_action(type="new_pin", property_id=pid))]))
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(url + "/havel?lang=en")
        page.fill("#havel-message", "Make a new PIN")
        page.keyboard.press("Enter")
        page.locator("[data-havel-card='new_pin']").wait_for()
        assert page.locator("[data-havel-card='new_pin'] .ui-btn-danger").count() == 1
        page.screenshot(path=str(SHOTS / "card-pin-390.png"))
        page.locator("[data-havel-card='new_pin'] .ui-btn-danger").click()
        page.wait_for_url("**/apartments/*view=settings*section=guests*")
        browser.close()
