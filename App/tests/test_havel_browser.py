"""0324: the Havel panel in a real browser at 1280 and 390 (rule 7)."""
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

from app import ai, auth, config, db
from app.main import app
from tests.ai_fake import FakeClient, reply
from tests.browser_support import chromium_launch_kwargs
from tests.test_submission_retry_cap import host as host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0324"
ANSWER = {"kind": "answer", "reply": "Open Stays.\n1. Tap Add stay.\n2. Pick the dates.", "sources": ["guide.stays.body"],
          "links": [{"page": "add_stay", "property_id": None}], "action": None, "support_summary": None}


@pytest.fixture
def origin(host, monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"havel"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "k")
    ai.set_client_for_tests(FakeClient([reply(ANSWER), reply(ANSWER), reply(ANSWER)]))
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
    yield f"http://127.0.0.1:{port}", host.cookies.get(auth.SESSION_COOKIE)
    server.should_exit = True
    thread.join(timeout=5)
    ai.set_client_for_tests(None)


def _context(playwright, origin, width, js=True):
    try:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for the Havel browser test")
    context = browser.new_context(viewport={"width": width, "height": 900}, java_script_enabled=js)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": origin[1], "url": origin[0] + "/"}])
    return browser, context


def test_computer_panel_topics_handoff_and_answer(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 1280)
        page = context.new_page()
        page.goto(origin[0] + "/")
        launcher = page.locator("#app-sidebar [data-havel-launcher]")
        assert launcher.is_visible()
        launcher.click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        assert dialog.locator("[data-havel-topic-link]").count() == 5
        assert dialog.locator("h2#havel-title").inner_text().strip() == "Havel (AI)"
        box = dialog.locator(".ui-sheet").bounding_box()
        assert box["width"] <= 400 and box["height"] <= 680
        dialog.locator("[data-havel-topic-link]", has_text="stay").first.click()
        dialog.locator("[data-havel-topic-link][href*='q=cancelled']").wait_for()
        dialog.locator("[data-havel-topic-link][href*='q=cancelled']").click()
        dialog.locator("[data-havel-ask]").wait_for()
        page.screenshot(path=str(SHOTS / "panel-topic-1280.png"))
        dialog.locator("[data-havel-ask]").click()
        assert page.evaluate("document.activeElement.id") == "havel-message"
        assert dialog.locator("[data-havel-topic]").input_value() == "stays"
        hosts_before = dialog.locator(".havel-msg-host").count()
        page.keyboard.type("And if the guest never arrives?")
        page.keyboard.press("Enter")
        dialog.locator(".havel-msg-havel:not([data-havel-writing])").last.wait_for()
        assert dialog.locator(".havel-msg-host").count() == hosts_before + 1
        assert dialog.locator(".havel-bubble ol li").count() == 2
        assert page.evaluate("document.activeElement.className").startswith("havel-msg havel-msg-havel")
        assert dialog.locator("[data-havel-topics]").count() == 0
        page.screenshot(path=str(SHOTS / "panel-answer-1280.png"))
        page.keyboard.press("Escape")
        assert page.locator("#havel-sheet[open]").count() == 0
        browser.close()


def test_phone_launcher_and_sheet(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        topbar = page.locator(".ui-topbar [data-havel-launcher]")
        assert topbar.is_visible()
        tb = topbar.bounding_box()
        assert tb["width"] >= 44 and tb["height"] >= 44
        topbar.click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        sheet = dialog.locator(".ui-sheet").bounding_box()
        assert sheet["width"] == 390 and sheet["height"] <= 900 * 0.92 + 1
        assert dialog.locator("[data-havel-device]").input_value() == "phone"
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        page.screenshot(path=str(SHOTS / "panel-topics-390.png"))
        dialog.locator("[data-sheet-close]").click()
        page.locator("[data-sheet-open='more-sheet']").click()
        page.locator("#more-sheet[open] [data-havel-more]").click()
        page.locator("#havel-sheet[open]").wait_for()
        assert page.locator("#more-sheet[open]").count() == 0
        browser.close()


NEXT = {**ANSWER, "reply": "Two things. Open Guest links first.", "next": ["Sync my calendars", "What does the red badge mean?"]}


def test_phone_next_buttons_send_the_tapped_request(origin):
    shots = SHOTS.parent / "screenshots-0332"
    shots.mkdir(parents=True, exist_ok=True)
    ai.set_client_for_tests(FakeClient([reply(NEXT), reply(ANSWER)]))
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        page.locator(".ui-topbar [data-havel-launcher]").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        composer = dialog.locator("#havel-message")
        composer.wait_for()
        composer.fill("guest link, sync and the red badge")
        composer.press("Enter")
        nxt = dialog.locator("[data-havel-next]")
        nxt.wait_for()
        buttons = nxt.locator("button")
        assert buttons.count() == 2 and buttons.first.bounding_box()["height"] >= 36
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        page.screenshot(path=str(shots / "next-390.png"))
        buttons.first.click()
        dialog.locator(".havel-msg-havel:not([data-havel-writing])").last.wait_for()
        assert dialog.locator("[data-havel-next]").count() == 0
        assert "Sync my calendars" in dialog.locator(".havel-msg-host").last.inner_text()
        browser.close()
