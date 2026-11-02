"""0728/0735: the phone Menu keeps its title, tiles, promo card, plain rows and log-out geometry at 320 to 768 px."""
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
  const vis = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'; };
  const box = el => { const r = el.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; };
  const mh = document.querySelector('.mh');
  const big = document.querySelector('.mh .big');
  const av = document.querySelector('.me-av');
  const tiles = [...document.querySelectorAll('.tiles .tile')].filter(vis).map(box);
  const promo = document.querySelector('.promo');
  const pi = document.querySelector('.promo .pi');
  const rows = [...document.querySelectorAll('.list.plain .row')].map(el => {
    const first = el.querySelector(':scope > svg:first-child');
    const chev = el.querySelector('.chev');
    return {row: box(el), icon: first ? box(first) : null, chev: chev ? box(chev) : null,
            smalls: el.querySelectorAll('small').length, logout: !!el.closest('.menu-logout'),
            label: el.textContent.trim()};
  });
  const logout = document.querySelector('.menu-logout');
  const outside = [];
  const main = document.querySelector('main');
  if (main) for (const el of main.querySelectorAll('*')) {
    if (!vis(el)) continue;
    const hasText = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!hasText) continue;
    const r = el.getBoundingClientRect();
    if (r.left < -0.5 || r.right > window.innerWidth + 0.5) outside.push(el.textContent.trim().slice(0, 30));
  }
  const tabs = document.querySelector('.tabs');
  return {
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    bigFont: big ? parseFloat(getComputedStyle(big).fontSize) : null,
    mh: mh ? box(mh) : null,
    av: av ? box(av) : null,
    tiles: tiles,
    promo: promo ? box(promo) : null,
    pi: pi ? box(pi) : null,
    rows: rows,
    logoutBorder: logout ? getComputedStyle(logout).borderTopWidth : null,
    logoutTop: logout ? logout.getBoundingClientRect().top : null,
    outside: outside,
  };
}"""

TAB_AND_LOGOUT_END = """() => {
  const tab = document.querySelector('.tabs');
  const logout = document.querySelector('.menu-logout .row');
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
    mh = measured["mh"]
    if mh is None:
        problems.append("menu title block .mh is missing")
        mh = {"l": 0, "r": measured["innerWidth"]}
    if measured["bigFont"] is None or abs(measured["bigFont"] - 30) > 0.5:
        problems.append(f"title font-size is {measured['bigFont']} (not 30px)")
    av = measured["av"]
    if av is None:
        problems.append("avatar .me-av is missing")
    else:
        if abs(av["w"] - 44) > 1 or abs(av["h"] - 44) > 1:
            problems.append(f"avatar is {av['w']:.1f}x{av['h']:.1f} (not 44x44)")
        right_gap = measured["innerWidth"] - av["r"]
        if not 18 <= right_gap <= 22:
            problems.append(f"avatar right edge is {right_gap:.1f} px from the viewport edge (not 20)")
    tiles = measured["tiles"]
    if len(tiles) != 2:
        problems.append(f"expected 2 tiles, found {len(tiles)}")
    else:
        first, second = tiles
        if abs(first["w"] - second["w"]) > 1:
            problems.append(f"tile widths differ: {first['w']:.1f} and {second['w']:.1f}")
        for index, tile in enumerate(tiles):
            if abs(tile["h"] - 150) > 1:
                problems.append(f"tile {index} is {tile['h']:.1f} px tall (not 150)")
        if abs(first["t"] - second["t"]) > 1:
            problems.append("tiles are not side by side (different tops)")
        gap = second["l"] - first["r"]
        if abs(gap - 14) > 1:
            problems.append(f"tile gap is {gap:.1f} px (not 14)")
        if abs(first["l"] - mh["l"]) > 1 or abs(second["r"] - mh["r"]) > 1:
            problems.append("tiles do not span the content width")
    promo = measured["promo"]
    if promo is None:
        problems.append("promo card .promo is missing")
    elif abs(promo["l"] - mh["l"]) > 1 or abs(promo["r"] - mh["r"]) > 1:
        problems.append("promo card does not span the content width")
    pi = measured["pi"]
    if pi is None or abs(pi["w"] - 44) > 1 or abs(pi["h"] - 44) > 1:
        problems.append(f"promo icon box is not 44x44: {pi}")
    for index, row in enumerate(measured["rows"]):
        box = row["row"]
        if box["h"] < 56:
            problems.append(f"row {index} {row['label']!r} is {box['h']:.1f} px tall (< 56)")
        if abs(box["l"] - mh["l"]) > 1 or abs(box["r"] - mh["r"]) > 1:
            problems.append(f"row {index} {row['label']!r} does not span the content width")
        icon = row["icon"]
        if icon is None or abs(icon["w"] - 26) > 1 or abs(icon["h"] - 26) > 1:
            problems.append(f"row {index} {row['label']!r} icon is not 26x26")
        if row["smalls"]:
            problems.append(f"row {index} {row['label']!r} has a second line")
        if row["logout"]:
            if row["chev"] is not None:
                problems.append("log-out row has a chevron")
        else:
            chev = row["chev"]
            if chev is None:
                problems.append(f"menu row {index} {row['label']!r} has no chevron")
            elif abs(chev["r"] - box["r"]) > 2:
                problems.append(f"menu row {index} chevron is {abs(chev['r'] - box['r']):.1f} px from the row edge")
    menu_rows = [row["row"] for row in measured["rows"] if not row["logout"]]
    if not menu_rows:
        problems.append("no menu rows found")
    elif measured["logoutTop"] is None or measured["logoutTop"] <= max(box["b"] for box in menu_rows):
        problems.append("log-out block does not sit below the last menu row")
    if measured["logoutBorder"] != "1px":
        problems.append(f"log-out block top border is {measured['logoutBorder']} (not 1px)")
    if measured["outside"]:
        problems.append(f"text outside the viewport: {measured['outside'][:5]}")
    if at_end["tabTop"] is None:
        if width != 768:
            problems.append("tab bar is not visible on phone")
    elif at_end["logoutBottom"] > at_end["tabTop"]:
        problems.append(f"log-out row bottom {at_end['logoutBottom']:.1f} is under the tab bar top {at_end['tabTop']:.1f}")
    assert not problems, f"menu at {width} px: {len(problems)} findings\n" + "\n".join(problems)
