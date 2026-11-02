"""Phone dashboard (0147, 0148, 0241): dots instead of bars, reduced controls, one PIN line, one short line per setup gap."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from tests.test_dashboard_calendar_browser import (  # noqa: F401
    calendar_origin, calendar_workspace, launch, open_page, shot,
)

from app import alerts, db


def seed_pin_alerts(ws):
    for property_id in ws["properties"]:
        alerts.raise_alert(
            "warning", "guest_pin_rotated", "The guest link PIN was replaced with a new six-digit PIN.",
            detail="Four-digit PINs are no longer accepted.", dedupe_key=f"guest_pin_rotated:{property_id}",
            apartment_id=property_id, owner_user_id=ws["owner"],
        )
    return [db.query_one("SELECT internal_name FROM apartment WHERE id = ?", (pid,))["internal_name"] for pid in ws["properties"]]


HIDDEN_ON_PHONE = (".cal-view-segment", "[data-cal-settings]", "[data-cal-scales]", "[data-cal-month]", "[data-cal-year]")
SHOWN_ON_PHONE = ("[data-cal-property]", "[data-cal-prev]", "[data-cal-next]", "[data-cal-period]")


def visible_count(page, selector):
    return page.locator(selector).evaluate_all("nodes => nodes.filter(node => node.offsetParent).length")


def test_phone_dashboard_compact(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        for width in (390, 1280):
            context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, locale="en", touch=width < 768)
            if width < 768:
                page.wait_for_selector(".cal-week.is-dots")
                assert page.locator(".cal-week-events .cal-event").count() == 0
                assert page.locator(".cal-dots .cal-dot").count() >= 3
                # The shared fixture puts five stays on 14-19 October: three dots plus "+2".
                assert page.locator(".cal-dot-more").first.inner_text() == "+2"
                for selector in HIDDEN_ON_PHONE:
                    assert visible_count(page, selector) == 0, selector
                for selector in SHOWN_ON_PHONE:
                    assert visible_count(page, selector) >= 1, selector
                page.locator('[data-cal-day="2026-10-15"]').click()
                assert page.locator("[data-cal-day-dialog]").is_visible()
                assert page.locator("[data-cal-day-list] .cal-event").count() == 5
                page.locator("[data-cal-day-dialog] [data-cal-close]").click()
                names = seed_pin_alerts(calendar_workspace)
                # 0765: the phone calendar view hides the to-do list, so check it on the Today view (no cal_ params).
                page.goto(f"{calendar_origin}/?lang=en")
                # 0241: the three PIN alerts are one line in "What needs you", linking to the property list.
                assert page.locator(".notification-stack:visible").count() == 0
                pin_lines = page.locator('[data-needs-you-card] [data-needs-you="alert"]', has_text="PIN")
                assert pin_lines.count() == 1
                assert pin_lines.first.locator('a[href="/apartments"]').count() == 1
                assert len(names) == 3
                # One short line per property with missing police details: no field list.
                setup_lines = page.locator('[data-needs-you-card] [data-needs-you="setup"]')
                assert setup_lines.count() == 3
                for index in range(3):
                    assert setup_lines.nth(index).locator(".btn").count() == 1
                    assert "Police details missing" in setup_lines.nth(index).text_content()
                if not pin_lines.first.is_visible():
                    page.locator(".needs-you-more > summary").first.click()
                shot(page, "phone-390-alert")
                # 0371: wait for the async dismiss POST and for the line to leave, not a fixed sleep.
                with page.expect_response(lambda response: response.request.method == "POST" and
                                          response.url.split("?")[0].endswith("/dismiss")) as dismissed:
                    pin_lines.first.locator("[data-notification-dismiss] button").click()
                assert dismissed.value.status == 204
                pin_lines.first.wait_for(state="detached")
                page.reload()
                assert page.locator("[data-notification]", has_text="PIN").count() == 0
            else:
                assert page.locator(".cal-dots").count() == 0
                assert page.locator(".cal-gantt-row").count() >= 1
                for selector in HIDDEN_ON_PHONE:
                    if selector != "[data-cal-scales]":
                        assert visible_count(page, selector) >= 1, selector
                assert not page.locator("[data-cal-scales]").is_visible()  # gantt hides scales by design
                page.locator('[data-cal-view="calendar"]').click()
                page.locator("[data-cal-scales]").wait_for(state="visible")
                page.locator('[data-cal-view="gantt"]').click()
                page.locator(".cal-gantt-row").first.wait_for(state="visible")
                assert page.locator('[data-needs-you-card] [data-needs-you="setup"]').count() == 3
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            shot(page, f"phone-{width}")
            context.close()
        browser.close()


# 0814: Airbnb-style phone calendar (day tiles, touch range select, bottom sheet).
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0814"
TILE = '.cal-day[data-date="{}"]'
BUTTON = '[data-cal-day="{}"]'
SHEET = "[data-cal-day-dialog]"


def _box(page, selector):
    result = page.locator(selector).bounding_box()
    assert result is not None, selector
    return result


def _center(page, selector):
    box = _box(page, selector)
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


WAIT_OPEN = "() => [...document.querySelectorAll('dialog[open]')].every(d => getComputedStyle(d).opacity === '1')"


def test_phone_calendar_tiles_and_sheet(calendar_workspace, calendar_origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=390, locale="en", touch=True)
        page.wait_for_selector(".cal-week.is-dots")
        page.evaluate("window.scrollTo(0, 0)")
        tile, neighbour = _box(page, TILE.format("2026-10-10")), _box(page, TILE.format("2026-10-11"))
        assert tile["width"] >= 44 and tile["height"] >= 44
        assert neighbour["x"] - (tile["x"] + tile["width"]) >= 4
        assert not page.locator("#calendar-title").is_visible()
        hint = page.locator("#cal-hint").bounding_box()
        assert hint is None or hint["width"] <= 1 or hint["height"] <= 1
        arrow_bg = page.eval_on_selector(".dashboard-calendar[data-cleaning='false'] .cal-navigation .cal-arrow", "e => getComputedStyle(e).backgroundColor")
        assert arrow_bg != "rgb(208, 69, 45)" and arrow_bg == "rgb(242, 242, 240)"
        assert page.evaluate("() => [...document.querySelectorAll('.cal-dots')].every(d => d.querySelectorAll('.cal-dot').length <= 3)")
        assert page.evaluate("() => [...document.querySelectorAll('.cal-dot')].every(d => d.getBoundingClientRect().right <= d.closest('.cal-day').getBoundingClientRect().right + 0.5)")
        page.wait_for_function(WAIT_OPEN)
        page.screenshot(path=str(SHOTS / "calendar-390.png"))
        page.locator(BUTTON.format("2026-10-10")).tap()
        assert page.locator(SHEET).is_visible()
        assert page.evaluate("document.querySelector('[data-cal-day-dialog]').open")
        assert not page.evaluate("!!document.querySelector('dialog:modal')")
        assert page.locator(TILE.format("2026-10-10") + ".is-selected").count() == 1
        assert page.eval_on_selector(TILE.format("2026-10-10"), "e => getComputedStyle(e).backgroundColor") == "rgb(34, 34, 34)"
        selected_look = page.eval_on_selector(TILE.format("2026-10-10"), "e => [getComputedStyle(e).boxShadow, getComputedStyle(e).outlineStyle]")
        assert selected_look == ["none", "none"], selected_look
        assert page.eval_on_selector_all(".havel-fab", "els => els.every(e => getComputedStyle(e).display === 'none')")
        page.locator(BUTTON.format("2026-10-12")).tap()
        assert page.locator(".cal-day.is-selected").count() == 3
        assert "13" in page.inner_text("#cal-day-title")
        pill, close = _box(page, "#cal-day-title"), _box(page, "[data-cal-day-dialog] [data-cal-close]")
        assert abs((pill["y"] + pill["height"] / 2) - (close["y"] + close["height"] / 2)) <= 2
        assert close["width"] == 40 and close["height"] == 40
        assert page.eval_on_selector("[data-cal-day-dialog] [data-cal-close]", "e => getComputedStyle(e).backgroundColor") != "rgb(208, 69, 45)"
        assert close["x"] - (pill["x"] + pill["width"]) >= 12
        sheet, add = _box(page, SHEET), _box(page, "[data-cal-day-add]")
        assert sheet["y"] + sheet["height"] <= page.viewport_size["height"] - 84 + 1
        assert add["height"] >= 44 and (sheet["y"] + sheet["height"]) - (add["y"] + add["height"]) >= 24
        assert add["x"] - sheet["x"] >= 16 and (sheet["x"] + sheet["width"]) - (add["x"] + add["width"]) >= 16
        if page.locator("[data-cal-day-list] .cal-event").count() == 0:
            heading = _box(page, "[data-cal-day-dialog] .cal-dialog-heading")
            assert abs((add["y"] - (heading["y"] + heading["height"])) - 16) <= 1
        page.wait_for_function(WAIT_OPEN)
        page.screenshot(path=str(SHOTS / "calendar-range-390.png"))
        page.locator("[data-cal-day-add]").tap()
        assert page.locator("[data-cal-create]").is_visible()
        assert page.input_value("#cal-arrival") == "2026-10-10"
        assert page.input_value("#cal-departure") == "2026-10-13"
        page.wait_for_function(WAIT_OPEN)
        select_box = _box(page, "#cal-property")
        assert abs(select_box["height"] - 48) <= 1
        assert page.eval_on_selector("#cal-property", "e => getComputedStyle(e).fontSize") == "16px"
        toggle = _box(page, "[data-cal-create] .cal-create-types .btn >> nth=0")
        assert abs(toggle["height"] - 40) <= 1
        inactive = page.eval_on_selector("[data-cal-create] .cal-create-types .btn:not([aria-pressed='true'])", "e => getComputedStyle(e).backgroundColor")
        assert inactive != "rgb(208, 69, 45)"
        page.screenshot(path=str(SHOTS / "calendar-create-390.png"))
        page.locator("[data-cal-create] [data-cal-close]").first.tap()
        page.locator(BUTTON.format("2026-10-10")).tap()
        page.locator("[data-cal-day-dialog] [data-cal-close]").tap()
        page.wait_for_timeout(200)
        assert page.locator(".cal-day.is-selected").count() == 0


def test_phone_calendar_long_press_drag(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=390, locale="en", touch=True)
        page.wait_for_selector(".cal-week.is-dots")
        cdp = context.new_cdp_session(page)
        # The page settles its scroll position after load; start the gesture from a fixed position.
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_function("scrollY === 0")
        x, y = _center(page, TILE.format("2026-10-03"))
        tx, ty = _center(page, TILE.format("2026-10-05"))
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        page.wait_for_timeout(400)
        for step in (1, 2, 3):
            point = {"x": x + (tx - x) * step / 3, "y": y + (ty - y) * step / 3}
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [point]})
            page.wait_for_timeout(50)  # Chrome dispatches touchmove once per frame; a real finger spans frames.
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        page.wait_for_timeout(100)
        selected = page.eval_on_selector_all(".cal-day.is-selected", "els => els.map(e => e.dataset.date)")
        assert selected == ["2026-10-03", "2026-10-04", "2026-10-05"]
        assert page.locator(SHEET).is_visible()
        page.locator("[data-cal-day-dialog] [data-cal-close]").tap()
        x, y = _center(page, TILE.format("2026-10-03"))
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y - 200}]})
        page.wait_for_timeout(50)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        page.wait_for_timeout(100)
        assert page.locator(".cal-day.is-selected").count() == 0
        assert not page.locator(SHEET).is_visible()


def test_phone_calendar_fits_320(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=320, locale="en", touch=True)
        page.wait_for_selector(".cal-week.is-dots")
        assert page.evaluate("document.documentElement.scrollWidth") <= 320
        assert _box(page, TILE.format("2026-10-10"))["height"] >= 44


def test_calendar_screenshots_0814_desktop(calendar_workspace, calendar_origin):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-10-01")
        page.wait_for_selector(".cal-week")
        page.screenshot(path=str(SHOTS / "calendar-1280.png"), full_page=True)
        page.locator(BUTTON.format("2026-10-10")).click()
        assert page.locator("[data-cal-day-dialog]").is_visible()
        page.locator("[data-cal-day-add]").click()
        assert page.locator("[data-cal-create]").is_visible()
        page.screenshot(path=str(SHOTS / "calendar-dialog-1280.png"), full_page=True)
