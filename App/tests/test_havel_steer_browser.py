"""Havel steer: Help opens Havel, composer on first open, guide ask box, frameless panel."""
from __future__ import annotations

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from tests import test_havel_browser as hb  # noqa: E402
from tests.test_submission_retry_cap import host  # noqa: E402,F401

origin = hb.origin
_context = hb._context


def test_help_entry_opens_havel_with_composer(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 1280)
        page = context.new_page()
        page.goto(origin[0] + "/")
        page.locator("#app-sidebar .me-menu > summary").click()
        page.locator('#app-sidebar .me-menu-list a[data-havel-launcher]').click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        sync_api.expect(dialog.locator("#havel-message")).to_be_visible()
        browser.close()


@pytest.mark.parametrize("width", [390, 1280])
def test_panel_has_no_border_and_composer_on_first_open(origin, width):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, width)
        page = context.new_page()
        page.goto(origin[0] + "/")
        page.locator("[data-havel-fab]").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        sync_api.expect(dialog.locator("#havel-message")).to_be_visible()
        widths = page.evaluate(
            "() => { const s = getComputedStyle(document.getElementById('havel-sheet'));"
            " return [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth]; }"
        )
        assert widths == ["0px"] * 4
        browser.close()


def test_guide_ask_box_posts_without_javascript(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390, js=False)
        page = context.new_page()
        page.goto(origin[0] + "/guide?lang=en")
        form = page.locator("form.guide-ask[data-havel-guide-ask]")
        sync_api.expect(form).to_be_visible()
        assert form.get_attribute("action") == "/havel"
        page.fill("#guide-ask-q", "How do I add a stay?")
        form.locator("button[type=submit]").click()
        page.wait_for_url("**/havel**")
        assert page.locator(".havel-bubble, .havel-msg-host").count() >= 1
        browser.close()


def test_guide_ask_box_fits_at_320(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 320)
        page = context.new_page()
        page.goto(origin[0] + "/guide?lang=en")
        box = page.locator(".guide-ask").bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= 320
        assert page.evaluate("document.documentElement.scrollWidth") <= 320
        browser.close()
