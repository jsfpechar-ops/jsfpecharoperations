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
    # Busy weeks must remain compact while every booking stays reachable.
    for index, summary in enumerate(
        ("Reserved", "! Reserved", "CLOSED - Not available", "Airbnb (Not available)", "Blocked")
    ):
        make_stay(calendar_workspace["properties"][index % 3], "2026-10-14", "2026-10-19",
                  summary=summary)
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
        page.wait_for_selector(".cal-gantt-row, .cal-week", timeout=10000)
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
        assert page.locator('[data-cal-scale="month"]').get_attribute("aria-pressed") == "true"
        page.locator('[data-cal-view="gantt"]').click()
        page.wait_for_selector(".cal-gantt-row")
        assert page.locator(".cal-gantt-row").count() == 1
        page.locator("[data-cal-property]").select_option("")
        page.wait_for_function("() => document.querySelectorAll('.cal-gantt-row').length === 3")
        page.locator('[data-cal-view="calendar"]').click()
        page.wait_for_selector(".cal-week")
        page.reload()
        page.wait_for_selector(".cal-week")
        assert page.locator('[data-cal-view="calendar"]').get_attribute("aria-pressed") == "true"
        # A new visit without a view in the URL must still honor the manual choice.
        page.goto(f"{calendar_origin}/?lang=en&cal_date=2026-10-01")
        page.wait_for_selector(".cal-week")
        assert page.locator('[data-cal-view="calendar"]').get_attribute("aria-pressed") == "true"
        # Imported booking-state placeholders never become visible bar titles.
        for word in ("Reserved", "CLOSED", "Not available", "Blocked"):
            assert page.locator(".cal-week-events").get_by_text(word, exact=False).count() == 0
        assert page.locator(".cal-event-mark").count() == 0
        # 0816: at 1280 px month tiles show stay chips instead of overlay bars.
        assert len(set(page.locator(".cal-tile-chip").evaluate_all(
            "nodes => nodes.map(node => getComputedStyle(node).borderLeftColor)"
        ))) >= 2
        more = page.locator('[data-cal-more="2026-10-14"]')
        assert more.is_visible()
        more.click()
        assert page.locator("[data-cal-day-dialog]").is_visible()
        assert page.locator("[data-cal-day-list] .cal-event").count() >= 4
        shot(page, "busy-day-details-en-1280")
        page.locator("[data-cal-day-dialog] [data-cal-close]").click()
        page.locator("[data-cal-settings]").click()
        page.locator("[data-cal-auto]").check()
        page.wait_for_selector(".cal-gantt-row")
        for field in ("property", "label", "guests"):
            page.locator(f'[data-cal-display="{field}"]').uncheck()
        assert page.locator(".cal-event").first.locator("span").last.inner_text() == "3 Oct – 7 Oct"
        for field in ("property", "label", "guests"):
            page.locator(f'[data-cal-display="{field}"]').check()
        page.locator("[data-cal-settings-dialog] [data-cal-close]").click()
        page.locator("[data-cal-property]").select_option(str(calendar_workspace["properties"][0]))
        page.wait_for_selector(".cal-week")
        # 0832: month and year selects are hidden in Month scale; the arrows walk from Oct 2026 to Feb 2028.
        for _ in range(16):
            page.locator("[data-cal-next]").click()
        page.wait_for_selector('[data-cal-day="2028-02-29"]')
        page.locator('[data-cal-scale="year"]').click()
        page.wait_for_function("() => document.querySelectorAll('.cal-mini-title').length === 12")
        page.locator(".cal-mini-title").nth(1).click()
        page.wait_for_selector('[data-cal-day="2028-02-29"]')
        page.locator('[data-cal-scale="week"]').click()
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
        assert page.locator("[data-cal-day-dialog]").is_visible()
        page.locator("[data-cal-day-add]").click()
        dialog = page.locator("[data-cal-create]")
        assert dialog.is_visible()
        assert page.locator("#cal-arrival").input_value() == "2026-10-26"
        assert page.locator("#cal-departure").input_value() == "2026-10-29"
        assert page.locator("#cal-property").input_value() == str(ws["properties"][0])
        assert page.locator("[data-cal-nights]").inner_text() == "3 nights"
        page.locator("#cal-guests").fill("2")
        page.locator("#cal-label").fill("Browser direct booking")
        shot(page, "drag-create-en-1280")
        with page.expect_response(lambda response: response.url.split("?")[0].endswith("/reservations") and response.request.method == "POST") as saved:
            page.locator("[data-cal-save]").click()
        assert saved.value.status == 201
        row_id = saved.value.json()["id"]
        page.locator('[data-cal-day="2026-10-26"]').click()
        live_booking = page.locator(f'[data-cal-day-list] .cal-event[data-cal-event="{row_id}"]')
        live_booking.wait_for(state="visible")
        live_booking.click()
        page.locator("[data-cal-details]").wait_for(state="visible")
        assert page.locator("[data-cal-detail-content]").get_by_text("Browser direct booking", exact=True).is_visible()
        row = db.query_one("SELECT * FROM reservation WHERE id = ?", (row_id,))
        assert row["date_from"] == "2026-10-26" and row["date_to"] == "2026-10-29"
        assert row["source"] == "manual" and row["expected_guests_override"] == 2
        assert page.locator("[data-cal-open]").get_attribute("href").startswith(f"/reservations/{row_id}")
        shot(page, "saved-details-en-1280")
        page.locator("[data-cal-details] [data-cal-close]").click()
        page.locator('[data-cal-day="2026-10-26"]').click()
        page.locator(f'[data-cal-day-list] .cal-event[data-cal-event="{row_id}"]').click()
        page.locator("[data-cal-details]").wait_for(state="visible")
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
        page.locator("[data-cal-day-add]").click()
        assert page.locator("#cal-arrival").input_value() == "2026-10-12"
        assert page.locator("#cal-departure").input_value() == "2026-10-15"
        page.keyboard.press("Escape")
        page.locator("[data-cal-create]").wait_for(state="hidden")  # 0401: the dialog fades out
        page.locator('[data-cal-day="2026-10-12"]').focus()
        page.keyboard.press("Shift+ArrowRight")
        page.locator("[data-cal-settings]").click()
        assert page.locator("[data-cal-settings-dialog]").is_visible()
        assert not page.locator("[data-cal-create]").is_visible()
        page.locator("[data-cal-settings-dialog] [data-cal-close]").click()
        page.locator('[data-cal-day="2026-10-05"]').click()
        page.locator("[data-cal-day-add]").click()
        assert page.locator("[data-cal-overlap]").is_visible()
        overlap_arrival = page.locator("#cal-arrival").input_value()
        overlap_departure = page.locator("#cal-departure").input_value()
        page.locator("[data-cal-save]").click()
        page.wait_for_function("() => document.querySelector('[data-cal-save-error]').textContent.length > 0")
        assert page.locator("[data-cal-create]").is_visible()
        page.locator('input[name="allow_overlap"]').check()
        with page.expect_response(lambda response: response.url.split("?")[0].endswith("/reservations") and response.request.method == "POST") as saved:
            page.locator("[data-cal-save]").click()
        assert saved.value.status == 201
        row_id = saved.value.json()["id"]
        assert page.evaluate("location.pathname") == "/"
        message = page.locator("[data-cal-message]")
        message.wait_for(state="visible")
        open_link = page.locator("[data-cal-message] a")
        open_link.wait_for(state="visible")
        open_href = open_link.get_attribute("href")
        assert open_href.split("?")[0] == f"/reservations/{row_id}" and "lang=en" in open_href
        row = db.query_one("SELECT date_from, date_to FROM reservation WHERE id = ?", (row_id,))
        assert row["date_from"] == overlap_arrival and row["date_to"] == overlap_departure
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
                for mode in (("calendar",) if width < 768 else ("gantt", "calendar")):
                    if width >= 768:
                        page.locator(f'[data-cal-view="{mode}"]').click()
                    page.wait_for_selector(".cal-gantt-row" if mode == "gantt" else ".cal-week")
                    wait_loaded(page)
                    # 0832: the calendar page is full-page at every width: the summary and "Full calendar" blocks are hidden.
                    boxes = page.evaluate("""() => ['[data-dashboard-refresh="stats"]', '.ov-cal-more', '#calendar'].map(selector => {
                        const r = document.querySelector(selector).getBoundingClientRect();
                        return {top:r.top, bottom:r.bottom, left:r.left, right:r.right, height:r.height};
                    })""")
                    assert boxes[0]["height"] == 0 and boxes[1]["height"] == 0, boxes
                    assert boxes[2]["height"] > 0, boxes
                    if width >= 768:
                        icon = page.locator("[data-cal-settings] svg").bounding_box()
                        assert icon["width"] >= 18 and icon["height"] >= 18, icon
                    if width >= 1024:
                        if mode == "calendar":
                            heights = page.locator(".cal-week").evaluate_all(
                                "nodes => nodes.map(node => node.getBoundingClientRect().height)"
                            )
                            assert max(heights) <= 140, heights
                    control_heights = page.locator(
                        ".cal-view-segment, .cal-scale-segment, [data-cal-property], [data-cal-month], "
                        "[data-cal-year], [data-cal-settings], [data-cal-today], [data-cal-prev], [data-cal-next]"
                    ).evaluate_all(
                        "nodes => nodes.filter(node => node.offsetParent).map(node => node.getBoundingClientRect().height)"
                    )
                    assert control_heights and max(control_heights) - min(control_heights) <= 1, control_heights
                    if width < 768:
                        assert page.locator(".cal-week-events .cal-event").count() == 0
                        assert page.locator(".cal-dots .cal-dot").count() >= 3
                        shown = page.locator(
                            ".cal-view-segment, .cal-scale-segment, [data-cal-month], [data-cal-year], [data-cal-settings]"
                        ).evaluate_all("nodes => nodes.filter(node => node.offsetParent).length")
                        assert shown == 0, shown
                        box = page.locator(".cal-day-number").first.bounding_box()
                        assert box["width"] >= 43.9 and box["height"] >= 44, box
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                    shot(page, f"{mode}-{locale}-{width}")
                page.locator('[data-cal-day="2026-10-15"]').click()
                assert page.locator("[data-cal-day-dialog]").is_visible()
                assert page.locator("[data-cal-day-list] .cal-event").count() >= 1
                page.locator("[data-cal-day-add]").click()
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


