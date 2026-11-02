"""0502: the nine per-page start-up functions bind each element once, so window.UbyHost.initPage can run again safely."""
from __future__ import annotations

import os

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from tests.test_dashboard_calendar import make_stay
from tests.test_dashboard_calendar_browser import calendar_origin, calendar_workspace, launch  # noqa: F401

# Each page lists the claimed selectors it is expected to show. Pages are
# chosen so that every selector below is present on at least one of them.
PAGES = [
    ("/reservations?lang=cs", [".action-panel", "#add-stay-panel", "[data-csv-export]", "#csv-export-dialog"]),
    ("/apartments/{property_id}?lang=cs", ["[data-automation-mode]", "#fee-copy-apply"]),
    ("/housebook?lang=cs", ["#housebook-pdf-dialog", "#csv-export-dialog"]),
]

# Every selector the nine functions claim. Some have no page in the templates
# yet (data-birth-date, form[data-notification-dismiss] and
# data-controller-same-toggle are not on the four pages above); they still go
# to the recorder so any listener added to them would be caught.
SELECTORS = [
    "[data-birth-date]", ".action-panel", "#add-stay-panel", "form[data-notification-dismiss]",
    "[data-automation-mode]", "form[data-inline-timing]", "[data-controller-same-toggle]",
    "#fee-copy-apply", "#csv-export-dialog", "[data-csv-export]", "#housebook-pdf-dialog",
]

RECORD_JS = """
(selectors) => {
  window.__adds = [];
  const orig = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    let target = 'other';
    if (this.matches && selectors.some(s => this.matches(s))) target = 'match';
    window.__adds.push([target, type]);
    return orig.call(this, type, fn, opts);
  };
  return true;
}
"""


def seed(ws):
    """Two stays so the list pages have rows."""
    properties = ws["properties"]
    make_stay(properties[0], "2026-10-01", "2026-10-03")
    make_stay(properties[1], "2026-10-02", "2026-10-04")
    # The stay-fee copy row needs a peer property with a fee rate (fee_template_peers).
    db.update("apartment", properties[1], {"stay_fee_rate_czk": 500})


def test_init_page_second_run_binds_no_claimed_element_again(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    property_id = calendar_workspace["properties"][0]
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = browser.new_context(viewport={"width": 390, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": calendar_workspace["client"].cookies.get(auth.SESSION_COOKIE), "url": calendar_origin + "/"}])
        for path_template, expected in PAGES:
            page = context.new_page()
            page.goto(calendar_origin + path_template.format(property_id=property_id))
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(250)

            # The test is not empty: every selector claimed for this page is on it.
            for selector in expected:
                assert page.locator(selector).count() >= 1, (path_template, selector)

            page.evaluate(RECORD_JS, SELECTORS)
            page.evaluate("() => window.UbyHost.initPage()")
            adds = page.evaluate("() => window.__adds")
            matched = [a for a in adds if a[0] == "match"]
            assert matched == [], (path_template, matched)
            page.close()
        context.close()
        browser.close()
