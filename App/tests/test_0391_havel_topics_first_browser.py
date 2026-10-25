"""0391: Havel starts with topics; the box opens after "Other topic" or "Didn't help? Ask Havel"."""
from __future__ import annotations

from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from tests import test_havel_browser as hb  # noqa: E402
from tests.test_submission_retry_cap import host  # noqa: E402,F401

origin = hb.origin
_context = hb._context

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0391"
ASK_PROMPT = "What is still unclear? Write it below and Havel will look into it."
OTHER_PROMPT = "Write your issue in a few words and Havel will look into it."


def _open(page):
    page.locator("[data-havel-fab]").click()
    dialog = page.locator("#havel-sheet[open]")
    dialog.wait_for()
    return dialog


@pytest.mark.parametrize("width", [390, 1280])
def test_topics_first_then_box(origin, width):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, width)
        page = context.new_page()
        page.goto(origin[0] + "/")
        dialog = _open(page)
        message = dialog.locator("#havel-message")
        sync_api.expect(message).to_be_hidden()
        sync_api.expect(dialog.locator("[data-havel-other]")).to_be_visible()
        assert dialog.locator(".havel-chips > a").last.get_attribute("data-havel-other") is not None
        page.screenshot(path=str(SHOTS / f"topics-{width}.png"))

        # A topic's answer, then "Didn't help? Ask Havel" opens the box.
        dialog.locator("[data-havel-topic-link]", has_text="stay").first.click()
        dialog.locator("[data-havel-topic-link][href*='q=cancelled']").wait_for()
        dialog.locator("[data-havel-topic-link][href*='q=cancelled']").click()
        dialog.locator(".havel-answer").wait_for()
        sync_api.expect(message).to_be_hidden()
        ask_chip = dialog.locator("[data-havel-ask-open]")
        sync_api.expect(ask_chip).to_have_text("Didn't help? Ask Havel")
        ask_chip.click()
        sync_api.expect(message).to_be_visible()
        sync_api.expect(message).to_be_focused()
        sync_api.expect(dialog.locator(".havel-bubble", has_text=ASK_PROMPT)).to_be_visible()
        if width == 390:
            page.screenshot(path=str(SHOTS / "answer-ask-390.png"))

        # A fresh chat: "Other topic" opens the box at once and the host can ask right away.
        page.evaluate("sessionStorage.clear()")
        page.goto(origin[0] + "/")
        dialog = _open(page)
        message = dialog.locator("#havel-message")
        sync_api.expect(message).to_be_hidden()
        dialog.locator("[data-havel-other]").click()
        sync_api.expect(dialog.locator(".havel-msg-host", has_text="Other topic")).to_be_visible()
        sync_api.expect(dialog.locator(".havel-bubble", has_text=OTHER_PROMPT)).to_be_visible()
        sync_api.expect(message).to_be_visible()
        sync_api.expect(message).to_be_focused()
        if width == 390:
            page.screenshot(path=str(SHOTS / "other-390.png"))
        page.keyboard.type("How do I add a stay?")
        page.keyboard.press("Enter")
        dialog.locator(".havel-msg-havel:not([data-havel-writing])").last.wait_for()
        sync_api.expect(dialog.locator(".havel-bubble ol li")).to_have_count(2)

        # The chat and the open box follow the host to another page.
        page.goto(origin[0] + "/apartments")
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        sync_api.expect(dialog.locator("#havel-message")).to_be_visible()
        assert "How do I add a stay?" in dialog.inner_text()
        assert page.evaluate("document.documentElement.scrollWidth") <= width

        # Without JavaScript: the box is locked until ask=1.
        locked = page.request.get(origin[0] + "/havel").text()
        assert "data-havel-locked" in locked
        unlocked = page.request.get(origin[0] + "/havel?ask=1").text()
        assert "data-havel-locked" not in unlocked
        assert OTHER_PROMPT in unlocked
        browser.close()