def test_calendar_week_boundary_clips_fractional_checkout_with_continuation_edges(calendar_workspace, calendar_origin, request):
    ws = calendar_workspace
    template = db.query_one("SELECT legal_entity_id FROM apartment WHERE id = ?", (ws["properties"][0],))
    apartment_id = db.insert("apartment", {
        "owner_user_id": ws["owner"], "legal_entity_id": template["legal_entity_id"],
        "internal_name": "Week boundary fixture", "active": 1, "created_at": db.utcnow(),
        "automation_mode": "manual", "checkin_hour": 15, "checkout_hour": 11,
    })
    def cleanup():
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    request.addfinalizer(cleanup)
    stay_id = make_stay(apartment_id, "2026-10-18", "2026-10-20", summary="Boundary booking")
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, ws, calendar_origin, width=1280, locale="en")
        # 0816: bars are week-scale only; the stay crosses the Sunday/Monday row break, so check each row.
        page.goto(f"{calendar_origin}/?lang=en&cal_date=2026-10-18&cal_view=calendar&cal_scale=week&cal_property={apartment_id}")
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        first = page.locator(f'.cal-event[data-cal-event="{stay_id}"]')
        first.wait_for(state="visible")
        assert first.count() == 1
        assert first.get_attribute("class").find("continues-end") >= 0
        first_box = first.bounding_box()
        sun = page.locator('.cal-day[data-date="2026-10-18"]').last.bounding_box()
        expected_start = sun["x"] + sun["width"] * 15 / 24
        expected_first_right = sun["x"] + sun["width"]
        assert abs(first_box["x"] - expected_start) <= 4, (first_box, expected_start)
        assert abs(first_box["x"] + first_box["width"] - expected_first_right) <= 4, (first_box, expected_first_right)
        page.locator("[data-cal-next]").click()
        wait_loaded(page)
        second = page.locator(f'.cal-event[data-cal-event="{stay_id}"]')
        second.wait_for(state="visible")
        assert second.count() == 1
        assert second.get_attribute("class").find("continues-start") >= 0
        second_box = second.bounding_box()
        mon = page.locator('.cal-day[data-date="2026-10-19"]').last.bounding_box()
        tue = page.locator('.cal-day[data-date="2026-10-20"]').last.bounding_box()
        expected_monday = mon["x"]
        expected_checkout = tue["x"] + tue["width"] * 11 / 24
        assert abs(second_box["x"] - expected_monday) <= 4, (second_box, expected_monday)
        assert abs(second_box["x"] + second_box["width"] - expected_checkout) <= 4, (second_box, expected_checkout)
        shot(page, "checkout-week-boundary-en-1280")
        context.close()
        browser.close()


