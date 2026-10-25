"""0404: the Leon setup wizard in a real browser at 390 px (plus a 1280 px footer check).

Screenshots go to docs/tasks/screenshots-0404/. Skipped when Chromium is missing, unless
UBYHOST_REQUIRE_BROWSER=1.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import config, db, guest_guide, guest_guide_import
from tests.test_0251_tablet_browser import _context, base, host  # noqa: F401 (fixtures)
from tests.test_guest_browser_e2e import browser, live_server  # noqa: F401 (fixtures)

sync_api = pytest.importorskip("playwright.sync_api")
OUT = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0404"


@pytest.fixture
def leon_offered(monkeypatch, host):  # noqa: F811
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"leon"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "AI_TEST_EMAILS", frozenset())
    monkeypatch.setattr(config, "APIFY_TOKEN", "test-token")
    monkeypatch.setattr(guest_guide_import, "enabled", lambda: True)
    db.execute("UPDATE apartment SET leon_enabled = 0, leon_terms_version = NULL WHERE id = ?", (host["apartment"],))
    return host["apartment"]


def _progress(live: bool):
    def progress(apartment_id):
        return {
            "done": 5 if live else 0, "total": 5, "answered": 5 if live else 0, "cards": 5, "check": 0,
            "must_have_done": 5 if live else 0, "must_have_total": 5, "live": live,
        }
    return progress


def _no_overflow(page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def _footer_on_one_row(page) -> bool:
    back = page.locator(".setup-wizard-foot .setup-wizard-back").bounding_box()
    primary = page.locator(".setup-wizard-foot .ui-btn-primary").bounding_box()
    return abs(back["y"] - primary["y"]) <= 2


def test_setup_wizard_in_a_browser(live_server, browser, host, base, leon_offered, monkeypatch):  # noqa: F811
    OUT.mkdir(parents=True, exist_ok=True)
    apt = leon_offered
    monkeypatch.setattr(guest_guide, "progress", _progress(False))
    context = _context(browser, base, host, 390, 844)
    try:
        page = context.new_page()
        page.goto(f"{base}/apartments/{apt}/leon/setup?lang=en")
        assert page.url.endswith("/leon/setup/switch_on")
        assert _no_overflow(page)
        assert page.locator(".ui-btn-primary").count() == 1
        page.screenshot(path=str(OUT / "switch-on-390.png"), full_page=True)

        page.locator("#leon-terms").check()
        page.locator('button[form="leon-setup-on"]').click()
        page.wait_for_url(f"**/apartments/{apt}/leon/setup/import*")
        assert page.locator('input[name="booking_url"]').count() == 1
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "import-390.png"), full_page=True)

        page.locator('input[name="booking_url"]').fill("https://www.booking.com/hotel/cz/test-apartment.html")
        page.locator('input[name="airbnb_url"]').fill("https://www.airbnb.com/rooms/123456")
        page.locator('button[form="leon-setup-import"]').click()
        page.wait_for_selector("[data-leon-import-wait]")
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "import-waiting-390.png"), full_page=True)

        page.locator('button[name="action"][value="skip_import"]').click()
        page.wait_for_url(f"**/apartments/{apt}/leon/setup/cards")
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "cards-390.png"), full_page=True)

        page.set_viewport_size({"width": 1280, "height": 900})
        assert _footer_on_one_row(page)
        page.goto(f"{base}/apartments/{apt}/leon/setup/import?lang=en")
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "import-1280.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})

        monkeypatch.setattr(guest_guide, "progress", _progress(True))
        page.goto(f"{base}/apartments/{apt}/leon/setup/try?lang=en")
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "try-390.png"), full_page=True)
        page.locator('button[name="action"][value="finish"]').click()
        page.wait_for_url(f"**/apartments/{apt}/leon/setup/done")
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "done-390.png"), full_page=True)
    finally:
        context.close()
