"""0895: a wide window never keeps the sidebar inert; a compact window keeps its drawer behaviour (real Chromium)."""
from __future__ import annotations

import os

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.test_0508_page_swap_browser import new_context, open_page, seed
from tests.test_dashboard_calendar_browser import calendar_origin, calendar_workspace, launch  # noqa: F401

SIDEBAR = "#app-sidebar"


def sidebar_inert(page):
    return page.evaluate("() => document.getElementById('app-sidebar').inert")


def test_wide_window_heals_stuck_inert_sidebar(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = open_page(context, calendar_origin, "/?lang=cs")
        page.evaluate("() => { document.getElementById('app-sidebar').inert = true; }")
        assert sidebar_inert(page) is True
        page.mouse.click(640, 400)
        assert sidebar_inert(page) is False
        page.locator('#app-sidebar .side-bottom a[href="/guide"]').click()
        page.wait_for_url("**/guide**", timeout=15000)
        page.locator('#app-sidebar a[href="/"]').first.click()
        page.wait_for_url(lambda url: url.split("?")[0].rstrip("/") == calendar_origin.rstrip("/"), timeout=15000)
        browser.close()


def test_compact_window_keeps_drawer_inert_until_opened(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = browser.new_context(viewport={"width": 800, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": calendar_workspace["client"].cookies.get(auth.SESSION_COOKIE), "url": calendar_origin + "/"}])
        page = context.new_page()
        page.goto(calendar_origin + "/?lang=cs")
        page.wait_for_load_state()
        assert sidebar_inert(page) is True
        page.evaluate(
            "() => document.getElementById('main-content').dispatchEvent("
            "new PointerEvent('pointerdown', {bubbles: true, cancelable: true}))"
        )
        assert sidebar_inert(page) is True
        browser.close()
