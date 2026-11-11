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


def test_sheet_grows_after_a_real_conversation(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 1280)
        page = context.new_page()
        page.goto(origin[0] + "/")
        page.locator("[data-havel-fab]").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        sheet = dialog.locator(".ui-sheet")
        before = sheet.bounding_box()["height"]
        message = dialog.locator("#havel-message")
        message.fill("How do I add a stay?")
        message.press("Enter")
        dialog.locator(".havel-msg-havel:not([data-havel-writing])").last.wait_for()
        after = sheet.bounding_box()["height"]
        assert after > before + 80, (before, after)
        assert after <= 681
        browser.close()


def test_topic_launcher_loads_the_reporting_topic(origin):
    """The Ask Havel links on stuck states carry data-havel-topic; one is injected here because the stuck states are hard to reach."""
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 390)
        page = context.new_page()
        page.goto(origin[0] + "/")
        page.evaluate(
            "() => { const a = document.createElement('a'); a.id = 'ask-test'; a.href = '/havel?topic=reporting';"
            " a.setAttribute('data-sheet-open', 'havel-sheet'); a.setAttribute('data-havel-launcher', '');"
            " a.setAttribute('data-havel-topic', 'reporting'); a.textContent = 'Ask Havel'; document.querySelector('main').prepend(a); }"
        )
        page.locator("#ask-test").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        dialog.locator("[data-havel-topic-link][href*='topic=reporting&q=']").first.wait_for()
        assert dialog.locator("[data-havel-topic-link][href*='topic=reporting&q=']").count() >= 2
        browser.close()


def test_guide_ask_box_opens_the_panel_and_sends(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 1280)
        page = context.new_page()
        page.goto(origin[0] + "/guide?lang=en")
        assert page.locator("#guide-ask-q").get_attribute("placeholder") == "Type your question"
        page.fill("#guide-ask-q", "How do I add a stay?")
        page.locator("form.guide-ask button[type=submit]").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        dialog.locator(".havel-msg-host", has_text="How do I add a stay?").wait_for()
        dialog.locator(".havel-msg-havel:not([data-havel-writing])").last.wait_for()
        assert page.locator("#guide-ask-q").input_value() == ""
        assert page.url.split("?")[0].endswith("/guide")
        browser.close()


@pytest.mark.parametrize("width", [390, 1280])
def test_guide_ask_box_and_link_sizes(origin, width):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, width)
        page = context.new_page()
        page.goto(origin[0] + "/guide?lang=en")
        field = page.locator("#guide-ask-q").bounding_box()
        button = page.locator("form.guide-ask button[type=submit]").bounding_box()
        assert abs(field["height"] - button["height"]) <= 1
        if width == 390:
            assert page.locator("#guide-ask-q").evaluate("el => getComputedStyle(el).fontSize") == "16px"
        page.locator("[data-havel-fab]").click()
        link = page.locator("#havel-sheet .havel-guide-link")
        link.wait_for()
        assert link.bounding_box()["height"] >= 44
        browser.close()


def test_panel_clears_the_tab_bar_at_768(origin):
    with sync_api.sync_playwright() as pw:
        browser, context = _context(pw, origin, 768)
        page = context.new_page()
        page.goto(origin[0] + "/")
        page.locator("[data-havel-fab]").click()
        dialog = page.locator("#havel-sheet[open]")
        dialog.wait_for()
        page.wait_for_timeout(400)
        sheet = dialog.locator(".ui-sheet").bounding_box()
        tabbar = page.locator("nav.tabs").bounding_box()
        assert sheet["y"] + sheet["height"] <= tabbar["y"] + 1, (sheet, tabbar)
        browser.close()
