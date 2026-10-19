"""Shell geometry (MASTER 6.2, 6.3): 240 px sidebar at 1280, 56 px tab bar with 44 px tabs at 390."""
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


def _open(playwright, base, width):
    username = f"shell{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Shell", role="host", username=username)
    db.insert("apartment", {"internal_name": "Shell flat", "owner_user_id": owner, "permalink_token": f"sh{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    try:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception as exc:
        if REQUIRE_BROWSER:
            raise
        pytest.skip(f"Chromium is not available: {exc}")
    context = browser.new_context(viewport={"width": width, "height": 900 if width >= 1024 else 844})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
    page = context.new_page()
    page.goto(base + "/reservations?lang=en")
    page.wait_for_selector("#main-content", timeout=30000)
    return browser, page


def test_desktop_sidebar_is_240_wide_and_main_starts_after_it(base):
    with sync_api.sync_playwright() as playwright:
        browser, page = _open(playwright, base, 1280)
        side = page.evaluate("document.querySelector('.ui-sidebar').getBoundingClientRect().width")
        main_left = page.evaluate("document.querySelector('#main-content').getBoundingClientRect().left")
        assert round(side) == 240 and main_left >= 240
        assert page.evaluate("getComputedStyle(document.querySelector('.ui-tabbar')).display") == "none"
        page.click("button[data-sidebar-collapse]")
        page.wait_for_function("document.body.classList.contains('sidebar-collapsed')")
        assert round(page.evaluate("document.querySelector('.ui-sidebar').getBoundingClientRect().width")) == 64
        browser.close()


def test_phone_tab_bar_is_fixed_at_the_bottom_with_five_44px_tabs(base):
    with sync_api.sync_playwright() as playwright:
        browser, page = _open(playwright, base, 390)
        assert page.evaluate("getComputedStyle(document.querySelector('.ui-sidebar')).display") == "none"
        bar = page.evaluate("(() => { const r = document.querySelector('.ui-tabbar').getBoundingClientRect(); return {top: r.top, bottom: r.bottom, h: r.height}; })()")
        assert round(bar["bottom"]) == 844 and bar["h"] >= 56
        heights = page.evaluate("[...document.querySelectorAll('.ui-tabbar a')].map(a => a.getBoundingClientRect().height)")
        assert len(heights) == 5 and min(heights) >= 44
        assert page.evaluate("document.documentElement.scrollWidth") <= 390
        page.click('[data-sheet-open="more-sheet"]')
        page.wait_for_selector("#more-sheet[open]")
        assert page.locator('#more-sheet a[href="/invoices"]').is_visible()
        browser.close()
