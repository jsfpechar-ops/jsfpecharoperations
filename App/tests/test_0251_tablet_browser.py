"""Task 0251: iPad touch behaviour of the property overview and the tablet menu.

Between 1024 and 1279 px the rail stays the default; the toggle opens the full
menu over the page. Overview cards must be tappable on touch screens.
"""
from __future__ import annotations

import os
from pathlib import Path

from app import auth
from tests.test_property_navigation_browser import (  # noqa: F401
    _STATE_JS,
    base,
    chromium_launch_kwargs,
    host,
    sync_api,
)

IPAD = (
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
VIEWPORTS = [(1180, 820), (1024, 1366), (820, 1180)]
SHOTS = os.environ.get("UBYHOST_SHOTS_DIR")

CARD_JS = """() => {
  const hit = (x, y) => {
    const el = document.elementFromPoint(x, y);
    return !!(el && el.closest('a, .host-property-card-actions'));
  };
  return [...document.querySelectorAll('.host-property-card')].map(card => {
    const r = card.getBoundingClientRect();
    const pill = card.querySelector('.host-property-card-open');
    const p = pill ? pill.getBoundingClientRect() : r;
    return {
      text: card.textContent.trim().slice(0, 30),
      centre: hit(r.left + r.width / 2, r.top + r.height / 2),
      corner: hit(r.left + 8, r.top + 8),
      pill: hit(p.left + p.width / 2, p.top + p.height / 2),
    };
  });
}"""


def _context(browser, base, host, width, height):
    context = browser.new_context(
        viewport={"width": width, "height": height},
        has_touch=True,
        is_mobile=True,
        user_agent=IPAD,
    )
    context.add_cookies([{
        "name": auth.SESSION_COOKIE,
        "value": host["client"].cookies.get(auth.SESSION_COOKIE),
        "url": base + "/",
    }])
    return context


def _visible_groups(page):
    return page.evaluate(_STATE_JS)["visibleGroups"]


def _shot(page, name, full_page=True):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / f"0251-{name}.png"), full_page=full_page)


def _sidebar_width(page):
    return page.locator("#app-sidebar").bounding_box()["width"]


def _wait_sidebar(page, wide):
    # The rail animates; wait for the end width instead of a fixed sleep.
    page.wait_for_function(
        "wide => { const w = document.querySelector('#app-sidebar').getBoundingClientRect().width;"
        " return wide ? w >= 200 : w < 100; }",
        arg=wide, timeout=5000)


def test_overview_cards_and_tablet_menu_on_touch(host, base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width, height in VIEWPORTS:
            url = f"{base}/apartments/{host['apartment']}?view=overview&lang=en"
            context = _context(browser, base, host, width, height)
            page = context.new_page()
            page.goto(url)
            page.wait_for_timeout(50)

            # 1. Every card can be hit at its centre, corner and Open pill.
            cards = page.evaluate(CARD_JS)
            assert cards, f"no overview cards at {width}px"
            for card in cards:
                assert card["centre"] and card["corner"] and card["pill"], (width, card)
            fits = page.evaluate(
                "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"
            )
            assert fits, f"horizontal scroll at {width}px"
            _shot(page, f"overview-{width}")

            # 2. Tapping the guest card opens the guests group; police reporting
            #    opens the reporting group.
            page.locator(".host-property-card-static").tap(position={"x": 8, "y": 8})
            page.wait_for_url("**section=guests**")
            assert "guests" in _visible_groups(page), (width, _visible_groups(page))

            page.goto(url)
            page.wait_for_timeout(50)
            page.locator('a.host-property-card[href*="section=reporting#ubyport"]').tap(position={"x": 8, "y": 8})
            page.wait_for_url("**section=reporting**")
            assert "reporting" in _visible_groups(page), (width, _visible_groups(page))

            # 3. Only in the tablet rail range: the toggle opens and closes the full menu.
            if 1024 <= width <= 1279:
                page.goto(url)
                page.wait_for_timeout(50)
                toggle = page.locator("button[data-sidebar-collapse]")
                toggle.tap()
                _wait_sidebar(page, True)
                assert _sidebar_width(page) >= 200, width
                assert page.locator(".ui-nav a > span").first.is_visible(), width
                # A full-page shot resizes the viewport, which closes the menu (0370).
                _shot(page, f"menu-open-{width}", full_page=False)

                toggle.tap()
                _wait_sidebar(page, False)
                assert _sidebar_width(page) < 100, width

                toggle.tap()
                _wait_sidebar(page, True)
                assert _sidebar_width(page) >= 200, width
                page.tap("body", position={"x": 900, "y": 600})
                _wait_sidebar(page, False)
                assert _sidebar_width(page) < 100, width

            context.close()
        browser.close()
