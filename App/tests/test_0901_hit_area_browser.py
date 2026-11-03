"""0901 guardrail: a click on a link or button lands on it, never on an invisible overlay from a stretched-link rule (real Chromium)."""
from __future__ import annotations

import os

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from tests.test_0508_page_swap_browser import new_context, seed
from tests.test_dashboard_calendar_browser import calendar_origin, calendar_workspace, launch  # noqa: F401,F811

PAGES = ["/?lang=en", "/?cal_view=calendar", "/reservations", "/stay-fees", "/apartments", "/cleaning", "/payments", "/settings"]

# Every visible link/button: the element at its centre must be itself or inside it (or contain it), and no
# absolutely positioned pseudo-element of it may reach beyond its own box by more than 4 px.
HIT_JS = """
() => {
  const bad = [];
  const sel = 'a[href], button, [role=button], summary, input:not([type=hidden]), select';
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2 || getComputedStyle(el).visibility === 'hidden') continue;
    if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
    if (el.closest('[inert], [hidden], dialog:not([open])')) continue;
    const x = Math.min(Math.max(r.left + r.width / 2, 0), innerWidth - 1);
    const y = Math.min(Math.max(r.top + r.height / 2, 0), innerHeight - 1);
    const hit = document.elementFromPoint(x, y);
    const label = (el.tagName + '.' + (el.className || '') + ' ' + (el.textContent || '').trim().slice(0, 30)).slice(0, 90);
    if (hit && !(el === hit || el.contains(hit) || hit.contains(el) || el.closest('label') === hit.closest('label'))) {
      bad.push('covered: ' + label + ' by ' + hit.tagName + '.' + hit.className);
    }
    for (const pseudo of ['::before', '::after']) {
      const cs = getComputedStyle(el, pseudo);
      if (cs.content === 'none' || cs.position !== 'absolute') continue;
      const host = [...[el], ...[]].find(Boolean);
      // the containing block of the pseudo-element: nearest positioned ancestor (el itself if positioned)
      let cb = el;
      while (cb && getComputedStyle(cb).position === 'static') cb = cb.parentElement;
      const cr = cb ? cb.getBoundingClientRect() : { width: innerWidth, height: innerHeight };
      const w = parseFloat(cs.width), h = parseFloat(cs.height);
      if (cb !== el && (w > r.width + 4 || h > r.height + 4) && (cr.width * cr.height) > 4 * r.width * r.height && w * h > 4 * r.width * r.height) {
        bad.push('overlay ' + pseudo + ' of ' + label + ' is ' + Math.round(w) + 'x' + Math.round(h) + ' vs box ' + Math.round(r.width) + 'x' + Math.round(r.height));
      }
    }
  }
  return bad;
}
"""


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_no_overlay_swallows_clicks(calendar_workspace, calendar_origin, width):
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = context.new_page()
        page.set_viewport_size({"width": width, "height": 900})
        problems = []
        for path in PAGES:
            page.goto(calendar_origin + path)
            page.wait_for_load_state()
            problems += [f"{path}: {p}" for p in page.evaluate(HIT_JS)]
        browser.close()
    assert not problems, problems[:10]


def test_guardrail_catches_a_page_sized_overlay(calendar_workspace, calendar_origin):
    """Self-check: the old bug (static button, absolute inset:0 overlay, unpositioned card) is reported."""
    seed(calendar_workspace)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = new_context(browser, calendar_workspace, calendar_origin)
        page = context.new_page()
        page.goto(calendar_origin + "/reservations")
        page.wait_for_load_state()
        page.add_style_tag(content=".host-workspace a.btn::before,#app-sidebar a::before{content:'';position:absolute;inset:0}")
        found = page.evaluate(HIT_JS)
        browser.close()
    assert found, "the guardrail missed a page-sized overlay"
