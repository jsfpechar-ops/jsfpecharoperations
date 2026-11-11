"""0850: address suggestions on the property editor (shared component; the endpoint is mocked with page.route)."""
from __future__ import annotations

import json
import os

from tests.browser_support import chromium_launch_kwargs
from tests.test_0710_v2_mockup_match_browser import _placeholders, base, dashboard_host, dashboard_rich_host  # noqa: F401
from tests.test_0830_airbnb_pages_browser import seeded  # noqa: F401
from tests.test_0833_property_editor_browser import _open_settings

WIDTHS_0850 = (390, 768, 1280)
SHOTS = os.environ.get("UBYHOST_SHOTS_0850")
SEVEN = ("addr_street", "addr_house_no", "addr_orient_no", "addr_zip", "addr_obec", "addr_obec_cast", "addr_okres")
ITEM = {
    "label": "Vinohradská 12, Praha 2",
    "fields": {
        "addr_street": "Vinohradská",
        "addr_house_no": "12",
        "addr_orient_no": "3",
        "addr_zip": "12000",
        "addr_obec": "Praha",
        "addr_obec_cast": "Vinohrady",
        "addr_okres": "Praha 2",
    },
}
OTHER = {"label": "Vinohradská 14, Praha 2", "fields": dict(ITEM["fields"], addr_house_no="14")}
LIST = "#addr_street-suggest"
OPTION = "#addr_street-suggest [role=option]"

_GAP_JS = """(list) => {
    const l = list.getBoundingClientRect();
    let minGap = null;
    let overlaps = 0;
    document.querySelectorAll('.property-address-grid input').forEach(e => {
        const r = e.getBoundingClientRect();
        if (r.width && r.left < l.right && l.left < r.right && r.top < l.bottom && l.top < r.bottom) overlaps += 1;
    });
    document.querySelectorAll('.property-address-grid .field').forEach(f => {
        if (f.contains(list)) return;
        const r = f.getBoundingClientRect();
        const horiz = r.left < l.right && l.left < r.right;
        if (horiz && r.top >= l.bottom - 1) {
            const gap = r.top - l.bottom;
            if (minGap === null || gap < minGap) minGap = gap;
        }
    });
    return {overlaps, minGap};
}"""


def _mock(page, body, status=200):
    def handler(route):
        route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

    page.route("**/apartments/ruian-suggest*", handler)


def _values(page):
    return {name: page.locator(f"#{name}").input_value() for name in SEVEN}


def _cookie_and_apartment(dashboard_rich_host):
    from app import auth

    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    return cookie, _placeholders(dashboard_rich_host)["first_property"]


def test_0850_typing_shows_list_and_pick_fills_all_seven(base, dashboard_rich_host, seeded):  # noqa: F811
    from playwright import sync_api

    cookie, apartment_id = _cookie_and_apartment(dashboard_rich_host)
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in WIDTHS_0850:
            context, page = _open_settings(browser, base, cookie, apartment_id, width)
            _mock(page, [ITEM, OTHER])
            page.locator("#addr_street").fill("Vinohr")
            page.locator(OPTION).first.wait_for(state="visible", timeout=5000)
            if page.locator(OPTION).count() != 2:
                problems.append(f"{width}: expected 2 suggestions")
            if SHOTS and width == 390:
                page.locator("#address").screenshot(path=os.path.join(SHOTS, "390-suggest-open.png"))
            vp = page.viewport_size
            box = page.locator(LIST).bounding_box()
            if box["x"] < 0 or box["x"] + box["width"] > vp["width"]:
                problems.append(f"{width}: list leaves the viewport")
            gap = page.locator(LIST).evaluate(_GAP_JS)
            if gap["overlaps"]:
                problems.append(f"{width}: list overlaps an address input")
            if gap["minGap"] is not None and gap["minGap"] < 11.5:
                problems.append(f"{width}: list is {gap['minGap']:.1f} px from the next field (need 12)")
            page.locator(OPTION).first.click()
            if _values(page) != ITEM["fields"]:
                problems.append(f"{width}: picked values were {_values(page)}")
            if not page.locator(LIST).is_hidden():
                problems.append(f"{width}: list stays open after a pick")
            context.close()
        browser.close()
    assert not problems, "\n".join(problems)


