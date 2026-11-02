"""0507: host scripts bind page elements once per page; a second initPage() adds no document/window listeners."""
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

PUSH_ROW = "[data-push-row]"
CALENDAR = "[data-calendar]"
SELECTORS = [PUSH_ROW, CALENDAR, "[data-havel-panel]", "[data-havel-page]"]

# Same recorder as 0505: wraps addEventListener and records what each listener is bound to.
RECORD_JS = """
(selectors) => {
  window.__adds = [];
  const orig = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    let target = 'other';
    if (this === document) target = 'document';
    else if (this === window) target = 'window';
    let hit = null;
    if (!(this === document || this === window) && this.matches) hit = selectors.find(s => this.matches(s)) || null;
    if (hit) target = 'match';
    window.__adds.push([target, type, hit]);
    return orig.call(this, type, fn, opts);
  };
  return true;
}
"""


def open_page(context, origin, path):
    page = context.new_page()
    page.goto(origin + path)
    page.wait_for_load_state()
    return page


def new_context(browser, ws, origin):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": ws["client"].cookies.get(auth.SESSION_COOKIE), "url": origin + "/"}])
    return context


def test_second_init_page_adds_no_document_or_window_listeners(calendar_workspace, calendar_origin):
    make_stay(calendar_workspace["properties"][0], "2026-10-03", "2026-10-07")
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        for path in ["/?lang=cs&cal_view=calendar", "/cleaning?lang=cs", "/settings?lang=cs"]:
            page = open_page(context, calendar_origin, path)
            page.evaluate(RECORD_JS, SELECTORS)
            page.evaluate("() => window.UbyHost.initPage()")
            adds = page.evaluate("() => window.__adds")
            assert [a for a in adds if a[0] in ("document", "window", "match")] == [], (path, adds)
            page.close()
        context.close()
        browser.close()


def test_calendar_and_cleaning_still_render_after_two_runs(calendar_workspace, calendar_origin):
    make_stay(calendar_workspace["properties"][0], "2026-10-03", "2026-10-07")
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        # The dashboard shows its calendar only with cal_view; the cleaning page has the calendar and the list.
        for path, list_selector in [("/?lang=cs&cal_view=calendar", None), ("/cleaning?lang=cs", "[data-cleaning-list]")]:
            page = open_page(context, calendar_origin, path)
            page.evaluate("() => window.UbyHost.initPage()")
            page.evaluate("() => window.UbyHost.initPage()")
            page.wait_for_selector(CALENDAR, state="attached")
            page.wait_for_selector("[data-cal-body]", state="attached")
            assert page.locator("[data-cal-body]").count() > 0, path
            if list_selector:
                assert page.locator(list_selector).count() > 0, path
            page.close()
        context.close()
        browser.close()


def test_settings_push_row_stays_bound_after_two_runs(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = open_page(context, calendar_origin, "/settings/phone?lang=cs")
        page.evaluate("() => window.UbyHost.initPage()")
        page.evaluate("() => window.UbyHost.initPage()")
        assert page.locator(PUSH_ROW).count() > 0
        # pwa.js claims the row through onPage; the claim record is the proof it is bound once and still present.
        claimed = page.evaluate("(sel) => Object.keys(document.querySelector(sel)._ubyBound || {})", PUSH_ROW)
        assert claimed, claimed
        page.close()
        context.close()
        browser.close()
