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
        assert not page.locator(".cal-view-segment").is_visible()
        assert page.locator(".cal-gantt-row").count() == 0
        page.locator("[data-cal-property]").select_option("")
        page.wait_for_function("() => document.querySelectorAll('.cal-gantt-row').length === 3")
        assert page.locator(".cal-view-segment").is_visible()
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
                            # the bound includes the +N overflow lane added by 0967 (C03)
                            assert max(heights) <= 226, heights  # 0905: 94 px tile + two more stacked stay lanes
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
                page.locator('[data-cal-day="2026-10-15"]').click(position={"x": 12, "y": 10})  # 0905: stacked pills cover the tile centre
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
        cleaning_tag_day.locator(".cal-day-number").click(position={"x": 12, "y": 10})  # 0956: stay bars sit under the day number
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
            f'[data-dashboard-refresh="stats"] .card[data-needs-you-stay="{created_stay["id"]}"]'
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
                rows: [...document.querySelectorAll('[data-dashboard-refresh="stats"] .card[data-needs-you="stay"]')].map(row => ({
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
                rows: [...doc.querySelectorAll('[data-dashboard-refresh="stats"] .card[data-needs-you="stay"]')].map(row => ({
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
                rows: [...document.querySelectorAll('[data-dashboard-refresh="stats"] .card[data-needs-you="stay"]')].map(row => ({
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
        # 0956: Auto is offered only while no property is picked, so clear the property first.
        page.locator("[data-cal-property]").select_option("")
        wait_loaded(page)
        page.locator("[data-cal-settings]").click()
        page.locator("[data-cal-auto]").check()
        wait_loaded(page)
        page.locator("[data-cal-settings-dialog] [data-cal-close]").click()
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
    const covered = all.filter(t => { const b = t.getBoundingClientRect(), over = Math.min(b.right, r.right) - Math.max(b.left, r.left); return t.dataset.date >= pill.dataset.calFrom && t.dataset.date < pill.dataset.calTo && over >= b.width / 4; }).length;
    const dep = all.find(t => t.dataset.date === pill.dataset.calTo && pill.dataset.calTo.slice(0, 7) === pill.closest('.cal-month').dataset.calSection.slice(0, 7));
    const want = Math.round((Date.parse(pill.dataset.calTo) - Date.parse(pill.dataset.calFrom)) / 86400000);
    return {want, nights: nights.length, covered, left: r.left - nights[0].left, right: nights[nights.length - 1].right - r.right,
            top: r.top - nights[0].top, bottom: nights[0].bottom - r.bottom, half: nights[0].height / 2,
            color: getComputedStyle(pill).backgroundColor, cut: pill.classList.contains('continues-start'),
            gap: parseFloat(getComputedStyle(pill.parentElement).columnGap) || 0, width: nights[0].width,
            halfEnd: !!dep, depMid: dep ? dep.getBoundingClientRect().left + dep.getBoundingClientRect().width / 2 : null, rightAbs: r.right};
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
            # 0905: each extra stacked stay lane adds 44 px (0967: the +N lane is the fourth); every tile of a row has the same height.
            heights = {round(t[3] - t[2]) for t in row["t"]}
            assert len(heights) == 1 and any(abs(heights.copy().pop() - (tile_height + k * 44)) <= 1 for k in range(4)), ("tile height", width, row)
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
        for pill in pills:
            # 0908: a bar starts halfway into its arrival day and ends halfway into its departure day; 2 px right margin
            assert pill["want"] == pill["nights"] == pill["covered"], pill
            # the grid line sits after the first half-track, so it is (cell + gap) / 2 from the cell edge
            expected_left = 0 if pill["cut"] else (pill["width"] + pill["gap"]) / 2
            if not pill["cut"] and not pill["halfEnd"] and abs(pill["right"]) <= 1 and pill["nights"] == 1 and pill["gap"] >= 12:  # gap 12 = the 768 px and up layout
                # 0908 4d: a Sunday arrival is only half a cell wide, so the bar grows to its 48 px min-width (.cal-pill) inside the row; a stay another test left in the shared workspace can put one here
                expected_left = min(expected_left, pill["width"] - 48)
            assert abs(pill["left"] - expected_left) <= 1, pill
            if pill["halfEnd"]:  # ends halfway into the departure day: cell middle minus g/2
                assert abs(pill["rightAbs"] - (pill["depMid"] - pill["gap"] / 2)) <= 1, pill
            else:  # runs into the next week: Sunday edge, 2 px margin
                assert abs(pill["right"]) <= 1, pill
            assert pill["top"] >= 36 and pill["bottom"] >= 0, pill  # below the day number (0905: stacked lanes)
            assert pill["color"], pill  # 0956: colour is per property, see test_0956_each_property_has_one_colour_everywhere
        assert page.locator(".cal-tile-chip:visible, .cal-dots:visible, .cal-week-events").count() == 0
        if width >= 768:
            assert page.locator('[data-cal-more="2026-10-14"]').is_visible()
            weekdays = page.locator("[data-cal-head] > .cal-weekdays span").all_inner_texts()
            assert len(weekdays) == 7 and weekdays[0] == "Mon", weekdays
        assert page.evaluate(FITS_0891)
        save_0891_shot(page, f"calendar-{width}.png")
        context.close()
        browser.close()


SHOTS_0908 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0908"
GEOM_0908 = """() => {
    const cell = date => { const b = document.querySelector(`.cal-day[data-date="${date}"]`).getBoundingClientRect(); return {l: b.left, r: b.right, w: b.width}; };
    const pills = [...document.querySelectorAll('.cal-pill')].map(p => { const b = p.getBoundingClientRect(); return {from: p.dataset.calFrom, to: p.dataset.calTo, l: b.left, r: b.right, t: b.top}; });
    const dates = ['2026-12-05', '2026-12-06', '2026-12-07', '2026-12-08', '2026-12-11'];
    return {gap: parseFloat(getComputedStyle(document.querySelector('.cal-pills')).columnGap) || 0, cells: Object.fromEntries(dates.map(d => [d, cell(d)])), pills};
}"""


@pytest.mark.parametrize("width", [390, 1280])
def test_0908_stay_bars_start_and_end_halfway_through_their_days(calendar_workspace, calendar_origin, width):
    property_id = calendar_workspace["properties"][0]
    make_stay(property_id, "2026-12-05", "2026-12-08", summary="0908 stay A", expected_guests_override=2)
    make_stay(property_id, "2026-12-08", "2026-12-11", summary="0908 stay B", expected_guests_override=2)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, touch=width < 768)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-12-01")
        page.wait_for_selector(".cal-month")
        wait_loaded(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        geo = page.evaluate(GEOM_0908)
        SHOTS_0908.mkdir(parents=True, exist_ok=True)
        page.locator(".cal-week", has=page.locator('.cal-pill[data-cal-from="2026-12-07"]')).first.screenshot(path=str(SHOTS_0908 / f"week-{width}.png"))
        context.close()
        browser.close()
    g, c = geo["gap"], geo["cells"]
    def mid(day):  # middle of a day cell
        return c[day]["l"] + c[day]["w"] / 2
    pills = {(x["from"], x["to"]): x for x in geo["pills"]}
    a1, a2, b = pills[("2026-12-05", "2026-12-07")], pills[("2026-12-07", "2026-12-08")], pills[("2026-12-08", "2026-12-11")]
    assert abs(a1["l"] - (mid("2026-12-05") + g / 2)) <= 1, a1  # starts halfway through the 5th: cell middle + g/2
    assert abs(a1["r"] - c["2026-12-06"]["r"]) <= 1, a1  # runs into the next week: Sunday edge
    assert abs(a2["l"] - c["2026-12-07"]["l"]) <= 1, a2  # continues from the previous week: Monday edge
    assert abs(a2["r"] - (mid("2026-12-08") - g / 2)) <= 1, a2  # ends halfway through the 8th: cell middle - g/2
    assert abs(b["l"] - (mid("2026-12-08") + g / 2)) <= 1, b  # back-to-back stay starts halfway through the same 8th
    assert abs(b["r"] - (mid("2026-12-11") - g / 2)) <= 1, b
    assert abs((b["l"] - a2["r"]) - g) <= 1 and abs(a2["t"] - b["t"]) <= 1, (a2, b)  # touching stays: gap g, same lane


def test_0908_sunday_arrival_bar_is_a_full_tap_target_at_768(calendar_workspace, calendar_origin):
    # 4d: a Sunday arrival is half a cell wide; the bar must still be a 44 px tap target inside its week row
    property_id = calendar_workspace["properties"][0]
    make_stay(property_id, "2026-12-06", "2026-12-09", summary="0908 sunday stay", expected_guests_override=2)
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=768, touch=False)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-12-01")
        page.wait_for_selector(".cal-month")
        wait_loaded(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        pill = page.locator('.cal-pill[data-cal-from="2026-12-06"]').first.bounding_box()
        row = page.locator(".cal-week", has=page.locator('.cal-pill[data-cal-from="2026-12-06"]')).first.bounding_box()
        context.close()
        browser.close()
    assert pill["width"] >= 44 - 0.5, (pill, row)
    assert pill["x"] + pill["width"] <= row["x"] + row["width"] + 1, (pill, row)


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


GEOMETRY_0893 = """() => {
  const root = document.querySelector('#calendar');
  const out = {small: [], edge: [], touching: []};
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode; if (!node.textContent.trim()) continue;
    const el = node.parentElement; if (!visible(el) || el.scrollWidth > el.clientWidth + 1) continue;
    const size = parseFloat(getComputedStyle(el).fontSize);
    if (size < 12) out.small.push([el.className, node.textContent.trim().slice(0, 20), size]);
    const range = document.createRange(); range.selectNodeContents(node);
    const box = range.getBoundingClientRect();
    if (box.width && (box.left < 8 || box.right > innerWidth - 8)) out.edge.push([el.className, node.textContent.trim().slice(0, 20), Math.round(box.left), Math.round(box.right)]);
  }
  const controls = [...root.querySelectorAll('[data-cal-head] button, [data-cal-head] select, [data-cal-head] a')].filter(visible)
    .map(el => [el, el.getBoundingClientRect()]);
  const title = root.querySelector('[data-cal-period]');
  if (title && visible(title)) controls.push([title, title.getBoundingClientRect()]);
  for (let i = 0; i < controls.length; i++) for (let j = i + 1; j < controls.length; j++) {
    const [a, p] = controls[i], [b, q] = controls[j];
    if (a.contains(b) || b.contains(a)) continue;
    const group = a.closest('.cal-segment');
    if (group && group === b.closest('.cal-segment')) continue;
    const dx = Math.max(q.left - p.right, p.left - q.right), dy = Math.max(q.top - p.bottom, p.top - q.bottom);
    if (Math.max(dx, dy) < 12) out.touching.push([a.className || a.tagName, b.className || b.tagName, Math.round(dx), Math.round(dy)]);
  }
  return out;
}"""


@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1280, 1440])
def test_0893_calendar_text_size_edges_and_header_spacing(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, touch=width < 768)
        page.goto(f"{calendar_origin}/?lang=en&cal_view=calendar&cal_date=2026-10-01")
        page.wait_for_selector(".cal-month")
        wait_loaded(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        found = page.evaluate(GEOMETRY_0893)
        assert not found["small"], (width, found["small"][:8])
        assert not found["edge"], (width, found["edge"][:8])
        assert not found["touching"], (width, found["touching"][:8])
        context.close()
        browser.close()


@pytest.mark.parametrize("width", [390, 768, 1280])
@pytest.mark.parametrize("locale", ["en", "cs"])
@pytest.mark.parametrize("entry", ["dashboard", "cleaning"])
def test_0978_record_type_selection_is_visually_unambiguous(
    calendar_workspace, calendar_origin, width, locale, entry
):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(
            browser, calendar_workspace, calendar_origin, width=width,
            locale=locale, touch=width < 768,
        )
        try:
            path = "/cleaning" if entry == "cleaning" else "/"
            page.goto(f"{calendar_origin}{path}?lang={locale}&cal_date=2026-10-01&cal_view=calendar")
            page.wait_for_selector(".cal-week")
            wait_loaded(page)
            page.locator('[data-cal-day="2026-10-10"]').click(position={"x": 8, "y": 8})
            if page.locator("[data-cal-day-add]").is_visible():
                page.locator("[data-cal-day-add]").click()
            dialog = page.locator("[data-cal-create]")
            dialog.wait_for(state="visible")
            for kind in ("stay", "cleaning", "stay"):
                choice = dialog.locator(f'[data-cal-type-choice="{kind}"]')
                choice.focus()
                choice.press("Space")
                other = "cleaning" if kind == "stay" else "stay"
                assert choice.get_attribute("aria-pressed") == "true"
                assert dialog.locator(f'[data-cal-type-choice="{other}"]').get_attribute("aria-pressed") == "false"
                assert dialog.locator("[data-cal-stay-fields]").is_visible() == (kind == "stay")
                assert dialog.locator("[data-cal-cleaning-fields]").is_visible() == (kind == "cleaning")
                page.wait_for_function("""() => {
                    const dialog = document.querySelector('[data-cal-create]');
                    const color = selector => getComputedStyle(dialog.querySelector(selector)).backgroundColor;
                    return color('[data-cal-type-choice][aria-pressed="true"]') !==
                        color('[data-cal-type-choice][aria-pressed="false"]') &&
                        color('[data-cal-type-choice][aria-pressed="false"]') !== color('[data-cal-save]');
                }""")
                for state in ("true", "false"):
                    label = dialog.locator(f'[data-cal-type-choice][aria-pressed="{state}"]')
                    ratio = label.evaluate(r"""e => {
                        const lum = c => { const v = c.match(/[\d.]+/g).slice(0, 3).map(n => { n /= 255; return n <= 0.03928 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4; }); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
                        const opaque = node => { for (let n = node; n; n = n.parentElement) { const c = getComputedStyle(n).backgroundColor; if (c !== "rgba(0, 0, 0, 0)") return c; } return "rgb(255, 255, 255)"; };
                        const fg = lum(getComputedStyle(e).color), bg = lum(opaque(e));
                        return (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
                    }""")
                    assert ratio >= 4.5, (width, locale, entry, kind, state, ratio)
                if kind == "cleaning" and locale == "en" and width == 390:
                    shot(page, f"0978-{entry}-cleaning-{locale}-{width}")
            if locale == "en" or width == 390:
                shot(page, f"0978-{entry}-stay-{locale}-{width}")
            page.keyboard.press("Escape")
            dialog.wait_for(state="hidden")
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("width", [390, 768, 1280])
@pytest.mark.parametrize("locale", ["en", "cs"])
@pytest.mark.parametrize("entry", ["dashboard", "cleaning"])
def test_0980_create_actions_label_input_and_cleaning_day_name(
    calendar_workspace, calendar_origin, width, locale, entry
):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(
            browser, calendar_workspace, calendar_origin, width=width,
            locale=locale, touch=width < 768,
        )
        try:
            path = "/cleaning" if entry == "cleaning" else "/"
            page.goto(f"{calendar_origin}{path}?lang={locale}&cal_date=2026-10-01&cal_view=calendar")
            page.wait_for_selector(".cal-week")
            wait_loaded(page)
            day = page.locator('[data-cal-day="2026-10-10"]')
            name = day.get_attribute("aria-label")
            if entry == "cleaning":
                assert name.startswith("Add cleaning" if locale == "en" else "Přidat úklid"), name
                assert "stay" not in name.lower() and "pobyt" not in name.lower(), name
            else:
                assert name.startswith("Add a stay" if locale == "en" else "Přidat pobyt"), name
            day.click(position={"x": 8, "y": 8})
            if page.locator("[data-cal-day-add]").is_visible():
                page.locator("[data-cal-day-add]").click()
            dialog = page.locator("[data-cal-create]")
            dialog.wait_for(state="visible")
            boxes = {}
            for kind in ("stay", "cleaning"):
                dialog.locator(f'[data-cal-type-choice="{kind}"]').click()
                data = page.evaluate("""() => {
                    const dialog = document.querySelector('[data-cal-create]');
                    const read = node => {
                        const box = node.getBoundingClientRect(), css = getComputedStyle(node);
                        return {x: Math.round(box.x - dialog.getBoundingClientRect().x), w: Math.round(box.width), h: Math.round(box.height),
                            bg: css.backgroundColor, border: css.borderTopWidth + css.borderTopStyle, radius: css.borderTopLeftRadius};
                    };
                    const buttons = [...dialog.querySelectorAll('.cal-dialog-actions .btn')].filter(b => b.offsetParent);
                    const filled = [...dialog.querySelectorAll('button.btn')].filter(b => b.offsetParent &&
                        getComputedStyle(b).backgroundColor === getComputedStyle(dialog.querySelector('[data-cal-save]')).backgroundColor);
                    return {cancel: read(dialog.querySelector('.cal-dialog-actions .btn.soft')), save: read(dialog.querySelector('[data-cal-save]')),
                        filled: filled.map(b => b.hasAttribute('data-cal-save')), count: buttons.length,
                        overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
                        dialogOverflow: dialog.scrollWidth > dialog.clientWidth,
                        label: dialog.querySelector('#cal-label') && dialog.querySelector('#cal-label').offsetParent ? read(dialog.querySelector('#cal-label')) : null,
                        guests: dialog.querySelector('#cal-guests').offsetParent ? read(dialog.querySelector('#cal-guests')) : null};
                }""")
                boxes[kind] = data
                assert data["count"] == 2 and data["filled"] == [True], (kind, data)
                assert data["cancel"]["bg"] != data["save"]["bg"], (kind, data)
                assert data["cancel"]["h"] == data["save"]["h"], (kind, data)
                assert data["cancel"]["x"] < data["save"]["x"], (kind, data)
                assert not data["overflow"] and not data["dialogOverflow"], (kind, data)
                if kind == "stay":
                    assert data["label"]["h"] == data["guests"]["h"], data
                    assert data["label"]["border"] == data["guests"]["border"] == "1pxsolid", data
                    assert data["label"]["radius"] == data["guests"]["radius"] != "0px", data
                    page.locator("#cal-label").focus()
                    label_ring = page.evaluate("() => { const c = getComputedStyle(document.querySelector('#cal-label')); return c.outlineColor + c.outlineWidth + c.outlineStyle; }")
                    page.locator("#cal-guests").focus()
                    guests_ring = page.evaluate("() => { const c = getComputedStyle(document.querySelector('#cal-guests')); return c.outlineColor + c.outlineWidth + c.outlineStyle; }")
                    assert label_ring == guests_ring, (label_ring, guests_ring)
                shot(page, f"0980-{entry}-{kind}-{locale}-{width}")
            assert boxes["stay"]["cancel"]["x"] == boxes["cleaning"]["cancel"]["x"]
            assert boxes["stay"]["cancel"]["w"] == boxes["cleaning"]["cancel"]["w"]
            assert boxes["stay"]["save"]["x"] == boxes["cleaning"]["save"]["x"]
            assert boxes["stay"]["save"]["w"] == boxes["cleaning"]["save"]["w"]
            page.keyboard.press("Escape")
            dialog.wait_for(state="hidden")
        finally:
            context.close()
            browser.close()
# 0967: calendar orientation (one named H1, no repeated month caption) and a +N lane that never covers a bar.
NAV_NAME_0967 = {"en": "Calendar", "cs": "Kalendář"}
DENSE_DAYS_0967 = ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"]
PANEL_OPEN_0967 = "() => [...document.querySelectorAll('[data-cal-day-dialog][open]')].every(d => getComputedStyle(d).opacity === '1')"
OVERFLOW_0967 = r"""(day) => {
    const badge = document.querySelector(`.cal-pill-more[data-cal-more="${day}"]`);
    if (!badge) return null;
    const week = badge.closest('.cal-week'), tile = week.querySelector(`.cal-day[data-date="${day}"]`);
    const b = badge.getBoundingClientRect(), t = tile.getBoundingClientRect();
    const pills = [...week.querySelectorAll('.cal-pill')];
    return {
        count: parseInt(badge.textContent.replace(/\D/g, ''), 10),
        covering: pills.filter(p => p.dataset.calFrom <= day && day < p.dataset.calTo).length,
        badgeTop: b.top, lowestBar: Math.max(...pills.map(p => p.getBoundingClientRect().bottom)),
        inside: b.left >= t.left - 1 && b.right <= t.right + 1 && b.top >= t.top - 1 && b.bottom <= t.bottom + 1,
    };
}"""
NAMES_0967 = """() => [...document.querySelectorAll('.cal-pill-name')]
    .filter(node => getComputedStyle(node).display !== 'none').map(node => Math.round(node.getBoundingClientRect().width))"""


def overlaps_0967(page, first, second):
    """Pairs of visible boxes (first vs second) that share more than half a pixel in both directions, per week row."""
    return page.evaluate("""([first, second]) => {
        const hit = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0.5 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0.5;
        const visible = node => node.offsetParent !== null && getComputedStyle(node).visibility !== 'hidden';
        const found = [];
        document.querySelectorAll('.cal-week').forEach(week => {
            const a = [...week.querySelectorAll(first)].filter(visible), b = [...week.querySelectorAll(second)].filter(visible);
            a.forEach(x => b.forEach(y => { if (x !== y && hit(x.getBoundingClientRect(), y.getBoundingClientRect())) found.push([x.textContent, y.textContent]); }));
        });
        return found;
    }""", [first, second])


def open_month_0967(page, origin, locale="en", date="2026-10-01"):
    page.goto(f"{origin}/?lang={locale}&cal_view=calendar&cal_date={date}")
    page.wait_for_selector(".cal-month")
    wait_loaded(page)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)


@pytest.mark.parametrize("locale", ["en", "cs"])
@pytest.mark.parametrize("width", [390, 768, 1280])
def test_0967_calendar_page_has_one_named_heading_and_no_repeated_month(calendar_workspace, calendar_origin, width, locale):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, locale=locale, touch=width < 768)
        try:
            open_month_0967(page, calendar_origin, locale)
            headings = page.locator("h1:visible")
            assert headings.count() == 1, headings.all_inner_texts()
            assert headings.first.inner_text().strip() == NAV_NAME_0967[locale]
            h1, head = headings.first.bounding_box(), page.locator("[data-cal-head]").bounding_box()
            assert h1["width"] > 40 and h1["height"] > 16 and h1["y"] + h1["height"] <= head["y"] + 1, (h1, head)
            assert headings.first.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
            assert page.locator("[data-cal-period]").inner_text().strip()
            if width >= 768:
                titles = page.locator(".cal-month-title")
                assert titles.first.is_hidden() and titles.nth(1).is_visible()  # the first caption repeats the period title
            assert page.evaluate(FITS_0891)
            shot(page, f"0967-heading-{locale}-{width}")
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_0967_overflow_badge_has_its_own_lane_and_counts_match_the_day_list(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width, touch=width < 768)
        try:
            open_month_0967(page, calendar_origin)
            if width < 768:  # the phone keeps its dot tiles and the day sheet; no badge is drawn
                assert page.locator(".cal-pill-more:visible").count() == 0
                return
            assert overlaps_0967(page, ".cal-pill-more", ".cal-pill") == []
            measured = {}
            for day in DENSE_DAYS_0967:
                info = page.evaluate(OVERFLOW_0967, day)
                assert info and info["count"] >= 1 and info["covering"] <= 3, (day, info)
                assert info["inside"], (day, info)
                assert info["badgeTop"] >= info["lowestBar"] - 0.5, (day, info)  # the badge lane is under every bar of the week
                measured[day] = info
            shot(page, f"0967-overflow-{width}")
            for day, info in measured.items():
                page.locator(f'.cal-pill-more[data-cal-more="{day}"]').click()
                page.wait_for_selector("[data-cal-day-dialog]", state="visible")
                page.wait_for_function(PANEL_OPEN_0967)
                items = page.locator('[data-cal-day-list] .cal-event:not([data-event-kind="cleaning"])').count()
                assert items == info["covering"] + info["count"], (day, items, info)  # hidden count + drawn bars = the day list
                page.locator("[data-cal-day-dialog] [data-cal-close]").click()
                page.locator("[data-cal-day-dialog]").wait_for(state="hidden")
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("width", [768, 1024, 1280])
def test_0967_open_day_panel_never_crushes_booking_text(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width)
        try:
            open_month_0967(page, calendar_origin)
            for state in ("closed", "open"):
                if state == "open":
                    page.locator('.cal-pill-more[data-cal-more="2026-10-16"]').click()
                    page.wait_for_selector("[data-cal-day-dialog]", state="visible")
                    page.wait_for_function(PANEL_OPEN_0967)
                    for item in page.locator("[data-cal-day-list] .cal-event").all():
                        assert item.bounding_box()["width"] >= 200  # the panel list keeps full, wrapped names
                    assert page.locator('.cal-pill-more[data-cal-more="2026-10-16"]').is_visible()
                assert page.locator(".cal-pill").count() >= 3
                names = page.evaluate(NAMES_0967)
                assert all(width_ >= 36 for width_ in names), (state, names)  # a name is readable or not drawn; never a fragment
                assert overlaps_0967(page, ".cal-pill-more", ".cal-pill") == []
                assert page.evaluate(FITS_0891)
                shot(page, f"0967-panel-{state}-{width}")
            page.locator("[data-cal-day-dialog] [data-cal-close]").click()
            page.locator("[data-cal-day-dialog]").wait_for(state="hidden")
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("width", [768, 1280])
def test_0967_scales_navigation_and_keyboard_focus(calendar_workspace, calendar_origin, width):
    with sync_api.sync_playwright() as playwright:
        browser = launch(playwright)
        context, page = open_page(browser, calendar_workspace, calendar_origin, width=width)
        try:
            open_month_0967(page, calendar_origin, date="2026-10-14")
            for scale in ("week", "year", "month"):
                page.locator(f'[data-cal-scale="{scale}"]').click()
                wait_loaded(page)
                assert page.locator("h1:visible").count() == 1
                assert page.locator("[data-cal-period]").inner_text().strip()
                assert overlaps_0967(page, ".cal-more", ".cal-event") == []
                if scale == "week":
                    assert page.locator(".cal-more:visible").count() >= 1
                    shot(page, f"0967-week-{width}")
                if scale == "year":
                    assert page.locator(".cal-mini-title").count() == 12
                    assert page.locator("[data-cal-period]").inner_text().strip() == "2026"
                    shot(page, f"0967-year-{width}")
            page.evaluate("window.scrollTo(0, 0)")
            page.locator("[data-cal-next]").click()
            wait_loaded(page)
            assert page.locator("[data-cal-period]").inner_text() == "November 2026"
            page.locator("[data-cal-prev]").click()
            wait_loaded(page)
            assert page.locator("[data-cal-period]").inner_text() == "October 2026"
            page.locator("[data-cal-today]").click()
            wait_loaded(page)
            page.evaluate("window.scrollTo(0, 0)")
            assert page.locator("[data-cal-period]").inner_text() == page.locator(".cal-month").first.get_attribute("aria-label")
            open_month_0967(page, calendar_origin)
            badge = page.locator('.cal-pill-more[data-cal-more="2026-10-16"]')
            badge.focus()
            page.keyboard.press("Shift+Tab")
            page.keyboard.press("Tab")  # a key press, so :focus-visible applies
            assert badge.evaluate("node => node === document.activeElement")
            ring = badge.evaluate("node => { const s = getComputedStyle(node); return [s.outlineStyle, parseFloat(s.outlineWidth), s.boxShadow]; }")
            assert (ring[0] != "none" and ring[1] >= 2) or ring[2] != "none", ring
            shot(page, f"0967-focus-{width}")
        finally:
            context.close()
            browser.close()
