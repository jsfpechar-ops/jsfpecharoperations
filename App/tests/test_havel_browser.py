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

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0373"
SHOTS_0374 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0374"
ANSWER = {"kind": "answer", "reply": "Open Stays.\n1. Tap Add stay.\n2. Pick the dates.", "sources": ["guide.stays.body"],
          "links": [{"page": "add_stay", "property_id": None}], "action": None, "support_summary": None}


@pytest.fixture
def origin(host, monkeypatch):
    db.init_db()
    # Other Havel test files leave rate-limit rows behind; a burst limit hides the composer.
    for scope in ("havel_burst", "havel_week", "havel_month", "havel_refuse"):
        db.execute("DELETE FROM rate_limit_event WHERE scope = ?", (scope,))
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
        launcher = page.locator("[data-havel-fab]")
        assert launcher.is_visible()
        launcher.click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        assert page.evaluate("document.querySelector('#havel-sheet').matches(':modal')") is False
        assert launcher.count() == 1 and not launcher.is_visible()
        sidebar = page.locator("#app-sidebar").bounding_box()
        assert page.evaluate("([x, y]) => !!document.elementFromPoint(x, y).closest('#app-sidebar')", [sidebar["x"] + sidebar["width"] / 2, sidebar["y"] + sidebar["height"] / 2])
        assert dialog.locator("[data-havel-topic-link]").count() == 6  # 0391: five topics + "Other topic"
        assert dialog.locator("h2#havel-title").inner_text().strip() == "Havel (AI)"
        box = dialog.locator(".ui-sheet").bounding_box()
        assert box["width"] <= 400 and box["height"] <= 680
        dialog.locator("[data-havel-topic-link]", has_text="stay").first.click()
        dialog.locator("[data-havel-topic-link][href*='q=cancelled']").wait_for()
        dialog.locator("[data-havel-topic-link][href*='q=cancelled']").click()
        dialog.locator("[data-havel-ask-open]").wait_for()
        page.screenshot(path=str(SHOTS / "panel-topic-1280.png"))
        dialog.locator("[data-havel-ask-open]").click()
        sync_api.expect(page.locator("#havel-message")).to_be_focused()
        assert dialog.locator("[data-havel-topic]").input_value() == "stays"
        page.keyboard.type("And if the guest never arrives?")
        page.keyboard.press("Enter")
        dialog.locator(".havel-msg-havel:not([data-havel-writing])").last.wait_for()
        assert dialog.locator(".havel-msg-host").count() == 1
        assert dialog.locator(".havel-bubble ol li").count() == 2
        assert page.evaluate("document.activeElement.className").startswith("havel-msg havel-msg-havel")
        assert dialog.locator("[data-havel-topics]").count() == 0
        page.screenshot(path=str(SHOTS / "panel-answer-1280.png"))
        page.keyboard.press("Escape")
        assert page.locator("#havel-sheet[open]").count() == 0
        sync_api.expect(launcher).to_be_visible()
        sync_api.expect(launcher).to_be_focused()
        browser.close()


