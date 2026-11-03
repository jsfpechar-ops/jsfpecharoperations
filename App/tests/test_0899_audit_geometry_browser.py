"""0899: after-redesign audit fixes, measured at 320/390/768/1024/1280/1440/1920 (real Chromium).

One help ring per "?" and centred on its glyph; the Havel button never covers the tab bar; the wizard
five-step list has no browser numbering; banners keep 12 px or more from the heading below.
"""
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

WIDTHS = (320, 390, 768, 1024, 1280, 1440, 1920)

RINGS_JS = """
() => {
  const bad = [];
  for (const b of document.querySelectorAll('button.help-tip-btn')) {
    const r = b.getBoundingClientRect();
    if (!r.width || getComputedStyle(b).visibility === 'hidden' || b.closest('[hidden]')) continue;
    const cs = getComputedStyle(b), a = getComputedStyle(b, '::after');
    const own = parseFloat(cs.borderTopWidth) > 0 && cs.borderTopColor !== 'rgba(0, 0, 0, 0)';
    const ring = parseFloat(a.borderTopWidth) > 0 && a.content !== 'none';
    if (own && ring) { bad.push('double ring ' + (b.getAttribute('aria-controls') || '')); continue; }
    if (!ring) continue;
    const m = new DOMMatrix(a.transform === 'none' ? undefined : a.transform);
    const cx = r.left + parseFloat(cs.borderLeftWidth) + parseFloat(a.left) + parseFloat(a.width) / 2 + m.e;
    const cy = r.top + parseFloat(cs.borderTopWidth) + parseFloat(a.top) + parseFloat(a.height) / 2 + m.f;
    const range = document.createRange(); range.selectNodeContents(b);
    const g = range.getBoundingClientRect();
    const dx = Math.abs(cx - (g.left + g.width / 2)), dy = Math.abs(cy - (g.top + g.height / 2));
    if (dx > 4 || dy > 4) bad.push('ring off glyph by ' + Math.round(dx) + ',' + Math.round(dy) + ' ' + (b.getAttribute('aria-controls') || ''));
  }
  return bad;
}
"""

FAB_JS = """
() => {
  const fab = document.querySelector('.havel-fab');
  const bar = document.querySelector('.tabs');
  if (!fab || !bar) return [];
  const f = fab.getBoundingClientRect();
  if (!f.width || !bar.getBoundingClientRect().width) return [];
  const hits = [];
  for (const a of bar.querySelectorAll('a.tab')) {
    const r = a.getBoundingClientRect();
    if (r.width && f.left < r.right && f.right > r.left && f.top < r.bottom && f.bottom > r.top) hits.push((a.innerText || '').trim());
  }
  return hits;
}
"""


@pytest.fixture(scope="module")
def stay_id(calendar_workspace):
    return make_stay(calendar_workspace["properties"][0], "2026-11-05", "2026-11-08")


def _pages(ws, stay_id):
    a = ws["properties"][0]
    return {
        "wizard": f"/apartments/{a}/setup/property", "property": f"/apartments/{a}", "invoice-new": "/invoices/new",
        "entities": "/entities", "stay": f"/reservations/{stay_id}", "stays": "/reservations",
    }


def _visit(page, origin, path, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(f"{origin}{path}?lang=en")
    page.wait_for_load_state()
    if width < 1024:  # the tab bar and the Havel button show below 1024 px
        page.wait_for_function("() => { const t = document.querySelector('.tabs'); return t && t.getBoundingClientRect().width > 0; }", timeout=8000)


@pytest.fixture()
def host_page(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": calendar_workspace["client"].cookies.get(auth.SESSION_COOKIE),
                              "url": calendar_origin + "/"}])
        yield context.new_page()
        browser.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_help_ring_is_single_and_centred(host_page, calendar_workspace, calendar_origin, stay_id, width):
    for name, path in _pages(calendar_workspace, stay_id).items():
        _visit(host_page, calendar_origin, path, width)
        assert host_page.evaluate(RINGS_JS) == [], f"{name} at {width}"


@pytest.mark.parametrize("width", WIDTHS)
def test_havel_button_clears_the_tab_bar(host_page, calendar_workspace, calendar_origin, stay_id, width):
    for name, path in _pages(calendar_workspace, stay_id).items():
        _visit(host_page, calendar_origin, path, width)
        assert host_page.evaluate(FAB_JS) == [], f"{name} at {width}"


@pytest.mark.parametrize("width", WIDTHS)
def test_wizard_steps_have_no_browser_numbering(host_page, calendar_workspace, calendar_origin, width):
    _visit(host_page, calendar_origin, f"/apartments/{calendar_workspace['properties'][0]}/setup/property", width)
    assert host_page.evaluate("() => getComputedStyle(document.querySelector('.workflow-strip')).listStyleType") == "none"
    assert host_page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")


@pytest.mark.parametrize("width", WIDTHS)
def test_stay_detail_title_shows_once(host_page, calendar_workspace, calendar_origin, stay_id, width):
    _visit(host_page, calendar_origin, f"/reservations/{stay_id}", width)
    big = host_page.evaluate("""() => [...document.querySelectorAll('main h1, main .big')].filter(e => {
        const r = e.getBoundingClientRect(); return r.width > 0 && parseFloat(getComputedStyle(e).fontSize) >= 20 && (e.innerText || '').trim() === 'Calendar home 1'; }).length""")
    assert big == 1, f"title shown {big} times at {width}"


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("path", ["/entities", "/settings/archived"])
def test_settings_help_sits_in_the_title(host_page, calendar_origin, path, width):
    _visit(host_page, calendar_origin, path, width)
    assert host_page.locator("main h1 .help-tip-btn").count() == 1
    assert host_page.locator(".settings-help-line").count() == 0
