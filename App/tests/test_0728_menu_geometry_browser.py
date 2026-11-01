"""0728: the phone Menu keeps its row, second-line and log-out geometry at 320 to 768 px."""
from __future__ import annotations

from app import auth
from tests.test_0710_v2_mockup_match_browser import _open_app
from tests.test_host_quiet_dashboard_browser import (  # the quiet overview's fixtures and helpers
    _launch,
    base,
    dashboard_host,
    dashboard_rich_host,
    sync_api,
)

import pytest

__all__ = ["base", "dashboard_host", "dashboard_rich_host"]

WIDTHS = (320, 360, 390, 768)
IDS = [f"menu-{width}" for width in WIDTHS]

MEASURE = """() => {
  const rows = [...document.querySelectorAll('.menu-list .row, .menu-logout .row')].map(el => {
    const b = el.getBoundingClientRect();
    return {h: b.height, l: b.left, r: b.right};
  });
  const smalls = [...document.querySelectorAll('.menu-list .row .t small')].map(el => {
    const cs = getComputedStyle(el);
    const fs = parseFloat(cs.fontSize);
    const lh = cs.lineHeight === 'normal' ? fs * 1.4 : parseFloat(cs.lineHeight);
    const text = el.closest('.t');
    const tRight = text.getBoundingClientRect().right;
    const next = [];
    for (let n = text.nextElementSibling; n; n = n.nextElementSibling) {
      if (n.getBoundingClientRect().width > 0) next.push(n.getBoundingClientRect().left);
    }
    return {h: el.getBoundingClientRect().height, lh: lh, tRight: tRight,
            nextLeft: next.length ? Math.min(...next) : null, label: el.textContent.trim()};
  });
  const menu = document.querySelector('.menu-list');
  const logout = document.querySelector('.menu-logout');
  return {
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    rows: rows,
    smalls: smalls,
    menuBottom: menu.getBoundingClientRect().bottom,
    logoutTop: logout.getBoundingClientRect().top,
  };
}"""

TAB_AND_LOGOUT_END = """() => {
  const tab = document.querySelector('.ui-tabbar');
  const logout = document.querySelector('.menu-logout');
  return {
    logoutBottom: logout.getBoundingClientRect().bottom,
    tabTop: tab && tab.getBoundingClientRect().width > 0 ? tab.getBoundingClientRect().top : null,
  };
}"""


@pytest.mark.parametrize("width", WIDTHS, ids=IDS)
def test_menu_geometry(width, base, dashboard_rich_host):
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, cookie, "/menu", width)
        measured = page.evaluate(MEASURE)
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        at_end = page.evaluate(TAB_AND_LOGOUT_END)
        context.close()
        browser.close()

    problems = []
    if measured["scrollWidth"] > measured["innerWidth"]:
        problems.append(f"horizontal overflow: scrollWidth {measured['scrollWidth']} > {measured['innerWidth']}")
    first = measured["rows"][0]
    for index, row in enumerate(measured["rows"]):
        if row["h"] < 56:
            problems.append(f"row {index} is {row['h']:.1f} px tall (< 56)")
        if abs(row["l"] - first["l"]) > 1 or abs(row["r"] - first["r"]) > 1:
            problems.append(f"row {index} edges {row['l']:.1f}-{row['r']:.1f} differ from row 0 {first['l']:.1f}-{first['r']:.1f}")
    for small in measured["smalls"]:
        if small["h"] > small["lh"] + 1:
            problems.append(f"second line wraps: {small['label']!r} is {small['h']:.1f} px tall")
        if small["nextLeft"] is not None and small["tRight"] > small["nextLeft"] + 1:
            problems.append(f"second line {small['label']!r} runs into the next element")
    gap = measured["logoutTop"] - measured["menuBottom"]
    if gap < 12:
        problems.append(f"log-out card is {gap:.1f} px below the menu (< 12)")
    if at_end["tabTop"] is not None and at_end["logoutBottom"] > at_end["tabTop"]:
        problems.append(f"log-out card bottom {at_end['logoutBottom']:.1f} is under the tab bar top {at_end['tabTop']:.1f}")
    assert not problems, f"menu at {width} px: {len(problems)} findings\n" + "\n".join(problems)