def test_phone_launcher_and_sheet(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        fab = page.locator("[data-havel-fab]")
        assert fab.is_visible()
        fb = fab.bounding_box()
        assert fb["width"] >= 44 and fb["height"] >= 44
        tabbar = page.locator(".ui-tabbar").bounding_box()
        assert fb["y"] + fb["height"] <= tabbar["y"]
        page.screenshot(path=str(SHOTS / "fab-dashboard-390.png"))
        fab.click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        sheet = dialog.locator(".ui-sheet").bounding_box()
        assert sheet["width"] == 390 and sheet["height"] >= 900 - 48 - 2
        assert sheet["y"] <= 48 + 1
        assert not fab.is_visible()
        assert dialog.locator("[data-havel-device]").input_value() == "phone"
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        page.screenshot(path=str(SHOTS / "panel-open-390.png"))
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
        page.locator("[data-havel-fab]").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        dialog.locator("[data-havel-other]").click()
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


def test_greeting_shows_once_after_a_reply(origin):
    ai.set_client_for_tests(FakeClient([reply(ANSWER)]))
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        page.locator("[data-havel-fab]").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        assert dialog.locator("[data-havel-greeting]").count() == 1
        dialog.locator("[data-havel-other]").click()
        composer = dialog.locator("#havel-message")
        composer.fill("How do I add a stay?")
        composer.press("Enter")
        assert composer.input_value() == ""
        dialog.locator(".havel-bubble ol li").first.wait_for()
        assert dialog.locator("[data-havel-greeting]").count() == 1
        browser.close()


def test_czech_greeting_on_the_phone(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/?lang=cs")
        page.locator("[data-havel-fab]").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        assert "Dobrý den, jsem Havel" in dialog.locator("[data-havel-greeting]").inner_text()
        page.screenshot(path=str(SHOTS / "panel-open-cs-390.png"))
        browser.close()


# 0374: the chat follows the host across pages (sessionStorage, this tab only).
@pytest.mark.parametrize("width", [1280, 390])
def test_chat_follows_the_host_across_pages(origin, width):
    SHOTS_0374.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, width)
        page = context.new_page()
        page.goto(origin[0] + "/")
        page.locator("[data-havel-fab]").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        dialog.locator("[data-havel-other]").click()
        composer = dialog.locator("#havel-message")
        composer.wait_for()
        composer.fill("How do I add a stay?")
        composer.press("Enter")
        # Wait for the reply itself: the intro bubble already matches .havel-msg-havel.
        dialog.locator(".havel-bubble ol li").first.wait_for()
        sync_api.expect(dialog.locator("[data-havel-history]")).not_to_have_value("[]")
        history_before = dialog.locator("[data-havel-history]").input_value()
        # The panel is still open on the next page, with the same chat.
        page.goto(origin[0] + "/guide")
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        sync_api.expect(dialog.locator(".havel-msg-host", has_text="How do I add a stay?")).to_have_count(1)
        sync_api.expect(dialog.locator("[data-havel-history]")).to_have_value(history_before)
        page.screenshot(path=str(SHOTS_0374 / f"restored-{width}.png"))
        # Closing only minimises it: the next page starts closed, and the chat is there on opening.
        dialog.locator("[data-sheet-close]").first.click()
        sync_api.expect(page.locator("#havel-sheet[open]")).to_have_count(0)
        # The close event (which saves the chat as closed and shows the button again) runs after the attribute goes; wait for it.
        sync_api.expect(page.locator("[data-havel-fab]")).to_be_visible()
        page.goto(origin[0] + "/")
        sync_api.expect(page.locator("[data-havel-fab]")).to_be_visible()
        assert page.locator("#havel-sheet[open]").count() == 0
        page.locator("[data-havel-fab]").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        sync_api.expect(dialog.locator(".havel-msg-host", has_text="How do I add a stay?")).to_have_count(1)
        browser.close()


def test_new_chat_and_other_user_clear_it(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        page.locator("[data-havel-fab]").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        dialog.locator("[data-havel-other]").click()
        composer = dialog.locator("#havel-message")
        composer.wait_for()
        composer.fill("How do I add a stay?")
        composer.press("Enter")
        dialog.locator(".havel-bubble ol li").first.wait_for()
        dialog.locator("button[name=reset]").click()
        sync_api.expect(dialog.locator(".havel-msg-host")).to_have_count(0)
        sync_api.expect(dialog.locator("[data-havel-greeting]")).to_have_count(1)
        page.goto(origin[0] + "/guide")
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        sync_api.expect(dialog.locator(".havel-msg-host")).to_have_count(0)
        sync_api.expect(dialog.locator("[data-havel-greeting]")).to_have_count(1)
        # A stored chat that belongs to another user is ignored and removed.
        page.evaluate("""() => sessionStorage.setItem('ubyhost.havel.chat', JSON.stringify({owner: '999999', saved: Date.now(), html: '<div class="havel-msg havel-msg-host"><div class="havel-bubble"><p>Other user chat</p></div></div>', history: '', sig: '', topic: '', q: '', open: true, unread: false}))""")
        page.reload()
        assert page.locator(".havel-msg-host", has_text="Other user chat").count() == 0
        assert page.locator("#havel-sheet[open]").count() == 0
        assert page.evaluate("() => sessionStorage.getItem('ubyhost.havel.chat')") is None
        browser.close()