def test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place(calendar_workspace, calendar_origin):
    ws = calendar_workspace
    # Dashboard copy links use the apartment's authorized public token.
    db.update("apartment", ws["properties"][0], {"permalink_token": "refresh-copy-test-token"})
    existing_stay = make_stay(ws["properties"][2], "2026-10-21", "2026-10-22",
                              summary="Existing details stay", expected_guests_override=2)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, ws, calendar_origin, width=1280)
        pathname = page.evaluate("location.pathname")

        # The calendar day itself remains a usable entry point to the default Stay form.
        page.locator("[data-cal-day]:visible").first.click()
        assert page.locator("[data-cal-create]").is_visible()
        assert page.locator('[data-cal-type-choice="stay"]').get_attribute("aria-pressed") == "true"
        shot(page, "dashboard-stay-popup-en")
        page.locator("[data-cal-create] .cal-close").click()

        page.locator("[data-cal-day]:visible").first.click()
        page.locator('[data-cal-type-choice="cleaning"]').click()
        assert page.locator('[data-cal-type-choice="cleaning"]').get_attribute("aria-pressed") == "true"
        page.locator("#cal-property").select_option(str(ws["properties"][0]))
        page.locator("#cal-clean-date").fill("2026-10-27")
        page.locator("#cal-clean-notes").fill("Calendar popup")
        shot(page, "dashboard-cleaning-popup-en")
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  response.url.split("?")[0].endswith("/cleaning/events")) as result:
            page.locator("[data-cal-save]").click()
        created_cleaning = result.value.json()
        assert result.value.status == 201
        assert page.evaluate("location.pathname") == pathname
        cleaning_event_id = f"cleaning:{created_cleaning['id']}"
        saved_cleanings = db.query(
            "SELECT id, apartment_id, scheduled_date FROM cleaning_event WHERE id = ?",
            (created_cleaning["id"],),
        )
        assert len(saved_cleanings) == 1
        assert saved_cleanings[0]["apartment_id"] == ws["properties"][0]
        assert saved_cleanings[0]["scheduled_date"] == "2026-10-27"
        assert page.locator(f'.cal-gantt-events .cal-event[data-cal-event="{cleaning_event_id}"]').count() == 0
        shot(page, "dashboard-cleaning-absent-gantt-en")

        page.locator('[data-cal-view="calendar"]').click()
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        assert page.locator(f'.cal-week-events .cal-event[data-cal-event="{cleaning_event_id}"]').count() == 0
        page.locator('[data-cal-scale="year"]').click()
        page.wait_for_function("() => document.querySelectorAll('.cal-mini-title').length === 12")
        assert page.locator(f'.cal-event[data-cal-event="{cleaning_event_id}"]').count() == 0
        page.locator('[data-cal-scale="month"]').click()
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        busy_day = page.locator('[data-cal-more="2026-10-14"]')
        assert busy_day.is_visible()
        busy_day.click()
        assert page.locator(f'[data-cal-day-list] .cal-event[data-cal-event="{cleaning_event_id}"]').count() == 0
        page.locator("[data-cal-day-dialog] [data-cal-close]").click()
        shot(page, "dashboard-cleaning-absent-en")

        cleaning_page = context.new_page()
        cleaning_page.goto(f"{calendar_origin}/cleaning?lang=en&cal_date=2026-10-27&cal_view=calendar")
        cleaning_page.wait_for_selector("[data-calendar]")
        wait_loaded(cleaning_page)
        # 0834: the /cleaning tile calendar shows cleaning tags only, so the saved cleaning is checked
        # on its day tag (month view) and in that day's sheet.
        cleaning_tag_day = cleaning_page.locator('.cal-day[data-date="2026-10-27"].has-cleaning')
        cleaning_tag_day.wait_for(state="visible")
        assert cleaning_tag_day.locator(".cal-clean-tag").count() >= 1
        cleaning_tag_day.locator(".cal-day-number").click()
        cleaning_marker = cleaning_page.locator(
            f'[data-cal-day-list] .cal-event[data-cal-event="{cleaning_event_id}"]'
        )
        cleaning_marker.wait_for(state="visible")
        assert "27" in cleaning_page.locator("[data-cal-day-dialog] #cal-day-title").inner_text()
        shot(cleaning_page, "cleaning-calendar-created-marker-en")
        cleaning_page.close()

        assert page.locator(".cal-tile-chip").count() >= 1
        page.locator('[data-cal-day="2026-10-21"]').click()
        booking = page.locator(f'[data-cal-day-list] .cal-event[data-cal-event="{existing_stay}"]')
        assert booking.count() == 1
        booking.click()
        action = page.locator("[data-cal-details] [data-cal-open]")
        assert action.is_visible() and action.inner_text().strip() == "Open stay"
        page.locator("[data-cal-details] [data-cal-close]").click()
        if page.locator("[data-cal-day-dialog][open]").count():
            page.locator("[data-cal-day-dialog] [data-cal-close]").click()

        # 0834: after the booking sheet the day click opens the day sheet, whose Add button opens the Stay form.
        page.locator("[data-cal-day]:visible").first.click()
        if page.locator("[data-cal-day-dialog][open]").count():
            page.locator("[data-cal-day-add]").click()
        page.locator('[data-cal-type-choice="stay"]').click()
        form = page.locator("[data-cal-form]")
        form.locator("#cal-property").select_option(str(ws["properties"][0]))
        arrival, departure = page.evaluate("""today => {
            const start = new Date(today + "T12:00:00Z");
            const end = new Date(start);
            end.setUTCDate(end.getUTCDate() + 2);
            return [start.toISOString().slice(0, 10), end.toISOString().slice(0, 10)];
        }""", page.locator("[data-calendar]").get_attribute("data-today"))
        form.locator("#cal-arrival").fill(arrival)
        form.locator("#cal-departure").fill(departure)
        form.locator("#cal-guests").fill("2")
        form.locator("#cal-label").fill("Popup row refresh")
        overlap = form.locator('input[name="allow_overlap"]')
        if overlap.count() and overlap.is_visible():
            overlap.check()
        shot(page, "dashboard-stay-save-popup-en")
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  response.url.split("?")[0].endswith("/reservations")) as stay_result:
            page.locator("[data-cal-save]").click()
        created_stay = stay_result.value.json()
        assert stay_result.value.status == 201
        assert page.evaluate("location.pathname") == pathname
        # 0241: the new stay arrives today with no guest form, so "What needs you" gains its line.
        line = page.locator(
            f'[data-dashboard-refresh="stats"] .todo .card[data-needs-you-stay="{created_stay["id"]}"]'
        )
        line.wait_for(state="attached")
        assert "Popup row refresh" in line.text_content()
        line_button = line.locator("[data-needs-you-go]")
        assert line_button.count() == 1
        assert line_button.get_attribute("href").startswith(f"/reservations/{created_stay['id']}?")
        # Re-delivering the scoped update must not double-bind imported controls.
        page.evaluate("""() => {
            const root = document.querySelector('[data-dashboard-refresh="stats"]');
            document.dispatchEvent(new CustomEvent("ubyhost:content-updated", {detail: {root}}));
            document.dispatchEvent(new CustomEvent("ubyhost:content-updated", {detail: {root}}));
        }""")
        assert line.count() == 1

        # Dashboard has no dismissible banner in every fixture; exercise the same
        # scoped binder with a transient banner under the refreshed work region.
        banner_id = page.evaluate("""() => {
            const root = document.querySelector('#calendar');
            const banner = document.createElement("aside");
            banner.className = "dismissible-banner";
            banner.id = "refresh-dismiss-banner";
            const button = document.createElement("button");
            button.type = "button";
            button.setAttribute("data-dismiss-banner", "");
            button.textContent = "Dismiss test banner";
            banner.append(button);
            root.append(banner);
            document.dispatchEvent(new CustomEvent("ubyhost:content-updated", {detail: {root}}));
            return banner.id;
        }""")
        page.locator(f'#{banner_id} [data-dismiss-banner]').click()
        assert page.locator(f"#{banner_id}").count() == 0

        shot(page, "dashboard-calendar-create-refresh-en")
        # 0832: the full calendar has no summary block; open the new stay from its day in the grid.
        page.locator(f'[data-cal-day="{arrival}"]').click()
        page.locator(f'[data-cal-day-list] .cal-event[data-cal-event="{created_stay["id"]}"]').click()
        with page.expect_navigation():
            page.locator("[data-cal-details] [data-cal-open]").click()
        assert page.url.split("?")[0].endswith(f"/reservations/{created_stay['id']}")
        context.close()
        browser.close()


