"""Overview 14-day card: calendar card look in fixed-days mode, month view one click away."""
from __future__ import annotations

from datetime import date, timedelta

from tests.test_dashboard_calendar import calendar_workspace, make_stay  # noqa: F401
from tests.test_dashboard_calendar_browser import (  # noqa: F401
    calendar_origin, launch, open_page, shot, sync_api, wait_loaded,
)

ROOT = "[data-calendar]"
FIXED = "is-fixed-days"


def root_classes(page):
    return page.get_attribute(ROOT, "class") or ""


def test_fourteen_day_mode_hides_filter_settings_and_title(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.goto(calendar_origin + "/?lang=cs")
        page.wait_for_selector(".cal-gantt-row")
        wait_loaded(page)
        assert FIXED in root_classes(page)
        assert page.locator("[data-cal-property]").is_hidden()
        assert page.locator("[data-cal-settings]").is_hidden()
        assert page.locator(".cal-toolbar h3").is_hidden()
        assert page.locator('[data-cal-view="calendar"]').is_visible()
        assert page.locator("[data-cal-prev]").is_visible()
        assert page.locator("[data-cal-today]").is_visible()
        assert page.locator("[data-cal-next]").is_visible()
        shot(page, "overview-0702-cs-1280")
        context.close()
        browser.close()


def test_done_bar_uses_green_pill_style(calendar_workspace, calendar_origin):
    today = date.today()
    make_stay(calendar_workspace["properties"][0], today.isoformat(), (today + timedelta(days=2)).isoformat())
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.goto(calendar_origin + "/?lang=cs")
        page.wait_for_selector(".cal-event")
        wait_loaded(page)
        # Tone "done" needs finished reports; the rule is checked on a bar with the class applied.
        style = page.locator(".cal-event").first.evaluate("""el => {
            el.classList.remove('is-neutral', 'is-overdue', 'is-action', 'is-ready');
            el.classList.add('is-done');
            const s = getComputedStyle(el);
            return {bg: s.backgroundColor, radius: parseFloat(s.borderTopLeftRadius)};
        }""")
        assert style["bg"] == "rgb(230, 245, 236)"
        assert style["radius"] >= 14
        context.close()
        browser.close()


def test_month_view_restores_controls_and_fourteen_days_comes_back(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.goto(calendar_origin + "/?lang=cs")
        page.wait_for_selector(".cal-gantt-row")
        wait_loaded(page)
        page.locator('[data-cal-view="calendar"]').click()
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        assert FIXED not in root_classes(page)
        assert page.locator("[data-cal-property]").is_visible()
        assert page.locator("[data-cal-settings]").is_visible()
        assert page.locator(".cal-toolbar h3").is_visible()
        assert page.locator("[data-cal-scales]").is_visible()
        page.locator("[data-cal-days]").click()
        page.wait_for_selector(".cal-gantt-row")
        wait_loaded(page)
        assert FIXED in root_classes(page)
        context.close()
        browser.close()


def test_cleaning_page_never_gets_fixed_days(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.goto(calendar_origin + "/cleaning?lang=cs")
        page.wait_for_selector(ROOT)
        wait_loaded(page)
        assert FIXED not in root_classes(page)
        context.close()
        browser.close()
