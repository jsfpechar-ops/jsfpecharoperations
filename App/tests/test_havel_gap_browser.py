"""0320: the "This didn't help" button at 390 px."""
import os
from pathlib import Path

import pytest

if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
    from playwright import sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import ai
from tests.ai_fake import FakeClient, reply
from tests.test_havel_browser import _context, origin  # noqa: F401
from tests.test_havel_gap import ANSWER
from tests.test_submission_retry_cap import host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0320"


def test_not_helped_at_390(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    ai.set_client_for_tests(FakeClient([reply(ANSWER)]))
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390, js=False)
        page = context.new_page()
        page.goto(f"{origin[0]}/havel?lang=en&ask=1")
        page.fill("#havel-message", "How do I add a stay?")
        page.locator("[data-havel-form] [data-havel-send]").click()
        button = page.locator("[data-havel-not-helped] button")
        button.wait_for()
        page.locator(".havel-msg-havel").last.screenshot(path=str(SHOTS / "not-helped-390.png"))
        button.click()
        page.locator("[data-havel-support]").wait_for()
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        browser.close()
