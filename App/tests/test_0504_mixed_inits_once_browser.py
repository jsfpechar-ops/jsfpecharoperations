"""0504: initUnsavedForms, initSubmitGuard and initDetailsLinks bind once; their window handlers still work after a page swap."""
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

GUARD = "form[data-unsaved-guard]"
SUBMIT_FORM = ".action-panel form"
DETAILS_LINK = "[data-open-details]"
MIXED_SELECTORS = [SUBMIT_FORM, DETAILS_LINK, GUARD]
WINDOW_TYPES = ["beforeunload", "pageshow", "hashchange"]

# Each covered selector must be on the page before the second run, so the test is not empty.
PAGE_SELECTORS = {
    "reservations": [SUBMIT_FORM],
    "apartment": [GUARD],
    "reservation_detail": [DETAILS_LINK],
}

# Same recorder as 0503: wraps addEventListener and records what each listener is bound to.
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

# Dispatches a cancelable beforeunload and reports whether a handler asked to prompt.
BEFORE_UNLOAD_JS = """
() => {
  const e = new Event('beforeunload', { cancelable: true });
  window.dispatchEvent(e);
  return e.defaultPrevented;
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


def assert_mixed_second_run(page):
    page.evaluate(RECORD_JS, MIXED_SELECTORS)
    page.evaluate("() => window.UbyHost.initPage()")
    adds = page.evaluate("() => window.__adds")
    element_hits = [a for a in adds if a[0] == "match" and a[2] != GUARD]
    assert element_hits == [], element_hits
    window_hits = sorted(a[1] for a in adds if a[0] == "window" and a[1] in WINDOW_TYPES)
    # initPropertyViews still re-binds a hashchange on window; brief 0505 makes this zero.
    expected_window = ["hashchange"] if page.locator("[data-property-views]").count() else []
    assert window_hits == expected_window, window_hits
    guard_events = sorted(a[1] for a in adds if a[0] == "match" and a[2] == GUARD)
    # initPropertyViews still re-binds; brief 0505 makes this zero.
    assert guard_events == sorted(["invalid"] * page.locator(GUARD).count()), guard_events


def test_mixed_inits_bind_nothing_on_second_run(calendar_workspace, calendar_origin):
    stay_id = seed(calendar_workspace)
    property_id = calendar_workspace["properties"][0]
    paths = {
        "reservations": "/reservations?lang=cs",
        "apartment": "/apartments/%s?lang=cs" % property_id,
        "reservation_detail": "/reservations/%s?lang=cs" % stay_id,
    }
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        for name, path in paths.items():
            page = open_page(context, calendar_origin, path)
            for selector in PAGE_SELECTORS[name]:
                assert page.locator(selector).count() > 0, (name, selector)
            assert_mixed_second_run(page)
            page.close()
        context.close()
        browser.close()


def test_unsaved_before_unload_still_works_after_two_runs(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    property_id = calendar_workspace["properties"][0]
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = open_page(context, calendar_origin, "/apartments/%s?lang=cs" % property_id)
        page.evaluate("() => window.UbyHost.initPage()")
        page.evaluate("() => window.UbyHost.initPage()")
        assert page.locator(GUARD).count() > 0

        # Mark the first guarded form dirty with the input event its own handler listens for.
        page.locator(GUARD).first.dispatch_event("input")
        assert page.evaluate(BEFORE_UNLOAD_JS) is True

        # A submitting form is not unsaved: the prompt is off, and the flag is cleared.
        page.evaluate("() => { document.querySelector('form[data-unsaved-guard]')._ubySubmitting = true; }")
        assert page.evaluate(BEFORE_UNLOAD_JS) is False
        assert page.evaluate(BEFORE_UNLOAD_JS) is True

        context.close()
        browser.close()
