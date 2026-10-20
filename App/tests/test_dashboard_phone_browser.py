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

from app import alerts, db


def seed_pin_alerts(ws):
    for property_id in ws["properties"]:
        alerts.raise_alert(
            "warning", "guest_pin_rotated", "The guest link PIN was replaced with a new six-digit PIN.",
            detail="Four-digit PINs are no longer accepted.", dedupe_key=f"guest_pin_rotated:{property_id}",
            apartment_id=property_id, owner_user_id=ws["owner"],
        )
    return [db.query_one("SELECT internal_name FROM apartment WHERE id = ?", (pid,))["internal_name"] for pid in ws["properties"]]


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
                # The shared fixture puts five stays on 14-19 October: three dots plus "+2".
                assert page.locator(".cal-dot-more").first.inner_text() == "+2"
                for selector in HIDDEN_ON_PHONE:
                    assert visible_count(page, selector) == 0, selector
                for selector in SHOWN_ON_PHONE:
                    assert visible_count(page, selector) >= 1, selector
                page.locator('[data-cal-day="2026-10-15"]').click()
                assert page.locator("[data-cal-day-dialog]").is_visible()
                assert page.locator("[data-cal-day-list] .cal-event").count() == 5
                page.locator("[data-cal-day-dialog] [data-cal-close]").click()
                names = seed_pin_alerts(calendar_workspace)
                page.reload()
                pin_cards = page.locator("[data-notification]", has_text="PIN")
                assert pin_cards.count() == 1
                assert pin_cards.first.get_attribute("data-notification-group") == "guest_pin_rotated"
                for name in names:
                    assert name in pin_cards.first.inner_text(), name
                assert pin_cards.first.locator('a[href="/apartments"]').count() == 1
                short = page.locator(".dashboard-missing-short")
                assert short.is_visible()
                assert short.inner_text().strip() == "3 properties need setup", short.inner_text()
                assert not page.locator(".dashboard-missing-list").first.is_visible()
                assert page.locator(".ui-banner-attention .ui-btn").count() == 1
                shot(page, "phone-390-alert")
                pin_cards.first.locator("[data-notification-dismiss] button").click()
                page.wait_for_timeout(500)
                page.reload()
                assert page.locator("[data-notification]", has_text="PIN").count() == 0
            else:
                assert page.locator(".cal-dots").count() == 0
                assert page.locator(".cal-gantt-row").count() >= 1
                for selector in HIDDEN_ON_PHONE:
                    if selector != "[data-cal-scales]":
                        assert visible_count(page, selector) >= 1, selector
                assert not page.locator("[data-cal-scales]").is_visible()  # gantt hides scales by design
                page.locator('[data-cal-view="calendar"]').click()
                page.locator("[data-cal-scales]").wait_for(state="visible")
                page.locator('[data-cal-view="gantt"]').click()
                page.locator(".cal-gantt-row").first.wait_for(state="visible")
                assert page.locator(".dashboard-missing-list").first.is_visible()
                assert not page.locator(".dashboard-missing-short").is_visible()
                assert page.locator(".dashboard-missing-line").count() == 3
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            shot(page, f"phone-{width}")
            context.close()
        browser.close()
