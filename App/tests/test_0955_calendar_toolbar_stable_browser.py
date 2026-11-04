"""0955: the calendar toolbar stays still, Today sits left of the arrows, Back keeps the calendar place."""
from __future__ import annotations

import pytest

from tests.test_dashboard_calendar import calendar_workspace  # noqa: F401
from tests.test_dashboard_calendar_browser import (  # noqa: F401
    GEOMETRY_0893,
    calendar_origin,
    launch,
    open_page,
    shot,
    sync_api,
    wait_loaded,
)

BOXES = """() => Object.fromEntries(['[data-cal-prev]','[data-cal-next]','[data-cal-today]','[data-cal-property]',
  '.cal-view-segment','[data-cal-settings]','[data-cal-scales]','[data-cal-month]','[data-cal-year]'].map(s => {
  const e = document.querySelector('#calendar ' + s); const r = e.getBoundingClientRect();
  return [s, [r.left, r.top, r.width, r.height].map(v => Math.round(v * 2) / 2)]; }))"""

SIX_CONTROLS = ["[data-cal-prev]", "[data-cal-next]", "[data-cal-today]", "[data-cal-property]",
                ".cal-view-segment", "[data-cal-settings]"]


def _open(playwright, workspace, origin, width, lang):
    browser = launch(playwright)
    context, page = open_page(browser, workspace, origin, width=width, locale=lang)
    page.goto(f"{origin}/?lang={lang}&cal_view=calendar&cal_date=2026-01-01")
    page.wait_for_selector(".cal-month, .cal-week")
    wait_loaded(page)
    return browser, context, page


@pytest.mark.parametrize("width", [768, 1024])
@pytest.mark.parametrize("scale", ["month", "week"])
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_0955_toolbar_still_across_12_arrow_clicks(calendar_workspace, calendar_origin, width, scale, lang):
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _open(playwright, calendar_workspace, calendar_origin, width, lang)
        if scale == "week":
            page.click('[data-cal-scale="week"]')
            page.wait_for_selector(".cal-week")
            wait_loaded(page)
        base = page.evaluate(BOXES)
        for selector in ("[data-cal-next]", "[data-cal-prev]"):
            for i in range(12):
                page.click(selector)
                wait_loaded(page)
                assert page.evaluate(BOXES) == base, (selector, i, page.locator("[data-cal-period]").inner_text())
        assert not page.evaluate(GEOMETRY_0893)["touching"]
        context.close()
        browser.close()


@pytest.mark.parametrize("width", [768, 1024, 1280])
def test_0955_scale_switch_keeps_arrows_and_filters_still(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _open(playwright, calendar_workspace, calendar_origin, width, "en")
        first = page.evaluate(BOXES)
        for scale in ("week", "year", "month"):
            page.click(f'[data-cal-scale="{scale}"]')
            wait_loaded(page)
            now = page.evaluate(BOXES)
            for control in SIX_CONTROLS:
                assert now[control] == first[control], (scale, control, now[control], first[control])
        context.close()
        browser.close()


@pytest.mark.parametrize("width", [768, 1024, 1280])
def test_0955_today_is_not_between_the_arrows(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _open(playwright, calendar_workspace, calendar_origin, width, "en")
        t = page.locator("[data-cal-today]").bounding_box()
        p = page.locator("[data-cal-prev]").bounding_box()
        n = page.locator("[data-cal-next]").bounding_box()
        assert t["x"] + t["width"] + 20 <= p["x"], (t, p)
        assert 12 <= n["x"] - (p["x"] + p["width"]) <= 16, (p, n)
        assert abs(t["y"] + t["height"] / 2 - (p["y"] + p["height"] / 2)) <= 1, (t, p)
        page.click("[data-cal-today]")
        wait_loaded(page)
        today = page.evaluate("() => document.querySelector('#calendar').dataset.today")
        assert page.locator("[data-cal-month]").input_value() == today[5:7]
        shot(page, f"0955-{width}")
        context.close()
        browser.close()


def test_0955_back_after_three_month_clicks(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280, locale="en")
        page.goto(f"{calendar_origin}/reservations")
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-01-01")
        page.wait_for_selector(".cal-month")
        wait_loaded(page)
        for _ in range(3):
            page.click("[data-cal-next]")
            wait_loaded(page)
        after = page.url
        month = page.locator("[data-cal-month]").input_value()
        assert "cal_date=2026-04" in after, (after, month)
        page.go_back()
        assert "/reservations" in page.url, page.url
        page.go_forward()
        page.wait_for_selector(".cal-month")
        wait_loaded(page)
        forward_month = page.locator("[data-cal-month]").input_value()
        assert forward_month == month, (page.url, forward_month, month)
        context.close()
        browser.close()