@pytest.mark.parametrize("width", [360, 1280])
def test_create_popover_reclamps_when_switching_to_taller_stay_form(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width)
        page.locator("[data-cal-day]:visible").last.scroll_into_view_if_needed()
        page.locator("[data-cal-day]:visible").last.click()
        if width < 768:
            page.locator("[data-cal-day-add]").click()
        dialog = page.locator("[data-cal-create]")
        assert dialog.is_visible()
        page.locator('[data-cal-type-choice="cleaning"]').click()
        page.locator('[data-cal-type-choice="stay"]').click()
        box = dialog.bounding_box()
        viewport = page.evaluate("({width: innerWidth, height: innerHeight})")
        assert box["x"] >= 0 and box["y"] >= 0
        assert box["x"] + box["width"] <= viewport["width"] + 1
        assert box["y"] + box["height"] <= viewport["height"] + 1
        shot(page, f"create-popover-reclamp-{width}")
        context.close()
        browser.close()


def test_dashboard_committed_stay_refresh_retry_does_not_post_twice(calendar_workspace, calendar_origin):
    ws = calendar_workspace
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, ws, calendar_origin, width=1280)
        before = page.evaluate("""() => {
            const normalize = value => (value || "").replace(/\\s+/g, " ").trim();
            return {
                stats: normalize(document.querySelector('[data-dashboard-refresh="stats"]')?.textContent),
                rows: [...document.querySelectorAll('[data-dashboard-refresh="stats"] .todo .card[data-needs-you="stay"]')].map(row => ({
                    id: row.getAttribute("data-needs-you-stay"),
                    text: normalize(row.textContent)
                }))
            };
        }""")
        assert before["rows"], "fixture should show stay lines before the committed save"
        failed_html = {"done": False}
        posts = []
        def fail_first_dashboard_html(route):
            request = route.request
            if request.method == "POST" and request.url.split("?")[0].endswith("/reservations"):
                posts.append(request.url)
            if (not failed_html["done"] and request.method == "GET" and
                    request.url.split("?")[0] == calendar_origin + "/" and
                    "text/html" in request.headers.get("accept", "")):
                failed_html["done"] = True
                route.abort()
            else:
                route.continue_()
        page.route("**/*", fail_first_dashboard_html)
        page.locator("[data-cal-day]:visible").first.click()
        page.locator('[data-cal-type-choice="stay"]').click()
        form = page.locator("[data-cal-form]")
        form.locator("#cal-property").select_option(str(ws["properties"][0]))
        arrival, departure = page.evaluate("""today => {
            const start = new Date(today + "T12:00:00Z");
            const end = new Date(start);
            end.setUTCDate(end.getUTCDate() + 2);
            return [start.toISOString().slice(0, 10), end.toISOString().slice(0, 10)];
        }""", page.locator("[data-calendar]").get_attribute("data-today"))
        form.locator("#cal-arrival").fill(arrival)
        form.locator("#cal-departure").fill(departure)
        form.locator("#cal-guests").fill("2")
        form.locator("#cal-label").fill("Refresh retry stay")
        # This test is about the save-retry flow, not overlap rules. Date fills reset the
        # checkbox, so allow the overlap here, after the dates are set. The server still
        # checks overlaps; the client may not know about every stay on today's date.
        form.locator('input[name="allow_overlap"]').evaluate("el => { el.checked = true; }")
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  response.url.split("?")[0].endswith("/reservations")) as result:
            page.locator("[data-cal-save]").click()
        saved = result.value.json()
        assert result.value.status == 201
        message = page.locator("[data-cal-message]")
        page.wait_for_function("""() => document.querySelector('[data-cal-message]')?.textContent.includes('Saved, but the calendar or list could not refresh.')""")
        assert "Saved, but the calendar or list could not refresh." in message.inner_text()
        assert page.locator('[data-cal-message] a').is_visible()
        retry = page.locator("[data-cal-message] button")
        assert retry.is_visible() and len(posts) == 1

        # Change an existing stay's label so the successful retry proves it replaced stale HTML.
        target_id = before["rows"][0]["id"]
        sentinel = f"Refresh retry sentinel {saved['id']}"
        assert sentinel not in before["rows"][0]["text"]
        db.update("reservation", target_id, {"summary": sentinel})
        with page.expect_response(lambda response: response.request.method == "GET" and
                                      response.url.split("?")[0] == calendar_origin + "/" and
                                      "text/html" in response.request.headers.get("accept", "")) as refreshed:
            retry.click()
        fresh_response = refreshed.value
        fresh_html = fresh_response.text()
        assert fresh_response.status == 200
        expected = page.evaluate("""html => {
            const doc = new DOMParser().parseFromString(html, "text/html");
            doc.querySelectorAll("noscript").forEach(node => node.remove());
            const normalize = value => (value || "").replace(/\\s+/g, " ").trim(); const rowText = row => { const c = row.cloneNode(true); c.querySelectorAll("[data-copy]").forEach(n => n.remove()); return (c.textContent || "").replace(/\\s+/g, " ").trim(); };
            return {
                stats: normalize(doc.querySelector('[data-dashboard-refresh="stats"]')?.textContent),
                rows: [...doc.querySelectorAll('[data-dashboard-refresh="stats"] .todo .card[data-needs-you="stay"]')].map(row => ({
                    id: row.getAttribute("data-needs-you-stay"),
                    text: rowText(row)
                }))
            };
        }""", fresh_html)
        assert any(row["id"] == target_id and sentinel in row["text"] for row in expected["rows"])
        saved_row = db.query_one("SELECT date_from, date_to, expected_guests_override, summary FROM reservation WHERE id = ?", (saved["id"],))
        assert (saved_row["date_from"], saved_row["date_to"], saved_row["expected_guests_override"], saved_row["summary"]) == (
            arrival, departure, 2, "Refresh retry stay"
        )
        page.wait_for_function("""expected => {
            const normalize = value => (value || "").replace(/\\s+/g, " ").trim(); const rowText = row => { const c = row.cloneNode(true); c.querySelectorAll("[data-copy]").forEach(n => n.remove()); return (c.textContent || "").replace(/\\s+/g, " ").trim(); };
            const actual = {
                stats: normalize(document.querySelector('[data-dashboard-refresh="stats"]')?.textContent),
                rows: [...document.querySelectorAll('[data-dashboard-refresh="stats"] .todo .card[data-needs-you="stay"]')].map(row => ({
                    id: row.getAttribute("data-needs-you-stay"),
                    text: rowText(row)
                }))
            };
            return JSON.stringify(actual) === JSON.stringify(expected);
        }""", arg=expected)
        assert len(posts) == 1
        assert db.query_one("SELECT COUNT(*) AS n FROM reservation WHERE id = ?", (saved["id"],))["n"] == 1
        shot(page, "dashboard-refresh-retry-en")
        context.close()
        browser.close()



