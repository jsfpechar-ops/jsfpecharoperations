"""0091: normal stays fit the content lane at every width and sidebar state."""
from __future__ import annotations

import json
import os
from pathlib import Path

from app import auth
from tests.test_host_stay_actions_browser import (  # noqa: F401  (fixtures)
    _browser, stay_actions_base, stay_actions_host, sync_api,
)

WIDTHS = (360, 390, 760, 1024, 1280, 1440, 1680, 1920, 2048)
EVIDENCE_WIDTHS = (360, 390, 760, 1024, 1280, 1440, 1920)
EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "0091-evidence"

MEASURE = """() => {
  const view = document.querySelector('.stays-view');
  const v = view.getBoundingClientRect();
  const rows = [...view.querySelectorAll('tbody tr')].map(tr => {
    const items = [...tr.querySelectorAll('td, td a, td button, td .pill, td .deadline')]
      .filter(el => el.offsetParent !== null && el.getBoundingClientRect().width > 0 && !el.closest('.row-menu-panel') && !el.classList.contains('sr-only'));
    const rects = items.map(el => { const r = el.getBoundingClientRect();
      return {tag: el.tagName, cls: el.className, left: r.left, right: r.right, top: r.top, bottom: r.bottom,
              font: parseFloat(getComputedStyle(el).fontSize)}; });
    const actions = [...tr.querySelectorAll('td.row-actions button, td.row-actions .row-menu-trigger')]
      .filter(el => el.offsetParent !== null && !el.closest('.row-menu-panel'))
      .map(el => { const r = el.getBoundingClientRect(); return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, h: r.height}; });
    return {rects, actions, height: tr.getBoundingClientRect().height};
  });
  const sc = document.documentElement;
  return {viewLeft: v.left, viewRight: v.right, viewScroll: view.scrollWidth, viewClient: view.clientWidth,
          docScroll: sc.scrollWidth, tableScroll: view.querySelector('table').scrollWidth,
          overflow: getComputedStyle(view).overflowX, rows,
          header: getComputedStyle(view.querySelector('thead')).display !== 'none'};
}"""


def _set_sidebar(page, collapsed: bool) -> bool:
    toggle = page.locator("button[data-sidebar-collapse]")
    if not toggle.count() or not toggle.first.is_visible():
        return False
    now = page.evaluate("document.body.classList.contains('sidebar-collapsed')")
    if now != collapsed:
        toggle.first.click()
        page.wait_for_function(
            f"document.body.classList.contains('sidebar-collapsed') === {str(collapsed).lower()}"
        )
    return True


def test_stays_fit_lane_at_every_width_and_sidebar_state(stay_actions_host, stay_actions_base):
    cookie = stay_actions_host["client"].cookies.get(auth.SESSION_COOKIE)
    capture = os.environ.get("UBYHOST_CAPTURE_0091") == "1"
    matrix = []
    with sync_api.sync_playwright() as playwright:
        browser = _browser(playwright)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": stay_actions_base + "/"}])
        page = context.new_page()
        for locale in ("en", "cs"):
            for collapsed in (False, True):
                for width in WIDTHS:
                    page.set_viewport_size({"width": width, "height": 900})
                    page.goto(f"{stay_actions_base}/reservations?range=all&lang={locale}")
                    page.wait_for_load_state("networkidle")
                    has_sidebar = _set_sidebar(page, collapsed)
                    if not has_sidebar and collapsed:
                        continue
                    page.wait_for_timeout(80)
                    m = page.evaluate(MEASURE)
                    if capture and width in EVIDENCE_WIDTHS:
                        EVIDENCE.mkdir(parents=True, exist_ok=True)
                        name = f"stays-{width}-{locale}-{'collapsed' if collapsed else 'expanded'}.png"
                        page.locator(".stays-view").first.screenshot(path=str(EVIDENCE / name))
                    state = f"{locale}/{width}/{'collapsed' if collapsed else 'expanded'}"
                    lane = round(m["viewClient"])
                    matrix.append({"locale": locale, "width": width,
                                   "sidebar": "collapsed" if collapsed else "expanded",
                                   "lane": lane, "docScroll": m["docScroll"], "viewScroll": m["viewScroll"],
                                   "mode": "row" if m["header"] else "card",
                                   "rowHeights": [round(r["height"]) for r in m["rows"]]})
                    assert m["overflow"] not in ("auto", "scroll"), state
                    assert m["viewScroll"] <= m["viewClient"] + 1, (state, m["viewScroll"], m["viewClient"])
                    assert m["tableScroll"] <= m["viewClient"] + 1, state
                    assert m["docScroll"] <= width + 1, (state, m["docScroll"])
                    # The fixture holds 8 stays; the list shows one page of 5 (owner-approved page size).
                    assert len(m["rows"]) >= 5, state
                    # One row per stay with a header from the 1024px viewport breakpoint (the bordered panel narrows
                    # the lane to 894-896px there), compact cards below.
                    assert m["header"] == (width >= 1024), (state, lane)
                    heights = sorted(r["height"] for r in m["rows"])
                    median = heights[(len(heights) - 1) // 2]  # lower median: Send rows may wrap in CS
                    # Roomy rows (0191): --row-h 80px plus 16px cell padding gives a one-line stay row of 98px
                    # (old budget: 72px for a 64px row, the same 8px slack above the measured height).
                    assert median <= (106 if m["header"] else (160 if lane >= 600 else 200)), (state, lane, heights)
                    if m["header"]:
                        assert heights[-1] <= 125, (state, heights)
                        assert heights[0] >= 80, (state, heights)  # never shorter than the --row-h token
                    for row in m["rows"]:
                        for r in row["rects"]:
                            assert r["left"] >= m["viewLeft"] - 1 and r["right"] <= m["viewRight"] + 1, (state, r)
                            assert r["font"] >= 11, (state, r)
                        actions = row["actions"]
                        for i, a in enumerate(actions):
                            for b in actions[i + 1:]:
                                assert (a["right"] <= b["left"] + 1 or b["right"] <= a["left"] + 1
                                        or a["bottom"] <= b["top"] + 1 or b["bottom"] <= a["top"] + 1), (state, a, b)
        context.close()
        browser.close()
    assert {item["mode"] for item in matrix} == {"row", "card"}
    if capture:
        (EVIDENCE / "measurements.json").write_text(json.dumps(matrix, indent=1))
