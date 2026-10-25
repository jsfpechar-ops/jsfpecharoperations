"""0319: the support card at 390 px without JavaScript."""
from pathlib import Path

from playwright import sync_api

from app import ai
from tests.ai_fake import FakeClient, reply
from tests.test_havel_browser import _context, origin  # noqa: F401
from tests.test_havel_support import ESCALATE
from tests.test_submission_retry_cap import host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0319"


def test_support_card_sends_without_javascript_at_390(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    ai.set_client_for_tests(FakeClient([reply(ESCALATE)]))
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390, js=False)
        page = context.new_page()
        page.goto(f"{origin[0]}/havel?lang=en")
        page.fill("#havel-message", "Error 4 on my report")
        page.locator("[data-havel-form] [data-havel-send]").click()
        card = page.locator("[data-havel-support]")
        card.wait_for()
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        card.screenshot(path=str(SHOTS / "support-card-390.png"))
        page.fill("#havel-support-note", "Since Monday")
        card.locator("button[type=submit]").click()
        page.get_by_text("Forwarded to the UbyHost team.").first.wait_for()
        page.screenshot(path=str(SHOTS / "support-sent-390.png"))
        browser.close()
