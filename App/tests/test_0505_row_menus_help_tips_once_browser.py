"""0505: initRowMenus and initHelpTips bind once; their document/window handlers still work after a second run."""
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

ROW_TRIGGER = ".row-menu-trigger"
ROW_PANEL = ".row-menu-panel"
HELP_TIP = "[data-help-tip]"
HELP_BUTTON = ".help-tip-btn"
MIXED_SELECTORS = [ROW_TRIGGER, ROW_PANEL, HELP_TIP, HELP_BUTTON]

# Each covered selector must be on the page before the second run, so the test is not empty.
PAGE_SELECTORS = {
    "reservations": [ROW_TRIGGER],
    "reservation_detail": [HELP_TIP],
}

# Same recorder as 0504: wraps addEventListener and records what each listener is bound to.
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
    const from = /initRowMenus|initHelpTips/.test(new Error().stack || '');
    window.__adds.push([target, type, hit, from]);
    return orig.call(this, type, fn, opts);
  };
  return true;
}
"""


def seed(ws):
    """Two stays so the reservations list has rows; returns the first stay id."""
    properties = ws["properties"]
    stay_id = make_stay(properties[0], "2026-10-01", "2026-10-03")
    make_stay(properties[1], "2026-10-02", "2026-10-04")
    return stay_id


def open_page(context, origin, path):
    page = context.new_page()
    page.goto(origin + path)
    page.wait_for_load_state()
    return page


def new_context(browser, ws, origin):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": ws["client"].cookies.get(auth.SESSION_COOKIE), "url": origin + "/"}])
    return context


def assert_second_run_binds_nothing(page):
    page.evaluate(RECORD_JS, MIXED_SELECTORS)
    page.evaluate("() => window.UbyHost.initPage()")
    adds = page.evaluate("() => window.__adds")
    element_hits = [a for a in adds if a[0] == "match"]
    assert element_hits == [], element_hits
    # Other inits still add document/window listeners on a second run (out of scope for 0505),
    # so the check is on who called addEventListener: nothing from initRowMenus or initHelpTips.
    from_hits = [a for a in adds if a[3]]
    assert from_hits == [], from_hits


def test_row_menus_and_help_tips_bind_nothing_on_second_run(calendar_workspace, calendar_origin):
    stay_id = seed(calendar_workspace)
    paths = {
        "reservations": "/reservations?lang=cs",
        "reservation_detail": "/reservations/%s?lang=cs" % stay_id,
    }
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        for name, path in paths.items():
            page = open_page(context, calendar_origin, path)
            for selector in PAGE_SELECTORS[name]:
                assert page.locator(selector).count() > 0, (name, selector)
            assert_second_run_binds_nothing(page)
            page.close()
        context.close()
        browser.close()


def test_row_menu_and_help_tip_still_work_after_two_runs(calendar_workspace, calendar_origin):
    stay_id = seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)

        # Row menu on the reservations list: open, then Escape closes it.
        page = open_page(context, calendar_origin, "/reservations?lang=cs")
        page.evaluate("() => window.UbyHost.initPage()")
        page.evaluate("() => window.UbyHost.initPage()")
        assert page.locator(ROW_TRIGGER).count() > 0
        page.locator(ROW_TRIGGER).first.click()
        assert page.locator(ROW_PANEL + ".is-open").count() == 1
        page.keyboard.press("Escape")
        assert page.locator(ROW_PANEL + ".is-open").count() == 0
        page.close()

        # Help tip on the reservation detail page: click opens it, Escape closes it.
        page = open_page(context, calendar_origin, "/reservations/%s?lang=cs" % stay_id)
        page.evaluate("() => window.UbyHost.initPage()")
        page.evaluate("() => window.UbyHost.initPage()")
        assert page.locator(HELP_TIP).count() > 0
        page.locator(HELP_BUTTON).first.click()
        assert page.locator(HELP_TIP + ".is-open").count() == 1
        page.keyboard.press("Escape")
        assert page.locator(HELP_TIP + ".is-open").count() == 0
        page.close()

        context.close()
        browser.close()
