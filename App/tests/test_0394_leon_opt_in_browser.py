"""0394: the Leon (AI) card on the property overview and the Leon page in a real browser at 390 px.

Screenshots go to docs/tasks/screenshots-0394/. Skipped when Chromium is missing, unless
UBYHOST_REQUIRE_BROWSER=1.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import config, db
from tests.test_0251_tablet_browser import _context, base, host  # noqa: F401 (fixtures)
from tests.test_guest_browser_e2e import browser, live_server  # noqa: F401 (fixtures)

OUT = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0394"


@pytest.fixture
def leon_offered(monkeypatch, host):  # noqa: F811
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"leon"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "AI_TEST_EMAILS", frozenset())
    db.execute("UPDATE apartment SET leon_enabled = 0, leon_terms_version = NULL WHERE id = ?", (host["apartment"],))
    return host["apartment"]


def _no_overflow(page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_overview_card_and_leon_page_at_390px(live_server, browser, host, base, leon_offered):  # noqa: F811
    OUT.mkdir(parents=True, exist_ok=True)
    apt = leon_offered
    context = _context(browser, base, host, 390, 844)
    try:
        page = context.new_page()
        page.goto(f"{base}/apartments/{apt}?view=overview&lang=en")
        card = page.locator('a.host-property-card[data-leon-card="off"]')
        card.scroll_into_view_if_needed()
        assert card.is_visible()
        assert _no_overflow(page)
        page.locator(".host-property-grid").screenshot(path=str(OUT / "overview-card-390.png"))

        page.goto(f"{base}/apartments/{apt}/leon?lang=en")
        assert _no_overflow(page)
        assert page.locator(".ui-btn-primary").count() == 1
        page.screenshot(path=str(OUT / "leon-off-390.png"), full_page=True)

        page.locator("#leon-terms").check()
        page.get_by_role("button", name="Switch Leon on").click()
        page.wait_for_load_state()
        assert "Leon is on and starts once your guest guide is live" in page.content()
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "leon-on-390.png"), full_page=True)
    finally:
        context.close()


def test_leon_page_off_at_1280px(live_server, browser, host, base, leon_offered):  # noqa: F811
    OUT.mkdir(parents=True, exist_ok=True)
    context = _context(browser, base, host, 1280, 900)
    try:
        page = context.new_page()
        page.goto(f"{base}/apartments/{leon_offered}?view=overview&lang=en")
        page.locator(".host-property-grid").screenshot(path=str(OUT / "overview-grid-1280.png"))
        page.goto(f"{base}/apartments/{leon_offered}/leon?lang=en")
        assert _no_overflow(page)
        page.screenshot(path=str(OUT / "leon-off-1280.png"), full_page=True)
    finally:
        context.close()
