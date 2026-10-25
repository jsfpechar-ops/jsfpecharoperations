"""Shell geometry (MASTER 6.2, 6.3): 240 px sidebar at 1280, 56 px tab bar with 44 px tabs at 390."""
import os
import secrets
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from tests.browser_support import chromium_launch_kwargs
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401


def _open(playwright, base, width, path="/reservations?lang=en", engine="chromium", java_script_enabled=True):
    username = f"shell{secrets.token_hex(3)}"
    owner = auth.create_account(f"{username}@example.test", "Shell", role="host", username=username)
    db.insert("apartment", {"internal_name": "Shell flat", "owner_user_id": owner, "permalink_token": f"sh{secrets.token_hex(4)}", "active": 1, "created_at": db.utcnow()})
    try:
        browser = getattr(playwright, engine).launch(**(chromium_launch_kwargs() if engine == "chromium" else {}))
    except Exception as exc:
        if REQUIRE_BROWSER:
            raise
        pytest.skip(f"{engine} is not available: {exc}")
    context = browser.new_context(
        viewport={"width": width, "height": 900 if width >= 1024 else 844},
        java_script_enabled=java_script_enabled, service_workers="block",
    )
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base + "/"}])
    page = context.new_page()
    page.goto(base + path)
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
        page.wait_for_function("() => !document.body.classList.contains('sidebar-animating')")  # 0376: let the slide finish
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
        assert page.locator('#more-sheet a[href="/stay-fees"]').is_visible()
        # skeleton.js sees this link before shell.js cancels navigation.
        # Wait past its 300 ms delay; opening/closing More must keep the page.
        original_url = page.url
        page.wait_for_timeout(650)
        assert page.url == original_url
        assert page.locator("[data-page-skeleton]").is_hidden()
        assert page.locator("#main-content").get_attribute("aria-busy") is None
        page.locator("#more-sheet [data-sheet-close]").click()
        assert not page.locator("#more-sheet").evaluate("(dialog) => dialog.open")
        assert page.locator("[data-page-skeleton]").is_hidden()
        assert page.locator("#main-content").get_attribute("aria-busy") is None
        assert page.url == original_url
        browser.close()


FORM_PAGES = ("/apartments/new?lang=en", "/cleaning/new?lang=en")


def test_collapsed_rail_expands_again_with_the_same_button(base):
    with sync_api.sync_playwright() as playwright:
        browser, page = _open(playwright, base, 1280)
        page.goto(base + "/invoices?lang=en")
        page.wait_for_selector("#main-content")
        button = page.locator("button[data-sidebar-collapse]")
        button.click()
        page.wait_for_function("document.body.classList.contains('sidebar-collapsed')")
        page.wait_for_function("() => !document.body.classList.contains('sidebar-animating')")  # 0376: let the slide finish
        assert button.get_attribute("aria-expanded") == "false"
        assert round(page.evaluate("document.querySelector('.ui-sidebar').getBoundingClientRect().width")) == 64
        button.click()
        page.wait_for_function("!document.body.classList.contains('sidebar-collapsed')")
        page.wait_for_function("() => !document.body.classList.contains('sidebar-animating')")  # 0376: let the slide finish
        assert button.get_attribute("aria-expanded") == "true"
        assert round(page.evaluate("document.querySelector('.ui-sidebar').getBoundingClientRect().width")) == 240
        browser.close()


def test_collapsed_account_menu_is_whole_inside_the_viewport(base):
    for width in (1280, 2000):
        with sync_api.sync_playwright() as playwright:
            browser, page = _open(playwright, base, width)
            page.goto(base + "/invoices?lang=en")
            page.wait_for_selector("#main-content")
            page.locator("button[data-sidebar-collapse]").click()
            page.wait_for_function("document.body.classList.contains('sidebar-collapsed')")
            page.locator("[data-host-account] summary").click()
            page.wait_for_selector("[data-host-account][open] .host-account-menu")
            box = page.locator(".host-account-menu").bounding_box()
            viewport = page.viewport_size
            assert box["x"] >= 0 and box["y"] >= 0, (width, box)
            assert box["x"] + box["width"] <= viewport["width"], (width, box)
            assert box["y"] + box["height"] <= viewport["height"], (width, box)
            covered = page.evaluate(
                """(() => { const r = document.querySelector('.host-account-menu').getBoundingClientRect();
                    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                    return !!(hit && hit.closest('.host-account-menu')); })()"""
            )
            assert covered, width
            clipped = page.evaluate("(() => { const m = document.querySelector('.host-account-menu'); return m.scrollWidth > m.clientWidth + 1; })()")
            assert not clipped, width
            browser.close()