def test_default_calendar_url_is_clean_and_specific_views_survive_reload(
    calendar_workspace, calendar_origin,
):
    from urllib.parse import parse_qs, urlsplit

    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=390)
        page.goto(calendar_origin + "/?cal_view=calendar")
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        assert urlsplit(page.url).query == "cal_view=calendar"
        today = page.locator("[data-calendar]").get_attribute("data-today")
        shot(page, "clean-url-dashboard-390")
        page.set_viewport_size({"width": 1280, "height": 1000})
        page.goto(
            f"{calendar_origin}/?cal_view=auto&cal_date={today}&cal_scale=month&lang=en#calendar"
        )
        page.wait_for_selector(".cal-gantt-row, .cal-week")
        wait_loaded(page)
        assert parse_qs(urlsplit(page.url).query) == {"lang": ["en"]}
        assert urlsplit(page.url).fragment == "calendar"

        property_id = str(calendar_workspace["properties"][0])
        page.goto(
            f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2028-02-15"
            f"&cal_scale=week&cal_property={property_id}#calendar"
        )
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        for _ in range(2):
            params = parse_qs(urlsplit(page.url).query)
            assert params == {
                "lang": ["en"], "cal_view": ["calendar"], "cal_date": ["2028-02-15"],
                "cal_scale": ["week"], "cal_property": [property_id],
            }
            assert urlsplit(page.url).fragment == "calendar"
            assert page.locator("[data-cal-property]").input_value() == property_id
            assert page.locator('[data-cal-scale="week"]').get_attribute("aria-pressed") == "true"
            page.reload()
            page.wait_for_selector(".cal-week")
            wait_loaded(page)

        page.locator("[data-cal-today]").click()
        wait_loaded(page)
        assert "cal_date" not in parse_qs(urlsplit(page.url).query)
        page.locator("[data-cal-settings]").click()
        page.locator("[data-cal-auto]").check()
        wait_loaded(page)
        page.locator("[data-cal-settings-dialog] [data-cal-close]").click()
        page.locator("[data-cal-property]").select_option("")
        wait_loaded(page)
        assert parse_qs(urlsplit(page.url).query) == {"lang": ["en"]}
        context.close()
        browser.close()


