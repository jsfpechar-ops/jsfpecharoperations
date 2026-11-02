"""0508: host pages swap with Turbo; forms, logout and Back behave as before (real Chromium)."""
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

HELP_TIP = "[data-help-tip]"
HELP_BUTTON = ".help-tip-btn"
ROW_TRIGGER = ".row-menu-trigger"
ROW_PANEL = ".row-menu-panel"
COMMAND_DIALOG = "#command-dialog"

# Records document/window listeners added while initPage (or one of its init functions) runs.
RECORD_JS = """
() => {
  window.__adds = [];
  const orig = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    if ((this === document || this === window) && /initPage|init[A-Z]/.test(new Error().stack || '')) {
      window.__adds.push(type);
    }
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


def turbo_visit(page, path, loads_before):
    """Start a Turbo visit from script and wait until its turbo:load has run."""
    page.evaluate("(p) => window.Turbo.visit(p)", path)
    page.wait_for_function("(n) => window.__loads > n", arg=loads_before, timeout=15000)
    page.wait_for_function("(p) => location.pathname + location.search.replace(/^\\?.*$/, '') === p.split('?')[0]", arg=path, timeout=15000)


def test_sidebar_click_swaps_without_full_load(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = open_page(context, calendar_origin, "/?lang=cs")
        page.evaluate("() => { window.__swapMarker = 1; }")
        page.locator('#app-sidebar a[href="/reservations"]').first.click()
        page.wait_for_selector('#app-sidebar a[href="/reservations"][aria-current="page"]', timeout=15000)
        assert page.evaluate("() => window.__swapMarker") == 1
        assert page.locator("#main-content").is_visible()
        assert page.locator('#app-sidebar a[href="/"][aria-current="page"]').count() == 0
        browser.close()


def test_controls_work_after_swap_and_back_restores_dashboard(calendar_workspace, calendar_origin):
    stay_id = seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = open_page(context, calendar_origin, "/?lang=cs")
        page.evaluate("() => { window.__swapMarker = 1; }")
        page.evaluate("() => { window.__loads = 0; document.addEventListener('turbo:load', () => { window.__loads += 1; }); }")
        page.locator('#app-sidebar a[href="/reservations"]').first.click()
        page.wait_for_selector('#app-sidebar a[href="/reservations"][aria-current="page"]', timeout=15000)

        # Row menu on the swapped-in list: open, then Escape closes it.
        page.locator(ROW_TRIGGER).first.click()
        assert page.locator(ROW_PANEL + ".is-open").count() == 1
        page.keyboard.press("Escape")
        assert page.locator(ROW_PANEL + ".is-open").count() == 0

        # Help tip on the detail page reached by a Turbo visit (lifted out of its section, as in 0505).
        turbo_visit(page, "/reservations/%s?lang=cs" % stay_id, page.evaluate("() => window.__loads"))
        page.evaluate("() => { const t = document.querySelector('[data-help-tip]'); document.querySelector('main').prepend(t); }")
        page.locator(HELP_BUTTON + ":visible").first.click()
        assert page.locator(HELP_TIP + ".is-open").count() == 1
        page.keyboard.press("Escape")

        # Command dialog opens with Ctrl+K after the swap.
        page.keyboard.press("Control+k")
        page.wait_for_selector(COMMAND_DIALOG, state="visible", timeout=5000)
        page.keyboard.press("Escape")

        # Back returns to the dashboard without a full reload, and the calendar renders.
        page.go_back()
        page.wait_for_function("() => location.pathname === '/reservations'", timeout=15000)
        page.go_back()
        page.wait_for_function("() => location.pathname === '/'", timeout=15000)
        page.wait_for_selector('#app-sidebar a[href="/"][aria-current="page"]', timeout=15000)
        assert page.evaluate("() => window.__swapMarker") == 1
        browser.close()


def test_listeners_do_not_grow_over_five_swaps(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = open_page(context, calendar_origin, "/?lang=cs")
        page.evaluate("() => { window.__loads = 0; document.addEventListener('turbo:load', () => { window.__loads += 1; }); }")
        # Visit both pages once first: a feature that exists only on one page binds its document
        # listeners the first time that page appears, and never again after that.
        for path in ("/reservations?lang=cs", "/?lang=cs"):
            turbo_visit(page, path, page.evaluate("() => window.__loads"))
        page.evaluate(RECORD_JS)
        for i in range(5):
            path = "/reservations?lang=cs" if i % 2 == 0 else "/?lang=cs"
            turbo_visit(page, path, page.evaluate("() => window.__loads"))
        adds = page.evaluate("() => window.__adds")
        assert adds == [], "\n".join(adds)
        browser.close()


def test_form_submit_is_a_full_load(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = open_page(context, calendar_origin, "/reservations?lang=cs")
        page.evaluate("() => { window.__swapMarker = 1; }")
        with page.expect_navigation(timeout=15000):
            page.evaluate(
                "() => { const f = [...document.querySelectorAll('#main-content form')]"
                ".find(f => (f.method || 'get').toLowerCase() === 'get'); f.requestSubmit(); }"
            )
        page.wait_for_load_state()
        assert page.evaluate("() => window.__swapMarker") is None
        browser.close()


def test_logout_is_a_full_load_and_back_shows_no_dashboard(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = open_page(context, calendar_origin, "/?lang=cs")
        page.locator('#app-sidebar a[href="/reservations"]').first.click()
        page.wait_for_selector('#app-sidebar a[href="/reservations"][aria-current="page"]', timeout=15000)
        page.evaluate("() => { window.__swapMarker = 1; }")
        with page.expect_navigation(timeout=15000):
            page.locator('form[action="/logout"] button:visible').first.click()
        page.wait_for_load_state()
        assert page.evaluate("() => window.__swapMarker") is None
        page.go_back()
        page.wait_for_load_state()
        assert page.locator('#app-sidebar a[href="/reservations"]').count() == 0
        browser.close()
