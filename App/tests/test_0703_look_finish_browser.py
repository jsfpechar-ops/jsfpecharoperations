"""0703: the Overview finishes the look at computer width: warm canvas, calm headings, account card at the top."""
from __future__ import annotations

from app import auth
from tests.test_host_quiet_dashboard_browser import (  # the quiet overview's fixtures and helpers
    _launch,
    _open,
    base,
    dashboard_host,
    dashboard_rich_host,
    sync_api,
)

__all__ = ["base", "dashboard_host", "dashboard_rich_host"]

ANCESTORS_JS = """
(sel) => {
  const out = [];
  let el = document.querySelector(sel);
  while (el) {
    out.push(el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + ' .' + String(el.className).split(' ').filter(Boolean).join('.') + ' ' + getComputedStyle(el).backgroundColor);
    el = el.parentElement;
  }
  return out;
}
"""

NEAREST_BG_JS = """
(sel) => {
  let el = document.querySelector(sel).parentElement;
  while (el) {
    const bg = getComputedStyle(el).backgroundColor;
    if (bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return bg;
    el = el.parentElement;
  }
  return null;
}
"""


def test_canvas_shows_behind_the_cards_at_1280(dashboard_rich_host, base):
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page, errors = _open(browser, base, cookie, "cs", 1280)
        assert not errors, errors
        chain = page.evaluate(ANCESTORS_JS, ".needs-you")
        bg = page.evaluate(NEAREST_BG_JS, ".needs-you")
        assert bg == "rgb(246, 246, 244)", (bg, chain)
        browser.close()


def test_needs_you_heading_is_calm_at_1280(dashboard_rich_host, base):
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page, errors = _open(browser, base, cookie, "cs", 1280)
        assert not errors, errors
        size = page.locator(".needs-you > h2").first.evaluate("el => getComputedStyle(el).fontSize")
        assert size == "16px", size
        browser.close()


def test_account_card_sits_above_the_nav_at_1280(dashboard_rich_host, base):
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page, errors = _open(browser, base, cookie, "cs", 1280)
        assert not errors, errors
        account = page.locator(".host-account").first.bounding_box()
        nav = page.locator("#app-sidebar nav a[href]").first.bounding_box()
        assert account and nav, (account, nav)
        assert account["y"] < nav["y"], (account, nav)
        browser.close()