def test_app_root_login_works_without_javascript_and_keeps_the_root_address(
    calendar_origin, monkeypatch,
):
    from app import config

    monkeypatch.setattr(config, "APP_BASE_URL", calendar_origin)
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://public.ubyhost.test")
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context = browser.new_context(
            viewport={"width": 390, "height": 844}, java_script_enabled=False,
        )
        page = context.new_page()
        response = page.goto(calendar_origin + "/?lang=en")
        assert response.status == 200
        assert page.url == calendar_origin + "/?lang=en"
        assert page.locator('form[action="/login"]').is_visible()
        assert page.locator('form[action="/login"] input[name="_csrf"]').input_value()
        assert page.locator("body").evaluate(
            "node => node.scrollWidth <= window.innerWidth"
        )
        shot(page, "app-root-login-390")
        context.close()
        browser.close()



def test_explicit_auto_view_survives_reload_over_a_saved_manual_preference(
    calendar_workspace, calendar_origin,
):
    from urllib.parse import parse_qs, urlsplit

    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin)
        page.evaluate(
            "() => localStorage.setItem('ubyhost.calendar.display.v1', JSON.stringify({mode: 'calendar'}))"
        )
        page.goto(calendar_origin + "/?lang=en&cal_view=auto")
        page.wait_for_selector(".cal-gantt-row")
        wait_loaded(page)
        assert parse_qs(urlsplit(page.url).query)["cal_view"] == ["auto"]
        page.reload()
        page.wait_for_selector(".cal-gantt-row")
        wait_loaded(page)
        page.locator("[data-cal-settings]").click()
        page.locator("[data-cal-auto]").uncheck()
        wait_loaded(page)
        page.locator("[data-cal-auto]").check()
        wait_loaded(page)
        assert "cal_view" not in parse_qs(urlsplit(page.url).query)
        context.close()
        browser.close()


def tile(page, day):
    # The day cell itself: the [data-cal-day] node or its nearest .cal-day ancestor.
    return page.locator(f'[data-cal-day="{day}"]').locator(
        "xpath=ancestor-or-self::*[contains(concat(' ', normalize-space(@class), ' '), ' cal-day ')][1]")


TASK_SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0814"


def save_task_shot(page, name):
    """0816 screenshots: written only when UBYHOST_TASK_SHOTS=1, after every dialog and panel is fully opaque."""
    if os.environ.get("UBYHOST_TASK_SHOTS") != "1":
        return
    page.wait_for_function(
        "() => [...document.querySelectorAll('dialog[open], [data-cal-day-dialog][open]')].every(d => getComputedStyle(d).opacity === '1')"
    )
    page.screenshot(path=str(TASK_SHOTS / name), full_page=False)


