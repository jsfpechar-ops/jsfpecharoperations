"""0911: Gantt only for 3+ properties, one colour per property, cleaning chips under stay bars."""
from __future__ import annotations

import json
import os

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth
from tests.browser_support import chromium_launch_kwargs
from tests.test_dashboard_calendar_browser import calendar_origin, launch, open_page, wait_loaded, shot  # noqa: F401
from tests.test_dashboard_calendar import calendar_workspace  # noqa: F401
from tests.test_0905_cleaning_calendar_stays_browser import _seed
from tests.test_host_geometry import _browser_session_cookie, base  # noqa: F401

AMBER = "rgb(138, 82, 0)"
TONES = {"teal", "blue", "purple", "indigo", "ink"}


def _workspace_page(browser, ws, origin, width):
    context = browser.new_context(viewport={"width": width, "height": 1000})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": ws["client"].cookies.get(auth.SESSION_COOKIE), "url": origin + "/"}])
    return context, context.new_page()


def _seed_page(browser, base_url, username, width):
    context = browser.new_context(viewport={"width": width, "height": 1000})
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": _browser_session_cookie(username), "url": base_url + "/"}])
    return context, context.new_page()


@pytest.mark.parametrize("path", ["/", "/cleaning"])
@pytest.mark.parametrize("width", [768, 1280])
def test_0911_one_property_shows_only_the_calendar(calendar_workspace, calendar_origin, path, width):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = _workspace_page(browser, calendar_workspace, calendar_origin, width)
        page.goto(f"{calendar_origin}{path}?lang=en&cal_view=gantt&cal_date=2026-10-01")
        page.wait_for_selector(".cal-gantt-row")
        assert page.locator(".cal-gantt-row").count() == 3
        assert page.locator(".cal-view-segment").is_visible()
        prop = calendar_workspace["properties"][0]
        page.locator("[data-cal-property]").select_option(str(prop))
        page.wait_for_selector(".cal-week")
        assert page.locator(".cal-gantt-row").count() == 0
        assert not page.locator(".cal-view-segment").is_visible()
        page.goto(f"{calendar_origin}{path}?lang=en&cal_view=gantt&cal_date=2026-10-01&cal_property={prop}")
        page.wait_for_selector(".cal-week")
        assert page.locator(".cal-gantt-row").count() == 0
        assert not page.locator(".cal-view-segment").is_visible()
        shot(page, f"0911-one-property-{path.strip('/') or 'home'}-{width}")
        page.locator("[data-cal-property]").select_option("")
        page.wait_for_function("() => document.querySelectorAll('.cal-gantt-row').length === 3")
        assert page.locator(".cal-view-segment").is_visible()
        context.close()
        browser.close()


@pytest.mark.parametrize("path", ["/", "/cleaning"])
@pytest.mark.parametrize("width", [768, 1280])
def test_0911_under_three_properties_never_offers_gantt(base, path, width):  # noqa: F811
    username = _seed()
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = _seed_page(browser, base, username, width)
        page.goto(f"{base}{path}?lang=en&cal_view=gantt&cal_date=2026-11-03")
        page.wait_for_selector(".cal-week")
        assert page.locator(".cal-gantt-row").count() == 0
        assert not page.locator(".cal-view-segment").is_visible()
        page.locator("[data-cal-settings]").first.click()
        assert page.locator("[data-cal-auto]").evaluate("el => el.closest('.cal-setting').hidden") is True
        context.close()
        browser.close()


