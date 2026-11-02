"""0506: initFilterPanels, initDateRanges, initMonthPickers, initNavigation and initPowerTools bind once; behaviour still works."""
from __future__ import annotations

import os

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.test_dashboard_calendar import make_stay
from tests.test_dashboard_calendar_browser import calendar_origin, calendar_workspace, launch  # noqa: F401

# Same recorder as 0505: wraps addEventListener and keeps every add that comes from the 0506 init functions.
RECORD_JS = """
() => {
  window.__adds = [];
  const orig = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    const from = /initFilterPanels|initDateRanges|initMonthPickers|initNavigation|initPowerTools/.test(new Error().stack || '');
    if (from) window.__adds.push([this === document ? 'document' : this === window ? 'window' : 'element', type]);
    return orig.call(this, type, fn, opts);
  };
  return true;
}
"""

PAGES = ["/reservations?lang=cs", "/?lang=cs"]


def seed(ws):
    properties = ws["properties"]
    make_stay(properties[0], "2026-10-01", "2026-10-03")
    make_stay(properties[1], "2026-10-02", "2026-10-04")


def new_context(browser, ws, origin):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": ws["client"].cookies.get(auth.SESSION_COOKIE), "url": origin + "/"}])
    return context


def open_page(context, origin, path, width=1280):
    page = context.new_page()
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(origin + path)
    page.wait_for_load_state()
    return page


def test_second_init_adds_no_listeners(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        for path in PAGES:
            page = open_page(context, calendar_origin, path)
            page.evaluate(RECORD_JS)
            page.evaluate("() => window.UbyHost.initPage()")
            adds = page.evaluate("() => window.__adds")
            assert adds == [], (path, adds)
            page.close()
        context.close()
        browser.close()


def test_range_popover_and_drawer_and_command_dialog_still_work(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)

        # Filter panel and date range on the reservations list.
        page = open_page(context, calendar_origin, "/reservations?lang=cs")
        page.evaluate("() => window.UbyHost.initPage()")
        page.evaluate("() => window.UbyHost.initPage()")
        toggle = page.locator("[data-filter-toggle]:visible").first
        if toggle.count():
            toggle.click()
        trigger = page.locator("[data-range-trigger]:visible").first
        trigger.click()
        popover = page.locator("[data-date-range] [data-range-popover]").first
        assert popover.is_visible()
        page.keyboard.press("Escape")
        assert not popover.is_visible()
        page.close()

        # Command dialog: Ctrl+K opens it, Escape closes it.
        page = open_page(context, calendar_origin, "/?lang=cs")
        page.evaluate("() => window.UbyHost.initPage()")
        page.evaluate("() => window.UbyHost.initPage()")
        page.keyboard.press("Control+k")
        assert page.locator("#command-dialog[open]").count() == 1
        page.keyboard.press("Escape")
        assert page.locator("#command-dialog[open]").count() == 0
        page.close()

        context.close()
        browser.close()
