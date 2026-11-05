"""0955 step 8: click-through audit of the property page at 390, 768 and 1280 px.

Opens every section, measures overflow, small targets, fields hidden under the
Save row, and the Save row's position. Screenshots go to UBYHOST_AUDIT_SHOTS
(default: a temporary folder). Synthetic data only. Chromium only here.
"""
from __future__ import annotations

import os

import pytest

from tests.test_host_unsaved_changes_browser import _page, base, browser, host  # noqa: F401

WIDTHS = [(390, 844), (768, 1024), (1280, 900)]
BAR = ".savebar[data-for='property-settings-form']"
MEASURE = """() => {
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
  const small = [], wide = [];
  document.querySelectorAll('.property-settings-form .btn, .property-settings-form .ui-btn, .prop-sec > summary, .savebar .btn').forEach(el => {
    if (!vis(el)) return;
    const r = el.getBoundingClientRect();
    if (r.height < 43) small.push(((el.textContent || '').trim().slice(0, 30)) + ' ' + Math.round(r.height));
  });
  document.querySelectorAll('.property-settings-form input, .property-settings-form select, .property-settings-form textarea, .property-settings-form .btn').forEach(el => {
    if (!vis(el)) return;
    const r = el.getBoundingClientRect();
    if (r.right > innerWidth + 1 || r.left < -1) wide.push(el.id || el.name || el.tagName);
  });
  return {sw: document.documentElement.scrollWidth, iw: innerWidth, small, wide};
}"""
COVER = """(id) => {
  const el = document.getElementById(id), bar = document.querySelector(".savebar[data-for='property-settings-form']");
  if (!el || !bar) return null;
  el.focus();
  const f = el.getBoundingClientRect(), b = bar.getBoundingClientRect();
  const under = bar.offsetParent !== null && f.bottom > b.top + 1 && f.top < b.bottom - 1 && getComputedStyle(bar).display !== 'none';
  return {under, field: Math.round(f.top), bar: Math.round(b.top)};
}"""


@pytest.mark.parametrize("width,height", WIDTHS)
def test_property_page_click_through_audit(browser, base, host, width, height, tmp_path):  # noqa: F811
    shots = os.environ.get("UBYHOST_AUDIT_SHOTS") or str(tmp_path)
    os.makedirs(shots, exist_ok=True)
    url = f"{base}/apartments/{host['apartment']}"
    page = _page(browser, base, host, width, height)
    page.goto(f"{url}?view=settings&section=property&lang=en")
    problems = []
    page.evaluate("() => document.querySelectorAll('details.prop-sec').forEach(d => { d.open = true; })")
    page.wait_for_timeout(200)
    page.screenshot(path=f"{shots}/audit-{width}-1-open.png", full_page=False)
    m = page.evaluate(MEASURE)
    if m["sw"] > m["iw"]:
        problems.append(f"{width}: horizontal scroll {m['sw']} > {m['iw']}")
    if m["small"]:
        problems.append(f"{width}: targets under 44 px: {m['small'][:5]}")
    if m["wide"]:
        problems.append(f"{width}: controls outside the viewport: {m['wide'][:5]}")
    page.fill("#internal_name", "Audit O1 draft")
    page.wait_for_timeout(200)
    bar = page.locator(BAR)
    assert bar.is_visible(), "the Save row is not visible after an edit"
    bb = bar.bounding_box()
    if bb["y"] + bb["height"] > height + 1:
        problems.append(f"{width}: Save row below the viewport")
    page.screenshot(path=f"{shots}/audit-{width}-2-dirty.png", full_page=False)
    for field in ["internal_name", "addr_house_no", "addr_zip", "addr_obec"]:
        result = page.evaluate(COVER, field)
        if result and result["under"]:
            problems.append(f"{width}: #{field} sits under the Save row")
    page.evaluate("() => document.getElementById('addr_zip') && document.getElementById('addr_zip').focus()")
    page.wait_for_timeout(200)
    page.screenshot(path=f"{shots}/audit-{width}-3-focus.png", full_page=False)
    assert not problems, "; ".join(problems)
    page.context.close()
