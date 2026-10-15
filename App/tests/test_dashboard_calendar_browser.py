"""Real pointer/keyboard booking flows and the automatic property-count view."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.test_dashboard_calendar import calendar_workspace, make_stay  # noqa: F401


@pytest.fixture(scope="module")
def calendar_origin(calendar_workspace):
    for index, property_id in enumerate(calendar_workspace["properties"]):
        make_stay(property_id, "2026-10-03", "2026-10-07",
                  summary=f"October booking {index + 1}", expected_guests_override=2)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    limit = time.time() + 15
    while not server.started and time.time() < limit:
        time.sleep(0.05)
    assert server.started
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def launch(playwright):
    try:
        return playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for calendar interaction coverage")


def open_page(browser, ws, origin, width=1280, locale="en", touch=False):
    context = browser.new_context(viewport={"width": width, "height": 1000}, has_touch=touch)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": ws["client"].cookies.get(auth.SESSION_COOKIE), "url": origin + "/"}])
    page = context.new_page()
    script_errors = []
    api_responses = []
    page.on("pageerror", lambda error: script_errors.append(str(error)))
    page.on("console", lambda message: script_errors.append(message.text) if message.type == "error" else None)
    page.on("response", lambda response: api_responses.append(response.status) if "/dashboard/calendar?" in response.url else None)
    response = page.goto(f"{origin}/?lang={locale}&cal_date=2026-10-01")
    try:
        page.wait_for_selector(".cal-gantt-row", timeout=10000)
    except Exception:
        shot(page, f"open-failed-{locale}-{width}")
        widget_state = {
            "rows": page.locator(".cal-gantt-row").count(),
            "weeks": page.locator(".cal-week").count(),
            "busy": page.locator("[data-cal-body]").get_attribute("aria-busy"),
        }
        raise AssertionError(
            f"Calendar did not start: HTTP {response.status}, URL {page.url}; "
            f"script errors={script_errors}; API responses={api_responses}; "
            f"widget={page.locator('[data-calendar]').inner_text()[:1600]}; "
            f"state={widget_state}"
        ) from None
    page.wait_for_function("() => document.querySelector('[data-cal-body]').getAttribute('aria-busy') === 'false'")
    later = page.locator("#security-prompt [data-security-prompt-later]")
    if later.is_visible():
        later.click()
    return context, page


def wait_loaded(page):
    page.wait_for_function("() => document.querySelector('[data-cal-body]').getAttribute('aria-busy') === 'false'")
    assert not page.locator("[data-cal-message]").is_visible() or page.locator("[data-cal-message]").inner_text() == "Stay created"


def shot(page, name):
    directory = os.environ.get("UBYHOST_SHOTS_DIR")
    if directory:
        Path(directory).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(directory) / f"calendar-{name}.png"), full_page=True)


def test_auto_view_threshold_filter_and_manual_override(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin)
        assert page.locator(".cal-gantt-row").count() == 3
        page.locator("[data-cal-property]").select_option(str(calendar_workspace["properties"][0]))
        page.wait_for_selector(".cal-week")
        assert page.locator("[data-cal-scale='month']").get_attribute("aria-pressed") == "true"
        page.locator("[data-cal-view='gantt']").click()
        page.wait_for_selector(".cal-gantt-row")
        assert page.locator(".cal-gantt-row").count() == 1
        page.locator("[data-cal-property]").select_option("")
        page.wait_for_function("() => document.querySelectorAll('.cal-gantt-row').length === 3")
        page.locator("[data-cal-view='calendar']").click()
        page.wait_for_selector(".cal-week")
        page.reload()
        page.wait_for_selector(".cal-week")
        assert page.locator("[data-cal-view='calendar']").get_attribute("aria-pressed") == "true"
        # A new visit without a view in the URL must still honor the manual choice.
        page.goto(f"{calendar_origin}/?lang=en&cal_date=2026-10-01")
        page.wait_for_selector(".cal-week")
        assert page.locator("[data-cal-view='calendar']").get_attribute("aria-pressed") == "true"
        page.locator("[data-cal-settings]").click()
        page.locator("[data-cal-auto]").check()
        page.wait_for_selector(".cal-gantt-row")
        for field in ("property", "label", "guests"):
            page.locator(f'[data-cal-display="{field}"]').uncheck()
        assert page.locator(".cal-event").first.locator("span").last.inner_text() == "Booked"
        for field in ("property", "label", "guests"):
            page.locator(f'[data-cal-display="{field}"]').check()
        page.locator("[data-cal-settings-dialog] [data-cal-close]").click()
        page.locator("[data-cal-property]").select_option(str(calendar_workspace["properties"][0]))
        page.wait_for_selector(".cal-week")
        page.locator("[data-cal-month]").fill("2028-02")
        page.wait_for_selector('[data-cal-day="2028-02-29"]')
        page.locator("[data-cal-scale='year']").click()
        page.wait_for_function("() => document.querySelectorAll('.cal-mini-title').length === 12")
        page.locator(".cal-mini-title").nth(1).click()
        page.wait_for_selector('[data-cal-day="2028-02-29"]')
        page.locator("[data-cal-scale='week']").click()
        page.wait_for_function("() => document.querySelectorAll('.cal-week').length === 1")
        context.close()
        browser.close()


def test_drag_nights_create_persist_and_open_details(calendar_workspace, calendar_origin):
    ws = calendar_workspace
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, ws, calendar_origin)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.locator("[data-cal-property]").select_option(str(ws["properties"][0]))
        page.wait_for_selector(".cal-week")
        first = page.locator('[data-cal-day="2026-10-26"]')
        last = page.locator('[data-cal-day="2026-10-28"]')
        first.scroll_into_view_if_needed()
        a, b = first.bounding_box(), last.bounding_box()
        page.mouse.move(a["x"] + a["width"] / 2, a["y"] + 15)
        page.mouse.down()
        page.mouse.move(b["x"] + b["width"] / 2, b["y"] + 15, steps=12)
        page.mouse.up()
        dialog = page.locator("[data-cal-create]")
        assert dialog.is_visible()
        assert page.locator("#cal-arrival").input_value() == "2026-10-26"
        assert page.locator("#cal-departure").input_value() == "2026-10-29"
        assert page.locator("#cal-property").input_value() == str(ws["properties"][0])
        assert page.locator("[data-cal-nights]").inner_text() == "3 nights"
        page.locator("#cal-guests").fill("2")
        page.locator("#cal-label").fill("Browser direct booking")
        shot(page, "drag-create-en-1280")
        with page.expect_response(lambda response: response.url.endswith("/reservations") and response.request.method == "POST") as saved:
            page.locator("[data-cal-save]").click()
        assert saved.value.status == 201
        row_id = saved.value.json()["id"]
        page.wait_for_selector("[data-cal-details][open]")
        assert page.locator("[data-cal-detail-content]").get_by_text("Browser direct booking", exact=True).is_visible()
        row = db.query_one("SELECT * FROM reservation WHERE id = ?", (row_id,))
        assert row["date_from"] == "2026-10-26" and row["date_to"] == "2026-10-29"
        assert row["source"] == "manual" and row["expected_guests_override"] == 2
        assert page.locator("[data-cal-open]").get_attribute("href").startswith(f"/reservations/{row_id}")
        shot(page, "saved-details-en-1280")
        page.locator("[data-cal-details] [data-cal-close]").click()
        page.wait_for_selector(f'[data-cal-event="{row_id}"]')
        page.locator(f'[data-cal-event="{row_id}"]').first.click()
        assert page.locator("[data-cal-details]").is_visible()
        assert not errors
        context.close()
        browser.close()


def test_keyboard_selection_cancel_and_overlap_confirmation(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin)
        page.locator("[data-cal-property]").select_option(str(calendar_workspace["properties"][1]))
        page.wait_for_selector(".cal-week")
        page.locator('[data-cal-day="2026-10-12"]').focus()
        page.keyboard.press("Shift+ArrowRight")
        page.keyboard.press("Shift+ArrowRight")
        page.keyboard.press("Enter")
        assert page.locator("#cal-arrival").input_value() == "2026-10-12"
        assert page.locator("#cal-departure").input_value() == "2026-10-15"
        page.keyboard.press("Escape")
        assert not page.locator("[data-cal-create]").is_visible()
        page.locator('[data-cal-day="2026-10-12"]').focus()
        page.keyboard.press("Shift+ArrowRight")
        page.locator("[data-cal-settings]").click()
        assert page.locator("[data-cal-settings-dialog]").is_visible()
        assert not page.locator("[data-cal-create]").is_visible()
        page.locator("[data-cal-settings-dialog] [data-cal-close]").click()
        page.locator('[data-cal-day="2026-10-05"]').click()
        assert page.locator("[data-cal-overlap]").is_visible()
        page.locator("[data-cal-save]").click()
        page.wait_for_function("() => document.querySelector('[data-cal-save-error]').textContent.length > 0")
        assert page.locator("[data-cal-create]").is_visible()
        page.locator('input[name="allow_overlap"]').check()
        with page.expect_response(lambda response: response.url.endswith("/reservations") and response.request.method == "POST") as saved:
            page.locator("[data-cal-save]").click()
        assert saved.value.status == 201
        page.wait_for_selector("[data-cal-details][open]")
        assert page.locator("[data-cal-detail-content]").get_by_text("Overlapping bookings", exact=True).is_visible()
        context.close()
        browser.close()


def test_reverse_gantt_drag_prefills_the_property_without_saving(calendar_workspace, calendar_origin):
    ws = calendar_workspace
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, ws, calendar_origin)
        property_id = ws["properties"][2]
        first = page.locator(f'.cal-gantt-slot[data-property="{property_id}"][data-date="2026-10-23"]')
        last = page.locator(f'.cal-gantt-slot[data-property="{property_id}"][data-date="2026-10-21"]')
        first.scroll_into_view_if_needed()
        last.scroll_into_view_if_needed()
        a, b = first.bounding_box(), last.bounding_box()
        before = db.query_one("SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ?", (property_id,))["n"]
        page.mouse.move(a["x"] + a["width"] / 2, a["y"] + a["height"] / 2)
        page.mouse.down()
        page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=12)
        page.mouse.up()
        assert page.locator("[data-cal-create]").is_visible()
        assert page.locator("#cal-property").input_value() == str(property_id)
        assert page.locator("#cal-arrival").input_value() == "2026-10-21"
        assert page.locator("#cal-departure").input_value() == "2026-10-24"
        page.keyboard.press("Escape")
        assert db.query_one("SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ?", (property_id,))["n"] == before
        context.close()
        browser.close()


def test_failed_load_preserves_view_and_can_retry(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin)
        page.route("**/dashboard/calendar?*", lambda route: route.abort())
        page.locator("[data-cal-next]").click()
        page.wait_for_function("() => document.querySelector('[data-cal-message]').textContent.includes('Try again')")
        assert page.locator(".cal-gantt-row").count() == 3
        page.unroute("**/dashboard/calendar?*")
        page.locator("[data-cal-message] button").click()
        wait_loaded(page)
        assert page.locator(".cal-gantt-row").count() == 3
        context.close()
        browser.close()


def test_calendar_geometry_locales_and_screenshots(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        for locale in ("en", "cs"):
            for width in (360, 390, 760, 1024, 1280, 1440, 1680, 1920, 2048):
                context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, locale=locale, touch=width < 761)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                for mode in ("gantt", "calendar"):
                    page.locator(f'[data-cal-view="{mode}"]').click()
                    page.wait_for_selector(".cal-gantt-row" if mode == "gantt" else ".cal-week")
                    wait_loaded(page)
                    if width <= 390:
                        target = page.locator(".cal-day-number" if mode == "calendar" else ".cal-gantt-slot").first
                        box = target.bounding_box()
                        assert box["width"] >= 43.9 and box["height"] >= 44, box
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                    shot(page, f"{mode}-{locale}-{width}")
                page.locator('[data-cal-day="2026-10-15"]').click()
                assert page.locator("[data-cal-create]").is_visible()
                assert page.locator("#cal-arrival").input_value() == "2026-10-15"
                assert page.locator("#cal-departure").input_value() == "2026-10-16"
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                shot(page, f"create-{locale}-{width}")
                page.keyboard.press("Escape")
                if width >= 1024:
                    toggle = page.locator("[data-sidebar-collapse]")
                    if toggle.is_visible():
                        toggle.click()
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                        shot(page, f"collapsed-{locale}-{width}")
                assert not errors
                context.close()
        browser.close()
