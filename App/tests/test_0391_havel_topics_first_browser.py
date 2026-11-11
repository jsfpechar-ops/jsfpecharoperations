"""0391: the composer is there from the first open, below the topics; "Didn't help? Ask Havel" only focuses it."""
from __future__ import annotations

from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from tests import test_havel_browser as hb  # noqa: E402
from tests.test_submission_retry_cap import host  # noqa: E402,F401

origin = hb.origin
_context = hb._context

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0391"
ASK_PROMPT = "What is still unclear? Write it below and I will look into it."
OTHER_PROMPT = "Write your issue in a few words and I will look into it."


def _open(page):
    page.locator("[data-havel-fab]").click()
    dialog = page.locator("#havel-sheet[open]")
    dialog.wait_for()
    return dialog


@pytest.mark.parametrize("width", [390, 1280])
def test_composer_visible_with_topics_and_ask_chip_focuses_it(origin, width):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, width)
        page = context.new_page()
        page.goto(origin[0] + "/")
        dialog = _open(page)
        message = dialog.locator("#havel-message")
        sync_api.expect(message).to_be_visible()  # composer is visible on first open
        assert dialog.locator("[data-havel-other]").count() == 0  # no "Other topic" chip: the box is already there
        assert dialog.locator(".havel-chips > a").count() == 5
        page.screenshot(path=str(SHOTS / f"topics-{width}.png"))

        # A topic's answer, then "Didn't help? Ask Havel" focuses the box (no extra Havel bubble).
        dialog.locator("[data-havel-topic-link]", has_text="stay").first.click()
        dialog.locator("[data-havel-topic-link][href*='q=cancelled']").wait_for()
        dialog.locator("[data-havel-topic-link][href*='q=cancelled']").click()
        dialog.locator(".havel-answer").wait_for()
        sync_api.expect(message).to_be_visible()
        ask_chip = dialog.locator("[data-havel-ask-open]")
        sync_api.expect(ask_chip).to_have_text("Didn't help? Ask Havel")
        ask_chip.click()
        sync_api.expect(message).to_be_visible()
        sync_api.expect(message).to_be_focused()
        assert dialog.locator(".havel-bubble", has_text=ASK_PROMPT).count() == 0
        assert ask_chip.evaluate("el => parseFloat(getComputedStyle(el).borderTopLeftRadius)") >= 20  # rounded chip
        if width == 390:
            page.screenshot(path=str(SHOTS / "answer-ask-390.png"))

        # A fresh chat: the host can ask right away, without tapping anything first.
        page.evaluate("sessionStorage.clear()")
        page.goto(origin[0] + "/")
        dialog = _open(page)
        message = dialog.locator("#havel-message")
        sync_api.expect(message).to_be_visible()
        message.click()
        sync_api.expect(message).to_be_focused()
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
        assert OTHER_PROMPT in unlocked and "Other topic" not in unlocked
        browser.close()
