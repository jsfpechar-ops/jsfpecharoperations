"""Dashboard and stay-list rows (0194): one clean box per row at every width, sidebar open or collapsed.

Guards: every cell and badge sits inside its row's box (no overflow), only the first and last cell of a
row carry a side border or radius (no per-cell boxes), and the number of row boxes equals the row count.
Set DASH_ROWS_SHOTS=1 (and DASH_ROWS_LANG=en|cs) to write screenshots to DASH_ROWS_SHOT_DIR.
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.test_dashboard_calendar import make_stay
from tests.test_dashboard_calendar_browser import calendar_origin, calendar_workspace, launch  # noqa: F401

GUARD_WIDTHS = (390, 700, 900, 1023, 1024, 1100, 1200, 1280, 1366, 1440, 1536, 2000)
LANG = os.environ.get("DASH_ROWS_LANG", "cs")
SHOT_DIR = pathlib.Path(os.environ.get("DASH_ROWS_SHOT_DIR", "/mnt/project-files/design-reset/checkpoint-4-shell-fixes"))
PATHS = (
    (f"/?lang={LANG}", "#needs-action table.ui-table", "dashboard"),
    (f"/reservations?lang={LANG}", "table.ui-table", "stays"),
)

METRICS_JS = """
(sel) => {
  const table = document.querySelector(sel);
  if (!table) return {error: 'no table'};
  const rows = [...table.querySelectorAll('tbody tr.ui-row')].filter(r => r.offsetParent !== null);
  const px = v => parseFloat(v) || 0;
  const res = {rows: rows.length, overflow: [], boxes: 0, midBorders: [],
    scroll: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    tableWidth: Math.round(table.getBoundingClientRect().width),
    trDisplay: rows.length ? getComputedStyle(rows[0]).display : null};
  rows.forEach((r, i) => {
    const rr = r.getBoundingClientRect();
    const cells = [...r.children];
    const rowCs = getComputedStyle(r);
    if (px(rowCs.borderTopWidth) > 0 || (cells[0] && px(getComputedStyle(cells[0]).borderLeftWidth) > 0)) res.boxes++;
    cells.forEach((td, j) => {
      const b = td.getBoundingClientRect();
      if (b.width && (b.left < rr.left - 0.5 || b.right > rr.right + 0.5)) res.overflow.push([i, j, Math.round(b.right - rr.right)]);
      td.querySelectorAll('.ui-badge, .pill, .row-menu-trigger, .ui-btn').forEach(el => {
        const eb = el.getBoundingClientRect();
        if (eb.width && (eb.right > rr.right + 0.5 || eb.left < rr.left - 0.5)) res.overflow.push([i, j, 'badge', Math.round(eb.right - rr.right)]);
      });
      const cs = getComputedStyle(td);
      if (j > 0 && j < cells.length - 1 && (px(cs.borderLeftWidth) || px(cs.borderRightWidth) || px(cs.borderTopLeftRadius))) res.midBorders.push([i, j]);
    });
  });
  return res;
}
"""

DETAIL_JS = """
(sel) => {
  const table = document.querySelector(sel);
  const tr = table.querySelector('tbody tr.ui-row');
  const pick = (el) => { const c = getComputedStyle(el); return {display: c.display, border: [c.borderTopWidth, c.borderRightWidth, c.borderBottomWidth, c.borderLeftWidth].join(' '), radius: c.borderTopLeftRadius, bg: c.backgroundColor, shadow: c.boxShadow, padding: c.padding, width: Math.round(el.getBoundingClientRect().width), left: Math.round(el.getBoundingClientRect().left)}; };
  return {table: pick(table), tr: pick(tr), cells: [...tr.children].map(pick), spacing: getComputedStyle(table).borderSpacing,
    sidebar: document.body.classList.contains('sidebar-collapsed'), section: pick(table.closest('.ui-section') || table)};
}
"""


def seed(ws):
    """Two overdue stays and one scheduled stay for the needs-action list."""
    properties = ws["properties"]
    make_stay(properties[0], "2026-10-01", "2026-10-03")
    make_stay(properties[1], "2026-10-02", "2026-10-04")
    make_stay(properties[2], "2026-11-05", "2026-11-08")


def open_page(browser, ws, origin, path, selector, width, collapsed):
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": ws["client"].cookies.get(auth.SESSION_COOKIE), "url": origin + "/"}])
    flag = "1" if collapsed else "0"
    context.add_init_script(f"try {{ localStorage.setItem('ubyhost-sidebar-collapsed', '{flag}'); }} catch (e) {{}}")
    page = context.new_page()
    page.goto(origin + path)
    page.wait_for_selector(selector, timeout=20000)
    page.wait_for_timeout(250)
    return context, page


@pytest.mark.parametrize("path, selector, name", PATHS)
def test_each_row_is_one_box_inside_its_row_at_every_width(calendar_workspace, calendar_origin, path, selector, name):
    seed(calendar_workspace)
    results, details = {}, {}
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        for collapsed in (False, True):
            for width in GUARD_WIDTHS:
                key = f"{width}-{'collapsed' if collapsed else 'open'}"
                context, page = open_page(browser, calendar_workspace, calendar_origin, path, selector, width, collapsed)
                results[key] = page.evaluate(METRICS_JS, selector)
                if width in (390, 1024, 1280, 2000):
                    details[key] = page.evaluate(DETAIL_JS, selector)
                if os.environ.get("DASH_ROWS_SHOTS"):
                    SHOT_DIR.mkdir(parents=True, exist_ok=True)
                    anchor = "#needs-action" if name == "dashboard" else selector
                    page.locator(anchor).first.screenshot(path=str(SHOT_DIR / f"{name}-rows-{width}-{key.split('-')[1]}-{LANG}.png"))
                context.close()
        browser.close()
    diag = os.environ.get("DASH_ROWS_DIAG")
    if diag:
        target = pathlib.Path(diag)
        target.with_name(f"{name}-{target.name}").write_text(json.dumps({"path": path, "results": results, "details": details}, indent=1))
    for key, metrics in results.items():
        assert metrics.get("rows", 0) >= 2, (key, metrics)
        assert not metrics.get("overflow"), (key, metrics)
        assert metrics["boxes"] == metrics["rows"], (key, metrics)
        assert not metrics.get("midBorders"), (key, metrics)
