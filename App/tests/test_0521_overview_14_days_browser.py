"""Overview calendar: a fixed 14-day timeline on computers, dots on phones."""
from __future__ import annotations

from datetime import date, timedelta

from tests.test_dashboard_calendar import calendar_workspace, make_stay  # noqa: F401
from tests.test_dashboard_calendar_browser import (  # noqa: F401
    calendar_origin, launch, open_page, shot, sync_api, wait_loaded,
)


def slot_dates(page):
    return page.locator(".cal-gantt-row").first.locator(".cal-gantt-slot").evaluate_all(
        "slots => slots.map(slot => slot.dataset.date)")


def test_overview_shows_fourteen_days_from_today_and_moves_by_fourteen(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.goto(calendar_origin + "/?lang=cs")
        page.wait_for_selector(".cal-gantt-row")
        wait_loaded(page)
        today = page.get_attribute("[data-calendar]", "data-today")
        start = date.fromisoformat(today)
        expected = [(start + timedelta(days=index)).isoformat() for index in range(14)]
        assert slot_dates(page) == expected
        assert page.locator("[data-cal-days]").get_attribute("aria-pressed") == "true"
        assert page.locator("[data-cal-scales]").is_hidden()
        assert page.locator("[data-cal-month]").is_hidden()
        assert page.locator("[data-cal-year]").is_hidden()
        shot(page, "overview-14-days-cs-1280")

        page.locator("[data-cal-next]").click()
        page.wait_for_function(
            "d => document.querySelector('.cal-gantt-slot').dataset.date === d",
            arg=(start + timedelta(days=14)).isoformat())
        wait_loaded(page)
        assert len(slot_dates(page)) == 14

        page.locator("[data-cal-today]").click()
        page.wait_for_function(
            "d => document.querySelector('.cal-gantt-slot').dataset.date === d", arg=today)
        wait_loaded(page)
        assert slot_dates(page) == expected
        context.close()
        browser.close()


def test_month_view_is_one_click_away_and_fourteen_days_comes_back(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.goto(calendar_origin + "/?lang=cs")
        page.wait_for_selector(".cal-gantt-row")
        wait_loaded(page)
        today = page.get_attribute("[data-calendar]", "data-today")
        expected = [(date.fromisoformat(today) + timedelta(days=index)).isoformat() for index in range(14)]
        assert page.locator('[data-cal-view="calendar"]').get_attribute("aria-pressed") == "false"
        page.locator('[data-cal-view="calendar"]').click()
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        assert page.locator('[data-cal-view="calendar"]').get_attribute("aria-pressed") == "true"
        assert page.locator("[data-cal-days]").get_attribute("aria-pressed") == "false"
        page.locator("[data-cal-days]").click()
        page.wait_for_selector(".cal-gantt-row")
        wait_loaded(page)
        assert slot_dates(page) == expected
        assert page.locator("[data-cal-days]").get_attribute("aria-pressed") == "true"
        page.goto(calendar_origin + "/?lang=cs&cal_date=2026-10-01")
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        assert page.locator("[data-cal-days]").get_attribute("aria-pressed") == "false"
        assert page.locator("[data-cal-scales]").is_visible()
        context.close()
        browser.close()

def test_cleaning_timeline_keeps_thirty_days(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.goto(f"{calendar_origin}/cleaning?lang=en&cal_date=2026-10-27&cal_view=gantt")
        page.wait_for_selector(".cal-gantt-row")
        wait_loaded(page)
        assert page.locator(".cal-gantt-row").first.locator(".cal-gantt-slot").count() == 30
        context.close()
        browser.close()


def test_phone_overview_keeps_the_dot_calendar(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=390)
        page.goto(calendar_origin + "/?lang=cs")
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        assert page.locator(".cal-gantt-row").count() == 0
        assert page.locator(".cal-week").count() > 0
        shot(page, "overview-14-days-cs-390")
        context.close()
        browser.close()
