"""0501: the shared binder binds each element once, and window.UbyHost.initPage can run again without double-binding."""
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

SELECTORS = ["[data-copy]", "tr[data-href]", ".clickable-row[data-href]", ".row-menu-trigger", "[data-dismiss-banner]", "form[data-confirm]", "button[data-confirm]"]

RECORD_JS = """
(selectors) => {
  window.__adds = [];
  const orig = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    let target = 'other';
    if (this === document) target = 'document';
    else if (this === window) target = 'window';
    else if (this.matches && selectors.some(s => this.matches(s))) target = 'match';
    window.__adds.push([target, type]);
    return orig.call(this, type, fn, opts);
  };
  return true;
}
"""


def seed(ws):
    """Two stays so the reservations list has rows."""
    properties = ws["properties"]
    make_stay(properties[0], "2026-10-01", "2026-10-03")
    make_stay(properties[1], "2026-10-02", "2026-10-04")


def test_init_page_second_run_binds_no_row_or_button_again(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": calendar_workspace["client"].cookies.get(auth.SESSION_COOKIE), "url": calendar_origin + "/"}])
        page = context.new_page()
        page.goto(calendar_origin + "/reservations?lang=cs")
        page.wait_for_selector("tr[data-href]", timeout=20000)
        page.wait_for_timeout(250)

        page.evaluate(RECORD_JS, SELECTORS)
        page.evaluate("() => window.UbyHost.initPage()")
        adds = page.evaluate("() => window.__adds")

        matched = [a for a in adds if a[0] == "match"]
        doc_content_updated = [a for a in adds if a[0] == "document" and a[1] == "ubyhost:content-updated"]
        assert matched == [], matched
        assert doc_content_updated == [], doc_content_updated

        href = page.locator("tr[data-href]").first.get_attribute("data-href")
        navigations = []
        page.on("framenavigated", lambda frame: navigations.append(frame.url) if frame == page.main_frame else None)
        page.locator("tr[data-href]").first.click()
        page.wait_for_url("**" + href, timeout=20000)
        page.wait_for_load_state()
        assert len(navigations) == 1, navigations
        assert page.url.endswith(href), (page.url, href)
        context.close()
        browser.close()