@pytest.mark.parametrize("width", [768, 1024, 1280, 1440])
def test_month_tiles_and_side_panel(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width)
        # 0832: the calendar page is full-page: the dashboard blocks are hidden at every width.
        page.goto(f"{calendar_origin}/?lang=en&cal_date=2026-10-01&cal_view=calendar")
        page.wait_for_selector("[data-calendar]")
        wait_loaded(page)
        assert page.locator("#needs-action:visible, .ov-cal-more:visible, .hs:visible").count() == 0
        assert page.evaluate("(() => { const h = document.querySelector('.cal-toolbar h3'); return h.scrollWidth <= h.clientWidth; })()")
        assert page.locator("[data-cal-settings]").evaluate("node => getComputedStyle(node).backgroundColor") != "rgb(208, 69, 45)"
        page.locator('[data-cal-view="calendar"]').click()
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        assert page.locator("[data-cal-month]:visible, [data-cal-year]:visible").count() == 0
        page.evaluate("window.scrollTo(0, 0)")
        assert page.locator(".cal-week-events .cal-event").count() == 0
        heights = page.locator(".cal-week-days .cal-day").evaluate_all(
            "nodes => nodes.filter(node => node.offsetParent).map(node => node.getBoundingClientRect().height)"
        )
        assert min(heights) >= 93, heights  # 0891: Airbnb tiles are 94 px
        day10 = page.locator('[data-cal-day="2026-10-10"]').bounding_box()
        day11 = page.locator('[data-cal-day="2026-10-11"]').bounding_box()
        assert day11["x"] - (day10["x"] + day10["width"]) >= 6, (day10, day11)
        assert page.locator('[data-cal-day="2026-10-03"] .cal-tile-chip').count() >= 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        save_task_shot(page, f"calendar-{width}.png")

        page.locator('[data-cal-day="2026-10-10"]').click()
        page.locator('[data-cal-day="2026-10-12"]').click()
        for day in ("2026-10-10", "2026-10-11", "2026-10-12"):
            backgrounds = [tile(page, day).evaluate("node => getComputedStyle(node).backgroundColor"),
                           page.locator(f'[data-cal-day="{day}"]').evaluate("node => getComputedStyle(node).backgroundColor")]
            assert "rgb(34, 34, 34)" in backgrounds, (day, backgrounds)
        panel = page.locator("[data-cal-day-dialog]")
        assert panel.is_visible()
        assert page.evaluate("document.querySelector('[data-cal-day-dialog]').matches(':modal')") is False
        box = panel.bounding_box()
        assert abs(box["x"] + box["width"] - width) <= 1, box
        last_tile = page.locator('[data-cal-day="2026-10-12"]').bounding_box()
        assert box["x"] >= last_tile["x"] + last_tile["width"] or box["x"] >= width - 400, (box, last_tile)
        close = page.locator("[data-cal-day-dialog] [data-cal-close]").bounding_box()
        assert abs(close["width"] - 40) <= 1 and abs(close["height"] - 40) <= 1, close
        add = page.locator("[data-cal-day-add]").bounding_box()
        assert add["height"] >= 44 and box["y"] + box["height"] - (add["y"] + add["height"]) >= 24, (add, box)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        panel_left = page.locator("[data-cal-day-dialog]").bounding_box()["x"]
        for selector in (".cal-toolbar button, .cal-toolbar select", ".cal-heading button, .cal-heading select"):
            for control in page.locator(selector).all():
                if control.is_visible():
                    box = control.bounding_box()
                    assert box["x"] + box["width"] <= panel_left + 1, (selector, box, panel_left)
        grid = page.locator(".cal-body").bounding_box()
        assert grid["x"] + grid["width"] >= panel_left - 24, (grid, panel_left)
        for selector in ("[data-cal-prev]", "[data-cal-today]", "[data-cal-next]"):
            assert page.locator(selector).evaluate("node => getComputedStyle(node).backgroundColor") != "rgb(208, 69, 45)", selector
        assert page.locator("#needs-action:visible, .ov-cal-more:visible, .hs:visible").count() == 0
        assert page.locator("[data-cal-settings]").evaluate("node => getComputedStyle(node).backgroundColor") != "rgb(208, 69, 45)"
        assert page.locator("[data-cal-month]:visible, [data-cal-year]:visible").count() == 0
        assert page.evaluate("(() => { const h = document.querySelector('.cal-toolbar h3'); return h.scrollWidth <= h.clientWidth; })()")
        if width == 768:
            # 0891: stays are dark pills over the tiles; the per-day chips are hidden.
            assert page.locator(".cal-pill").count() >= 1
            assert page.locator(".cal-tile-chip:visible").count() == 0
        assert not page.locator(".havel-fab").is_visible()
        save_task_shot(page, f"calendar-range-{width}.png") if width in (768, 1280) else None

        page.locator("[data-cal-day-add]").click()
        assert page.locator("[data-cal-create]").is_visible()
        assert page.locator("#cal-arrival").input_value() == "2026-10-10"
        assert page.locator("#cal-departure").input_value() == "2026-10-13"
        create_close = page.locator("[data-cal-create] .cal-close").bounding_box()
        assert abs(create_close["width"] - 40) <= 1 and abs(create_close["height"] - 40) <= 1, create_close
        save_task_shot(page, "calendar-create-1280.png") if width == 1280 else None
        context.close()
        browser.close()


def test_mouse_drag_opens_panel(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.locator('[data-cal-view="calendar"]').click()
        page.wait_for_selector(".cal-week")
        wait_loaded(page)
        page.locator('[data-cal-day="2026-10-05"]').scroll_into_view_if_needed()
        page.wait_for_timeout(300)  # the dashboard settles its scroll after load
        first = page.locator('[data-cal-day="2026-10-03"]').bounding_box()
        last = page.locator('[data-cal-day="2026-10-05"]').bounding_box()
        page.mouse.move(first["x"] + first["width"] / 2, first["y"] + 15)
        page.mouse.down()
        page.mouse.move(last["x"] + last["width"] / 2, last["y"] + 15, steps=12)
        page.mouse.up()
        assert page.locator("[data-cal-day-dialog]").is_visible()
        assert page.evaluate("document.querySelector('[data-cal-day-dialog]').matches(':modal')") is False
        for day in ("2026-10-03", "2026-10-04", "2026-10-05"):
            backgrounds = [tile(page, day).evaluate("node => getComputedStyle(node).backgroundColor"),
                           page.locator(f'[data-cal-day="{day}"]').evaluate("node => getComputedStyle(node).backgroundColor")]
            assert "rgb(34, 34, 34)" in backgrounds, (day, backgrounds)
        assert page.locator("[data-cal-create]").is_hidden()
        context.close()
        browser.close()


def test_calendar_view_hides_today_table_and_alert_stack_0835(calendar_workspace, calendar_origin):
    # 0835: the full-page calendar at 1280 px shows no Today table and no alert stack.
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-10-01")
        wait_loaded(page)
        assert page.locator(".ov-table").first.is_hidden()
        visible = [node.evaluate("n => { const out = []; for (let e = n; e && out.length < 9; e = e.parentElement) out.push(e.tagName + '.' + e.className + '#' + e.id); return out.join(' > ') }") for node in page.locator("[data-notification]").all() if node.is_visible()]
        assert not visible, visible
        context.close()
        browser.close()


# 0891: Airbnb month calendar: one scroll of month sections, rounded tiles, dark stay pills, sticky head, back-to-top.
SHOTS_0891 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0891"
ROWS_0891 = """() => [...document.querySelectorAll('.cal-month .cal-week.is-dots')].map(row => ({
    s: [...document.querySelectorAll('.cal-month')].indexOf(row.closest('.cal-month')),
    t: [...row.querySelectorAll('.cal-day[data-date]')].map(tile => { const r = tile.getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; })
})).filter(row => row.t.length)"""
PILLS_0891 = """() => [...document.querySelectorAll('.cal-pill')].map(pill => {
    const r = pill.getBoundingClientRect(), all = [...pill.closest('.cal-week').querySelectorAll('.cal-day[data-date]')];
    const nights = all.filter(t => t.dataset.date >= pill.dataset.calFrom && t.dataset.date < pill.dataset.calTo).map(t => t.getBoundingClientRect());
    const covered = all.filter(t => { const b = t.getBoundingClientRect(), mid = b.left + b.width / 2; return mid > r.left && mid < r.right; }).length;
    const want = Math.round((Date.parse(pill.dataset.calTo) - Date.parse(pill.dataset.calFrom)) / 86400000);
    return {want, nights: nights.length, covered, left: r.left - nights[0].left, right: nights[nights.length - 1].right - r.right,
            top: r.top - nights[0].top, bottom: nights[0].bottom - r.bottom, half: nights[0].height / 2,
            color: getComputedStyle(pill).backgroundColor, cut: pill.classList.contains('continues-start')};
})"""
FITS_0891 = "document.documentElement.scrollWidth <= innerWidth + 1"


def save_0891_shot(page, name):
    if os.environ.get("UBYHOST_TASK_SHOTS") != "1":
        return
    SHOTS_0891.mkdir(parents=True, exist_ok=True)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOTS_0891 / name), full_page=False)


