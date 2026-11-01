"""0503: eight more per-page start-up functions bind once, so a second window.UbyHost.initPage() adds no listeners."""
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

SELECTORS = [
    "#unsaved-dialog",
    "form[data-unsaved-guard]",
    "form[data-auto-submit]",
    "[data-generate-password]",
    "#reset-password-dialog",
    "#confirm-dialog",
    "[data-saved-views]",
    "[data-save-view]",
    "form[data-inline-edit]",
    "[data-feedback-rail]",
    "[data-toast]",
]

# Selectors each real page must contain before the second run, so the test is not empty.
PAGE_SELECTORS = {
    "reservations": ["#unsaved-dialog", "#confirm-dialog", "[data-feedback-rail]", "[data-saved-views]", "[data-save-view]"],
    "reservation_detail": ["form[data-inline-edit]"],
    "apartment": ["form[data-unsaved-guard]"],
}

# No template renders these yet, so the test adds the markup itself and runs initPage once before the second run.
INJECT_JS = """
() => {
  const rail = document.querySelector("[data-feedback-rail]");
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.setAttribute("data-toast", "");
  toast.setAttribute("data-toast-kind", "info");
  toast.innerHTML = '<span class="grow">injected</span><button type="button" data-toast-close>&times;</button>';
  rail.appendChild(toast);

  const host = document.createElement("div");
  host.innerHTML = `
    <form data-auto-submit><select name="probe"><option value="a">a</option><option value="b">b</option></select></form>
    <div class="password-generate"><input type="text" data-generated-password><button type="button" data-generate-password>Generate</button></div>
    <button type="button" data-reset-password data-user-id="1" data-user-label="probe">Reset</button>
    <dialog id="reset-password-dialog"><p id="reset-password-label"></p>
      <form id="reset-password-form" method="post"><input type="password" data-generated-password>
        <button type="button" data-reset-password-cancel>Cancel</button></form></dialog>`;
  document.body.appendChild(host);
  return true;
}
"""

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


def assert_covered(page, selectors):
    for selector in selectors:
        assert page.locator(selector).count() > 0, selector


# initPropertyViews still re-binds; brief 0505 makes this zero.
GUARD = "form[data-unsaved-guard]"
GUARD_KNOWN_EVENTS = ["invalid"]


def assert_second_run_adds_nothing(page):
    page.evaluate(RECORD_JS, SELECTORS)
    page.evaluate("() => window.UbyHost.initPage()")
    matched = [a for a in page.evaluate("() => window.__adds") if a[0] == "match"]
    guard_events = sorted(a[1] for a in matched if a[2] == GUARD)
    others = [a for a in matched if a[2] != GUARD]
    assert others == [], others
    guard_forms = page.locator(GUARD).count()
    assert guard_events == sorted(GUARD_KNOWN_EVENTS * guard_forms), guard_events


def test_second_init_page_run_binds_nothing_on_real_pages(calendar_workspace, calendar_origin):
    stay_id = seed(calendar_workspace)
    property_id = calendar_workspace["properties"][0]
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": calendar_workspace["client"].cookies.get(auth.SESSION_COOKIE), "url": calendar_origin + "/"}])
        paths = {
            "reservations": "/reservations?lang=cs",
            "reservation_detail": "/reservations/%s?lang=cs" % stay_id,
            "apartment": "/apartments/%s?lang=cs" % property_id,
        }
        for name, path in paths.items():
            page = open_page(context, calendar_origin, path)
            assert_covered(page, PAGE_SELECTORS[name])
            assert_second_run_adds_nothing(page)
            page.close()
        context.close()
        browser.close()


def test_second_init_page_run_binds_nothing_on_injected_controls(calendar_workspace, calendar_origin):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": calendar_workspace["client"].cookies.get(auth.SESSION_COOKIE), "url": calendar_origin + "/"}])
        page = open_page(context, calendar_origin, "/reservations?lang=cs")
        page.evaluate(INJECT_JS)
        page.evaluate("() => window.UbyHost.initPage()")
        assert_covered(page, ["form[data-auto-submit]", "[data-generate-password]", "#reset-password-dialog", "[data-toast]"])
        assert_second_run_adds_nothing(page)
        context.close()
        browser.close()