def test_invoice_settings_tab_switch_does_not_move_the_page(base):
    with sync_api.sync_playwright() as playwright:
        browser, page = _open(playwright, base, 1280)
        page.goto(base + "/invoices?lang=en")
        page.wait_for_selector("#main-content")
        page.locator(".ui-tabs a", has_text="Invoice settings").first.click()
        page.wait_for_url("**/entities**")
        page.wait_for_selector("#main-content")
        samples = page.evaluate(
            """async () => { const out = [];
                for (let i = 0; i < 20; i++) {
                    const m = document.querySelector('#main-content');
                    const t = document.querySelector('.ui-tabs');
                    out.push([getComputedStyle(m).transform, Math.round(m.getBoundingClientRect().left),
                              t ? t.scrollLeft : 0, window.scrollY]);
                    await new Promise(r => setTimeout(r, 30));
                }
                return out; }"""
        )
        assert all(row[0] == "none" and row[2] == 0 and row[3] == 0 for row in samples), samples
        assert len({row[1] for row in samples}) == 1, samples
        browser.close()


def test_focused_form_fields_do_not_outline_their_labels(base):
    with sync_api.sync_playwright() as playwright:
        browser, page = _open(playwright, base, 1280)
        for path in FORM_PAGES:
            page.goto(base + path)
            page.wait_for_selector("#main-content")
            field = page.locator("#main-content input:not([type=hidden]):not([type=checkbox]):not([type=radio]), #main-content select, #main-content textarea").first
            field.focus()
            outlined = page.evaluate(
                "[...document.querySelectorAll('#main-content label')].map(l => getComputedStyle(l).outlineStyle).filter(s => s !== 'none')"
            )
            assert outlined == [], (path, outlined)
        browser.close()


def _assert_content_is_not_loading(page):
    assert page.locator("[data-page-skeleton]").is_hidden()
    assert page.locator("#main-content").get_attribute("aria-busy") is None


@pytest.mark.parametrize("engine", os.environ.get("UBYHOST_SHELL_BROWSERS", "chromium").split(","))
@pytest.mark.parametrize("width", [390, 820])
@pytest.mark.parametrize("path", [
    "/?lang=en", "/reservations?lang=en", "/apartments/new?lang=en", "/settings?lang=en",
])
def test_more_preserves_each_page_kind_and_sheet_links_work(base, engine, width, path):
    with sync_api.sync_playwright() as playwright:
        browser, page = _open(playwright, base, width, path, engine)
        try:
            original_url = page.url
            for close_method in ("button", "escape", "search"):
                page.locator('[data-sheet-open="more-sheet"] svg').click()
                page.wait_for_selector("#more-sheet[open]")
                # A non-navigation must still show real content after DELAY_MS.
                page.wait_for_timeout(650)
                _assert_content_is_not_loading(page)
                assert page.url == original_url
                if close_method == "button":
                    shots = os.environ.get("UBYHOST_SHOTS_DIR")
                    if shots and width == 390:
                        folder = Path(shots)
                        folder.mkdir(parents=True, exist_ok=True)
                        name = path.split("?")[0].strip("/").replace("/", "-") or "dashboard"
                        page.screenshot(path=str(folder / f"more-{engine}-{name}-390.png"))
                    page.locator("#more-sheet [data-sheet-close]").click()
                elif close_method == "escape":
                    page.keyboard.press("Escape")
                else:
                    page.locator("#more-sheet [data-command-open]").click()
                    page.wait_for_selector("#command-dialog[open]")
                    page.locator("#command-dialog [data-command-close]").click()
                assert not page.locator("#more-sheet").evaluate("(dialog) => dialog.open")
                _assert_content_is_not_loading(page)
                assert page.url == original_url
            # The opt-out belongs to the trigger, so destinations in the sheet still work.
            page.locator('[data-sheet-open="more-sheet"]').click()
            page.locator('#more-sheet a[href="/stay-fees"]').click()
            page.wait_for_url("**/stay-fees**")
            assert page.locator("#main-content").is_visible()
        finally:
            browser.close()


@pytest.mark.parametrize("engine", os.environ.get("UBYHOST_SHELL_BROWSERS", "chromium").split(","))
def test_more_keeps_settings_fallback_without_javascript(base, engine):
    with sync_api.sync_playwright() as playwright:
        browser, page = _open(playwright, base, 390, engine=engine, java_script_enabled=False)
        try:
            page.locator('[data-sheet-open="more-sheet"]').click()
            page.wait_for_url("**/settings")
            assert page.locator("#main-content").is_visible()
        finally:
            browser.close()