def check_tiles_0891(rows, width, tile_height=None):
    gap = 12 if width >= 768 else 4
    assert rows, "no month tiles"
    for row in rows:
        for a, b in zip(row["t"], row["t"][1:]):
            assert abs(b[0] - a[1] - gap) <= 1, ("column gap", width, a, b)
        if tile_height:
            assert all(abs(t[3] - t[2] - tile_height) <= 1 for t in row["t"]), ("tile height", width, row)
    for upper, lower in zip(rows, rows[1:]):
        if upper["s"] == lower["s"]:
            assert abs(lower["t"][0][2] - upper["t"][0][3] - gap) <= 1, ("row gap", width, upper, lower)


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_0891_airbnb_month_tiles_and_pills(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, touch=width < 768)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-10-01")
        page.wait_for_selector(".cal-month")
        wait_loaded(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        sections = page.locator(".cal-month").evaluate_all("nodes => nodes.map(node => [node.dataset.calSection, node.getAttribute('aria-label')])")
        assert [s[0] for s in sections] == ["2026-10-01", "2026-11-01", "2026-12-01", "2027-01-01", "2027-02-01", "2027-03-01"], sections
        assert sections[0][1] == "October 2026", sections
        assert page.locator('.cal-day[data-date="2026-10-31"]').count() == 1
        assert page.locator('.cal-day[data-date="2026-11-01"]').count() == 1
        check_tiles_0891(page.evaluate(ROWS_0891), width, 94 if width >= 768 else None)
        pills = page.evaluate(PILLS_0891)
        assert pills, "no stay pills"
        inset = 8 if width >= 768 else 3
        for pill in pills:
            assert pill["want"] == pill["nights"] == pill["covered"], pill
            assert abs(pill["left"] - (0 if pill["cut"] else inset)) <= 1, pill
            assert abs(pill["right"]) <= 1, pill
            assert pill["top"] >= pill["half"] and pill["bottom"] >= 0, pill
            assert pill["color"] == "rgb(34, 34, 34)", pill
        assert page.locator(".cal-tile-chip:visible, .cal-dots:visible, .cal-week-events").count() == 0
        if width >= 768:
            assert page.locator('[data-cal-more="2026-10-14"]').is_visible()
            weekdays = page.locator("[data-cal-head] > .cal-weekdays span").all_inner_texts()
            assert len(weekdays) == 7 and weekdays[0] == "Mon", weekdays
        assert page.evaluate(FITS_0891)
        save_0891_shot(page, f"calendar-{width}.png")
        context.close()
        browser.close()


def test_0891_sticky_head_title_follows_scroll_and_back_to_top(calendar_workspace, calendar_origin):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=1280)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-10-01")
        page.wait_for_selector(".cal-month")
        wait_loaded(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        top = page.locator("[data-cal-top]")
        assert top.is_hidden()
        assert page.locator("[data-cal-period]").inner_text() == "October 2026"
        page.mouse.move(640, 700)
        page.mouse.wheel(0, 1800)
        page.wait_for_function("() => scrollY > 1000")
        page.wait_for_timeout(300)
        head = page.locator("[data-cal-head]").bounding_box()
        assert abs(head["y"]) <= 1, head
        assert page.locator("[data-cal-head] > .cal-weekdays").is_visible()
        title = page.locator("[data-cal-period]").inner_text()
        assert title in ("November 2026", "December 2026", "January 2027"), title
        assert top.is_visible()
        box = top.bounding_box()
        assert abs(box["width"] - 48) <= 1 and box["x"] + box["width"] <= 1280 - 23, box
        page.locator("[data-cal-next]").click()
        wait_loaded(page)
        expected = {"November 2026": "2026-12-01", "December 2026": "2027-01-01", "January 2027": "2027-02-01"}[title]
        assert page.locator(".cal-month").first.get_attribute("data-cal-section") == expected
        page.mouse.move(640, 700)
        page.mouse.wheel(0, 1800)
        page.wait_for_function("() => scrollY > 1000")
        page.wait_for_timeout(300)
        top.click()
        page.wait_for_function("() => scrollY === 0")
        assert page.locator("[data-cal-head]").bounding_box()["y"] >= 0
        context.close()
        browser.close()


@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1280, 1440])
def test_0891_calendar_no_horizontal_overflow(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, touch=width < 768)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-10-01")
        page.wait_for_selector(".cal-month")
        wait_loaded(page)
        assert page.evaluate(FITS_0891), (width, "top")
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        page.wait_for_timeout(300)
        assert page.evaluate(FITS_0891), (width, "bottom")
        context.close()
        browser.close()
