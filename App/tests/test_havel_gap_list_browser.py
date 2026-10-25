"""0331: the admin Havel section at 390 px."""
from pathlib import Path

from playwright import sync_api

from app import havel
from tests.test_havel_browser import _context, origin  # noqa: F401
from tests.test_submission_retry_cap import host  # noqa: F401

SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0331"


def test_admin_havel_section_at_390(origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    havel.record_gap("en", "stays", "escalate", "Can guests pay the stay fee by card?")
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390, js=False)
        page = context.new_page()
        page.goto(f"{origin[0]}/admin/operations#ops-havel")
        section = page.locator("#ops-havel")
        section.wait_for()
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        section.screenshot(path=str(SHOTS / "admin-havel-390.png"))
        browser.close()