def test_0850_keyboard_moves_escape_closes_enter_picks(base, dashboard_rich_host, seeded):  # noqa: F811
    from playwright import sync_api

    cookie, apartment_id = _cookie_and_apartment(dashboard_rich_host)
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in WIDTHS_0850:
            context, page = _open_settings(browser, base, cookie, apartment_id, width)
            _mock(page, [ITEM, OTHER])
            street = page.locator("#addr_street")
            street.fill("Vinohr")
            page.locator(OPTION).first.wait_for(state="visible", timeout=5000)
            street.press("ArrowDown")
            street.press("ArrowDown")
            street.press("ArrowUp")
            if street.get_attribute("aria-activedescendant") != "addr_street-suggest-0":
                problems.append(f"{width}: arrow keys did not land on the first suggestion")
            street.press("Escape")
            if not page.locator(LIST).is_hidden():
                problems.append(f"{width}: Escape did not close the list")
            street.press("ArrowDown")
            if not page.locator(LIST).is_visible():
                problems.append(f"{width}: ArrowDown did not reopen the list")
            street.press("Enter")
            if _values(page) != ITEM["fields"]:
                problems.append(f"{width}: Enter did not pick the active suggestion")
            context.close()
        browser.close()
    assert not problems, "\n".join(problems)


def test_0850_empty_or_error_leaves_fields_untouched(base, dashboard_rich_host, seeded):  # noqa: F811
    from playwright import sync_api

    cookie, apartment_id = _cookie_and_apartment(dashboard_rich_host)
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in WIDTHS_0850:
            for body, status in (([], 200), ({"error": "x"}, 500), ({"error": "x"}, 404)):
                context, page = _open_settings(browser, base, cookie, apartment_id, width)
                _mock(page, body, status)
                before = _values(page)
                street = page.locator("#addr_street")
                street.fill("Vinohr")
                page.wait_for_timeout(700)
                if not page.locator(LIST).is_hidden():
                    problems.append(f"{width}/{status}: an empty answer showed a list")
                after = _values(page)
                if after != dict(before, addr_street="Vinohr"):
                    problems.append(f"{width}/{status}: other fields changed: {after}")
                context.close()
        browser.close()
    assert not problems, "\n".join(problems)


def test_1103_empty_lookup_says_so_instead_of_staying_silent(base, dashboard_rich_host, seeded):  # noqa: F811
    """1103: a lookup with no result shows a visible line, and the loading line shows while it runs."""
    from playwright import sync_api

    cookie, apartment_id = _cookie_and_apartment(dashboard_rich_host)
    problems = []
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
        for width in WIDTHS_0850:
            context, page = _open_settings(browser, base, cookie, apartment_id, width)

            def slow_empty(route):
                import time as _t

                _t.sleep(0.6)
                route.fulfill(status=200, content_type="application/json", body="[]")

            page.route("**/apartments/ruian-suggest*", slow_empty)
            page.locator("#addr_street").fill("Nowhereville")
            status = page.locator("#addr_street-suggest-status")
            status.wait_for(state="visible", timeout=3000)
            if "…" not in status.inner_text():
                problems.append(f"{width}: no loading line while the lookup runs")
            page.wait_for_function(
                "() => { const s = document.getElementById('addr_street-suggest-status');"
                " return s && !s.hidden && !s.textContent.includes('\u2026'); }", timeout=5000)
            if not page.locator(LIST).is_hidden():
                problems.append(f"{width}: empty list is shown")
            context.close()
        browser.close()
    assert not problems, "\n".join(problems)