def test_0911_each_property_has_one_colour_everywhere(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = _workspace_page(browser, calendar_workspace, calendar_origin, 1280)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=gantt&cal_date=2026-10-01")
        page.wait_for_selector(".cal-gantt-row")
        names = page.locator(".cal-gantt-row .cal-gantt-name[data-cal-color]")
        assert names.count() == 3
        gantt_colour = {}
        for index in range(names.count()):
            node = names.nth(index)
            gantt_colour[node.inner_text().strip()] = node.evaluate("el => getComputedStyle(el, '::before').backgroundColor")
        assert len(set(gantt_colour.values())) == 3
        for colour in gantt_colour.values():
            assert colour not in (AMBER,)
        properties = json.loads(page.locator("[data-cal-properties]").text_content())
        colour_by_id = {str(item["id"]): gantt_colour[item["name"]] for item in properties}
        page.locator('[data-cal-view="calendar"]').click()
        page.wait_for_selector(".cal-week")
        pills = page.locator(".cal-pill")
        assert pills.count() > 0
        for index in range(pills.count()):
            pill = pills.nth(index)
            assert pill.evaluate("el => getComputedStyle(el).backgroundColor") == colour_by_id[pill.get_attribute("data-cal-property-id")]
            assert pill.evaluate("el => getComputedStyle(el).color") == "rgb(255, 255, 255)"
        select = page.locator("[data-cal-property]")
        select.select_option(str(properties[1]["id"]))
        page.wait_for_selector(".cal-week")
        assert "radial-gradient" in select.evaluate("el => getComputedStyle(el).backgroundImage")
        assert select.get_attribute("data-cal-color") in TONES
        shot(page, "0911-colours-1280")
        context.close()
        browser.close()


@pytest.mark.parametrize("width", [768, 1024, 1280])
def test_0911_bars_never_cover_cleaning_chips(base, width):  # noqa: F811
    username = _seed()
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = _seed_page(browser, base, username, width)
        page.goto(f"{base}/cleaning?lang=en&cal_date=2026-11-03")
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        row = page.locator(".cal-week", has=page.locator('[data-date="2026-11-08"]'))
        tile = row.locator('[data-date="2026-11-08"]').filter(has=page.locator(".cal-clean-chip")).first
        chips = tile.locator(".cal-clean-chip")
        assert chips.count() == 2
        pills = row.locator(".cal-pill")
        assert pills.count() == 2
        gap = float(row.locator(".cal-pills").evaluate("el => getComputedStyle(el).columnGap").replace("px", ""))
        t = tile.bounding_box()
        r = row.bounding_box()
        pill_boxes = [pills.nth(i).bounding_box() for i in range(2)]
        chip_boxes = [chips.nth(i).bounding_box() for i in range(2)]
        for box in pill_boxes:
            assert box["x"] + box["width"] <= t["x"] + t["width"] / 2 - gap / 2 + 1
            assert box["y"] + box["height"] <= r["y"] + r["height"] + 1
        lowest_pill = max(box["y"] + box["height"] for box in pill_boxes)
        for chip in chip_boxes:
            assert chip["y"] >= lowest_pill + 7
            assert chip["y"] + chip["height"] <= t["y"] + t["height"] - 11
            for box in pill_boxes:
                overlap = not (chip["x"] + chip["width"] <= box["x"] or box["x"] + box["width"] <= chip["x"]
                               or chip["y"] + chip["height"] <= box["y"] or box["y"] + box["height"] <= chip["y"])
                assert not overlap
            cx, cy = chip["x"] + chip["width"] / 2, chip["y"] + chip["height"] / 2
            hit = page.evaluate("([x, y]) => { const e = document.elementFromPoint(x, y); return !!e && !!e.closest('.cal-clean-chip'); }", [cx, cy])
            assert hit
        shot(page, f"0911-cleaning-{width}")
        context.close()
        browser.close()


def test_0911_phone_cleaning_tiles_unchanged(base):  # noqa: F811
    username = _seed()
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = _seed_page(browser, base, username, 390)
        page.goto(f"{base}/cleaning?lang=en&cal_date=2026-11-03")
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        row = page.locator(".cal-week", has=page.locator('[data-date="2026-11-08"]'))
        tile = row.locator('[data-date="2026-11-08"]').first
        bars = row.locator(".cal-pill")
        assert bars.count() == 2
        for index in range(2):
            assert bars.nth(index).is_visible()
            assert bars.nth(index).bounding_box()["height"] <= 10
        for tag in tile.locator(".cal-clean-tag").all():
            tag_box = tag.bounding_box()
            for index in range(2):
                box = bars.nth(index).bounding_box()
                overlap = not (tag_box["x"] + tag_box["width"] <= box["x"] or box["x"] + box["width"] <= tag_box["x"]
                               or tag_box["y"] + tag_box["height"] <= box["y"] or box["y"] + box["height"] <= tag_box["y"])
                assert not overlap
        shot(page, "0911-cleaning-390")
        context.close()
        browser.close()
