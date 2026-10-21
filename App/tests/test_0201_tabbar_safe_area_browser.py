"""0201: the phone tab bar clears the home indicator and the rounded corners (viewport-fit=cover, safe-area padding)."""
import os
import secrets

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401

SHOT_DIR = "/mnt/project-files/design-reset/checkpoint-6/mobile/tabbar/"


def _open(playwright, base, width, height, target):
    username = f"tabbar{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Tabbar", role="host", username=username)
    db.insert("apartment", {"internal_name": "Tabbar flat", "owner_user_id": owner, "permalink_token": f"tb{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    try:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception as exc:
        if REQUIRE_BROWSER:
            raise
        pytest.skip(f"Chromium is not available: {exc}")
    context = browser.new_context(viewport={"width": width, "height": height})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
    page = context.new_page()
    page.goto(base + target)
    page.wait_for_selector("#main-content", timeout=30000)
    return browser, page


@pytest.mark.parametrize("path", ["/", "/stay-fees"])
@pytest.mark.parametrize("lang", ["en", "cs"])
@pytest.mark.parametrize("width,height", [(390, 844), (360, 780)])
def test_phone_tab_bar_clears_the_home_indicator(base, width, height, lang, path):
    with sync_api.sync_playwright() as playwright:
        browser, page = _open(playwright, base, width, height, f"{path}?lang={lang}")
        try:
            meta = page.evaluate("document.querySelector('meta[name=viewport]').getAttribute('content')")
            assert "viewport-fit=cover" in meta
            inner_h = page.evaluate("window.innerHeight")
            bar = page.evaluate("(() => { const r = document.querySelector('.ui-tabbar').getBoundingClientRect(); return {top: r.top, bottom: r.bottom, h: r.height}; })()")
            assert abs(bar["bottom"] - inner_h) <= 1
            assert round(bar["h"]) == 56
            assert page.evaluate("getComputedStyle(document.documentElement).scrollPaddingBottom") == "56px"
            link_bottoms = page.evaluate("[...document.querySelectorAll('.ui-tabbar a')].map(a => a.getBoundingClientRect().bottom)")
            assert len(link_bottoms) == 5
            max_link_bottom = max(link_bottoms)
            assert max_link_bottom <= bar["bottom"] + 0.5
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            page.wait_for_timeout(100)
            content_bottom = page.evaluate("Math.max(...[...document.querySelectorAll('#main-content *')].filter(e => e.getBoundingClientRect().height > 0).map(e => e.getBoundingClientRect().bottom))")
            bar_top = page.evaluate("document.querySelector('.ui-tabbar').getBoundingClientRect().top")
            assert content_bottom <= bar_top
            scroll_w = page.evaluate("document.documentElement.scrollWidth")
            assert scroll_w <= width
            print(f"TABBAR {path} {lang} {width}: meta_ok=1 inner_h={inner_h} bar_top={bar['top']:.1f} bar_bottom={bar['bottom']:.1f} bar_h={bar['h']:.1f} max_link_bottom={max_link_bottom:.1f} content_bottom={content_bottom:.1f} scrollWidth={scroll_w}")
            if path == "/" and width == 390:
                os.makedirs(SHOT_DIR, exist_ok=True)
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=os.path.join(SHOT_DIR, f"dashboard-{lang}-390.png"))
        finally:
            browser.close()


def test_phone_tab_bar_is_hidden_at_1280(base):
    with sync_api.sync_playwright() as playwright:
        browser, page = _open(playwright, base, 1280, 900, "/?lang=en")
        try:
            assert page.evaluate("getComputedStyle(document.querySelector('.ui-tabbar')).display") == "none"
        finally:
            browser.close()
