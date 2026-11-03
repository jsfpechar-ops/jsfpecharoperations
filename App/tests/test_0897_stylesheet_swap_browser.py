"""0897: a page with another stylesheet set is a full load, never a Turbo swap that mixes both sets (real Chromium)."""
from __future__ import annotations

import os

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from tests.test_0508_page_swap_browser import new_context, open_page, seed
from tests.test_dashboard_calendar_browser import calendar_origin, calendar_workspace, launch  # noqa: F401,F811

# The sidebar page that still uses the old stylesheet set (body has no "v2" class).
OLD_PAGE = "/payments"
STYLESHEETS = "() => [...document.querySelectorAll('link[rel=stylesheet]')].map((l) => l.getAttribute('href').split('?')[0].split('/').pop())"


def sheets(page):
    return page.evaluate(STYLESHEETS)


def test_old_stylesheet_page_and_back_never_mix_sets(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = open_page(context, calendar_origin, "/?lang=cs")
        assert "app.css" not in sheets(page)
        assert page.evaluate("() => document.body.classList.contains('v2')")

        page.locator(f'#app-sidebar a[href="{OLD_PAGE}"]').first.click()
        page.wait_for_function("(p) => location.pathname === p", arg=OLD_PAGE, timeout=15000)
        page.wait_for_load_state()
        names = sheets(page)
        assert not ("app.css" in names and "app2.css" in names), names
        assert "app.css" in names
        assert not page.evaluate("() => document.body.classList.contains('v2')")

        page.locator('#app-sidebar a[href="/"]').first.click()
        page.wait_for_selector('#app-sidebar a[href="/"][aria-current="page"]', timeout=15000)
        names = sheets(page)
        assert not ("app.css" in names and "app2.css" in names), names
        assert "app.css" not in names
        assert "app2.css" in names
        assert page.evaluate("() => document.body.classList.contains('v2')")
        browser.close()


def test_dashboard_to_another_v2_page_stays_a_swap(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = open_page(context, calendar_origin, "/?lang=cs")
        page.evaluate("() => { window.__swapMarker = 1; }")
        page.locator('#app-sidebar a[href="/reservations"]').first.click()
        page.wait_for_selector('#app-sidebar a[href="/reservations"][aria-current="page"]', timeout=15000)
        assert page.evaluate("() => window.__swapMarker") == 1
        assert "app.css" not in sheets(page)
        assert "app2.css" in sheets(page)
        browser.close()
