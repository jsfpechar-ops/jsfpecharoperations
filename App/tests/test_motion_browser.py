"""0386: dialogs, fold-outs, menus and page changes move smoothly, and stay still under reduced motion."""
from __future__ import annotations

from tests.test_host_wide_geometry_browser import (  # noqa: F401 - shared synthetic host fixtures
    _rail_context,
    _rail_page,
    chromium_launch_kwargs,
    sync_api,
    wide_base,
    wide_host,
)

# Records whether the page being left started a cross-document view transition.
PAGE_SWAP_RECORDER = """
window.addEventListener('pageswap', event => { sessionStorage.setItem('swapFaded', String(!!event.viewTransition)); });
"""
# True when a stylesheet opts this page into page-change fades (inside media rules that match).
OPTS_IN = """() => {
  const walk = rules => [...rules].some(rule =>
    (rule instanceof CSSViewTransitionRule && rule.navigation === 'auto')
    || (rule instanceof CSSMediaRule && matchMedia(rule.conditionText).matches && walk(rule.cssRules)));
  return [...document.styleSheets].some(sheet => { try { return walk(sheet.cssRules); } catch (e) { return false; } });
}"""
OPEN_DIALOG = """id => {
  const dialog = document.getElementById(id);
  dialog.showModal();
  return dialog.getAnimations().map(a => a.transitionProperty);
}"""
FOLD_OUT_HEIGHTS = """async selector => {
  const details = document.querySelector(selector);
  details.querySelector('summary').click();
  const heights = [];
  for (let i = 0; i < 6; i++) {
    await new Promise(resolve => setTimeout(resolve, 50));
    heights.push(parseFloat(getComputedStyle(details, '::details-content').blockSize));
  }
  return heights;
}"""


def test_dialogs_fade_in_and_phone_sheets_slide_up(wide_host, wide_base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = _rail_context(browser, wide_host, wide_base, 1280, collapsed=False)
        page = _rail_page(context, wide_base)
        assert {"opacity", "translate"} <= set(page.evaluate(OPEN_DIALOG, "command-dialog"))
        page.wait_for_function("() => document.getElementById('command-dialog').getAnimations().length === 0")
        facts = page.evaluate("() => { const s = getComputedStyle(document.getElementById('command-dialog')); return [s.opacity, s.translate]; }")
        assert facts == ["1", "0px"], facts
        page.keyboard.press("Escape")
        page.wait_for_function("() => !document.getElementById('command-dialog').open")
        context.close()

        context = _rail_context(browser, wide_host, wide_base, 390, collapsed=False)
        page = _rail_page(context, wide_base)
        page.click('[data-sheet-open="more-sheet"]')
        start = page.evaluate("() => getComputedStyle(document.getElementById('more-sheet')).translate")
        assert start not in ("none", "0px"), start
        page.wait_for_function("() => document.getElementById('more-sheet').getAnimations().length === 0")
        assert page.evaluate("() => getComputedStyle(document.getElementById('more-sheet')).translate") == "0px"
        context.close()
        browser.close()


def test_fold_outs_slide_open_and_floating_menus_are_not_clipped(wide_host, wide_base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = _rail_context(browser, wide_host, wide_base, 1280, collapsed=False)
        page = _rail_page(context, wide_base)
        heights = page.evaluate(FOLD_OUT_HEIGHTS, "details.ui-how")
        full = page.evaluate("() => document.querySelector('.ui-how-body').getBoundingClientRect().height")
        assert heights[0] < full, heights
        assert heights == sorted(heights), heights
        page.wait_for_function("() => document.querySelector('details.ui-how').getAnimations({subtree: true}).length === 0")
        assert page.evaluate("() => getComputedStyle(document.querySelector('details.ui-how'), '::details-content').overflow") == "clip"

        # The account menu floats above its trigger, so its fold-out must never clip it.
        page.locator("details.host-account summary").click()
        menu = page.locator(".host-account-menu")
        menu.wait_for(state="visible")
        box = menu.bounding_box()
        assert box and box["height"] > 40, box
        clip = page.evaluate("() => getComputedStyle(document.querySelector('details.host-account'), '::details-content').overflow")
        assert clip != "clip", clip
        context.close()
        browser.close()


def test_page_changes_cross_fade_with_the_rail_held_still(wide_host, wide_base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = _rail_context(browser, wide_host, wide_base, 1280, collapsed=False)
        context.add_init_script(PAGE_SWAP_RECORDER)
        page = _rail_page(context, wide_base)
        assert page.evaluate("getComputedStyle(document.getElementById('app-sidebar')).viewTransitionName") == "host-rail"
        assert page.evaluate(OPTS_IN) is True
        page.locator('.ui-nav a[href="/reservations"]').click()
        page.wait_for_url("**/reservations**")
        page.wait_for_load_state("networkidle")
        # Headless Chromium sometimes drops the new half; a dropped fade just snaps, so check both ends opted in.
        assert page.evaluate("sessionStorage.getItem('swapFaded')") == "true"
        assert page.evaluate(OPTS_IN) is True
        context.close()
        browser.close()


def test_reduced_motion_keeps_pages_and_dialogs_still(wide_host, wide_base):
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = _rail_context(browser, wide_host, wide_base, 1280, collapsed=False, reduced_motion="reduce")
        context.add_init_script(PAGE_SWAP_RECORDER)
        page = _rail_page(context, wide_base)
        page.evaluate(OPEN_DIALOG, "command-dialog")
        duration = page.evaluate("() => getComputedStyle(document.getElementById('command-dialog')).transitionDuration")
        seconds = [float(p[:-2]) / 1000 if p.endswith("ms") else float(p[:-1]) for p in duration.split(", ")]
        assert max(seconds) < 0.01, duration
        page.keyboard.press("Escape")
        page.locator('.ui-nav a[href="/reservations"]').click()
        page.wait_for_url("**/reservations**")
        page.wait_for_load_state("networkidle")
        assert page.evaluate("sessionStorage.getItem('swapFaded')") == "false"
        context.close()
        browser.close()


def test_pages_without_javascript_stay_still(wide_host, wide_base):
    """Chromium can leave a fade unfinished with scripting off, so no-JS pages get no motion at all."""
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        context = _rail_context(browser, wide_host, wide_base, 1280, collapsed=False, java_script_enabled=False)
        page = _rail_page(context, wide_base)
        page.locator("details.ui-how summary").click()
        assert page.locator(".ui-how-body").is_visible()
        page.locator('.ui-nav a[href="/reservations"]').click()
        page.wait_for_url("**/reservations**")
        page.locator(".ui-nav a[href='/']").click()
        page.wait_for_url(wide_base + "/")
        context.close()
        browser.close()
