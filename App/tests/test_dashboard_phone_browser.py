"""Phone dashboard (0147, 0148): dots instead of bars, reduced controls, one PIN alert, one-line setup banner."""
from __future__ import annotations

import os

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from tests.test_dashboard_calendar_browser import (  # noqa: F401
    calendar_origin, calendar_workspace, launch, open_page, shot,
)

HIDDEN_ON_PHONE = (".cal-view-segment", "[data-cal-settings]", "[data-cal-scales]", "[data-cal-month]", "[data-cal-year]")
SHOWN_ON_PHONE = ("[data-cal-property]", "[data-cal-prev]", "[data-cal-next]", "[data-cal-period]")


def visible_count(page, selector):
    return page.locator(selector).evaluate_all("nodes => nodes.filter(node => node.offsetParent).length")


def test_phone_dashboard_compact(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        for width in (390, 1280):
            context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, locale="en", touch=width < 768)
            if width < 768:
                page.wait_for_selector(".cal-week.is-dots")
                assert page.locator(".cal-week-events .cal-event").count() == 0
                assert page.locator(".cal-dots .cal-dot").count() >= 3
                assert page.locator(".cal-dot-more").first.inner_text() == "+1"
                for selector in HIDDEN_ON_PHONE:
                    assert visible_count(page, selector) == 0, selector
                for selector in SHOWN_ON_PHONE:
                    assert visible_count(page, selector) >= 1, selector
                page.locator('[data-cal-day="2026-10-15"]').click()
                assert page.locator("[data-cal-day-dialog]").is_visible()
                assert page.locator("[data-cal-day-list] .cal-event").count() == 4
                page.locator("[data-cal-day-dialog] [data-cal-close]").click()
                # 0148: alerts and banner (390)
            else:
                assert page.locator(".cal-dots").count() == 0
                assert page.locator(".cal-gantt-row").count() >= 1
                for selector in HIDDEN_ON_PHONE:
                    assert visible_count(page, selector) >= 1, selector
                # 0148: alerts and banner (1280)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            shot(page, f"phone-{width}")
            context.close()
        browser.close()
