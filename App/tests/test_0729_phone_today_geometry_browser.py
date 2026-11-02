"""0729: the phone Overview (Today) keeps its pill switch, headline, need cards and stay cards at 320 to 768 px."""
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
IDS = [f"today-{width}" for width in WIDTHS]

MEASURE = """() => {
  const vis = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'; };
  const box = el => { const r = el.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; };
  const W = window.innerWidth;
  const seg = document.querySelector('.seg');
  const segOn = !!seg && vis(seg);
  const links = segOn ? [...seg.querySelectorAll('a')].filter(vis).map(box) : [];
  const hl = document.querySelector('.hl');
  const hlOn = !!hl && vis(hl);
  const hlCs = hlOn ? getComputedStyle(hl) : null;
  const needs = [...document.querySelectorAll('.card.need')].filter(vis).map(card => {
    const btn = card.querySelector('.btn');
    return {box: box(card), radius: getComputedStyle(card).borderRadius,
            btn: btn ? box(btn) : null, btnVis: !!btn && vis(btn)};
  });
  const icVisible = [...document.querySelectorAll('.need .ic')].some(vis);
  const stays = [...document.querySelectorAll('.hs .card')].filter(vis).map(card => {
    const av = card.querySelector('.av');
    return {box: box(card), av: av ? box(av) : null};
  });
  const hidden = sel => { const el = document.querySelector(sel); return !el || !vis(el); };
  const main = document.querySelector('main');
  let mainBottom = 0;
  if (main) for (const el of main.querySelectorAll('*')) { if (vis(el)) mainBottom = Math.max(mainBottom, el.getBoundingClientRect().bottom); }
  const tabs = document.querySelector('.tabs');
  return {
    scrollWidth: document.documentElement.scrollWidth, innerWidth: W,
    seg: segOn ? box(seg) : null, links: links,
    hl: hlOn ? {box: box(hl), align: hlCs.textAlign, size: hlCs.fontSize} : null,
    ovSub: hidden('.ov-head .sub'), ovQuiet: hidden('.ov-head .ov-quiet'), ovBtn: hidden('.ov-head > .btn'),
    ovH1Hidden: hidden('.ov-head h1.hl'), ovMonth: hidden('.ov-month'), needsTitle: hidden('#needs-you-title'),
    ovTopCount: document.querySelectorAll('.ov-top').length,
    needs: needs, icVisible: icVisible, stays: stays,
    mainBottom: mainBottom, tabTop: tabs && vis(tabs) ? tabs.getBoundingClientRect().top : null,
  };
}"""


@pytest.mark.parametrize("width", WIDTHS, ids=IDS)
def test_today_phone_geometry(width, base, dashboard_rich_host):
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, cookie, "/", width)
        measured = page.evaluate(MEASURE)
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        at_end = page.evaluate(MEASURE)
        context.close()
        browser.close()

    problems = []
    W = measured["innerWidth"]
    if measured["scrollWidth"] > W:
        problems.append(f"horizontal overflow: scrollWidth {measured['scrollWidth']} > {W}")
    seg = measured["seg"]
    if seg is None:
        problems.append(".seg is not visible")
    else:
        if abs(seg["l"] - (W - seg["r"])) > 2:
            problems.append(f"pill switch off centre: left {seg['l']:.1f}, right {W - seg['r']:.1f}")
        for link in measured["links"]:
            if link["h"] < 44:
                problems.append(f"pill {link['h']:.1f} px tall (< 44)")
    hl = measured["hl"]
    if hl is None:
        problems.append(".hl is not visible")
    else:
        if hl["align"] != "center":
            problems.append(f"headline text-align {hl['align']} (want center)")
        if hl["size"] != "30px":
            problems.append(f"headline font-size {hl['size']} (want 30px)")
        if hl["box"]["r"] > W + 0.5:
            problems.append(f"headline overflows: right {hl['box']['r']:.1f} > {W}")
    for key, label in (("ovSub", ".ov-head .sub"), ("ovQuiet", ".ov-head .ov-quiet"), ("ovBtn", ".ov-head > .btn"), ("ovMonth", ".ov-month"), ("needsTitle", "#needs-you-title")):
        if not measured[key]:
            problems.append(f"{label} is visible on phone")
    if measured["ovH1Hidden"]:
        problems.append(".ov-head h1.hl is not visible on phone")
    if measured["ovTopCount"]:
        problems.append(".ov-top is in the phone markup")
    for index, card in enumerate(measured["needs"]):
        if card["radius"] != "24px":
            problems.append(f"need card {index} radius {card['radius']} (want 24px)")
        if not card["btnVis"]:
            problems.append(f"need card {index} has no visible button")
            continue
        btn, cw = card["btn"], card["box"]["w"]
        if btn["w"] < cw - 2 * 22 - 2:
            problems.append(f"need card {index} button {btn['w']:.1f} px wide, card {cw:.1f} px")
        if btn["h"] < 44:
            problems.append(f"need card {index} button {btn['h']:.1f} px tall (< 44)")
    if measured["icVisible"]:
        problems.append(".need .ic is visible")
    for index, stay in enumerate(measured["stays"]):
        if abs(stay["box"]["l"] - (W - stay["box"]["r"])) > 2:
            problems.append(f"stay card {index} off centre")
        if stay["box"]["r"] > W + 0.5:
            problems.append(f"stay card {index} overflows the viewport")
        av = stay["av"]
        if av is None or abs(av["w"] - 72) > 0.5 or abs(av["h"] - 72) > 0.5:
            problems.append(f"stay card {index} avatar is not 72x72")
    if at_end["tabTop"] is None:
        problems.append("tab bar is not visible on phone")
    elif at_end["mainBottom"] > at_end["tabTop"]:
        problems.append(f"content bottom {at_end['mainBottom']:.1f} is under the tab bar top {at_end['tabTop']:.1f}")
    assert not problems, f"today at {width} px: {len(problems)} findings\n" + "\n".join(problems)


def test_today_desktop_keeps_overview_head(base, dashboard_rich_host):
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, cookie, "/", 1280)
        assert not page.locator(".ph-top").first.is_visible()
        assert page.locator(".ov-head").first.is_visible()
        context.close()
        browser.close()
