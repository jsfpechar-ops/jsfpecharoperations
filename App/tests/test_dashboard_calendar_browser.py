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
    for index in range(4):
        make_stay(calendar_workspace["properties"][index % 3], "2026-10-14", "2026-10-19",
                  summary="Reserved" if index % 2 == 0 else "! Reserved")
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
        assert page.locator(".cal-week-events").get_by_text("Reserved", exact=False).count() == 0
        assert page.locator(".cal-event-mark").count() == 0
        assert len(set(page.locator(".cal-week-events .cal-event").evaluate_all(
            "nodes => nodes.map(node => getComputedStyle(node).backgroundColor)"
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
        page.locator("[data-cal-year]").select_option("2028")
        page.wait_for_selector('[data-cal-day="2028-10-01"]')
        page.locator("[data-cal-month]").select_option("02")
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
        live_booking = page.locator(f'.cal-week-events .cal-event[data-cal-event="{row_id}"]')
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
        live_booking = page.locator(f'.cal-week-events .cal-event[data-cal-event="{row_id}"]')
        live_booking.click()
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
                for mode in ("gantt", "calendar"):
                    page.locator(f'[data-cal-view="{mode}"]').click()
                    page.wait_for_selector(".cal-gantt-row" if mode == "gantt" else ".cal-week")
                    wait_loaded(page)
                    # Summary -> calendar -> detailed action queue, in the same lane.
                    boxes = page.evaluate("""() => ['.dashboard-stats', '#calendar', '#needs-action'].map(selector => {
                        const r = document.querySelector(selector).getBoundingClientRect();
                        return {top:r.top, bottom:r.bottom, left:r.left, right:r.right, height:r.height};
                    })""")
                    assert 0 <= boxes[1]["top"] - boxes[0]["bottom"] <= 16, boxes
                    assert boxes[2]["top"] >= boxes[1]["bottom"], boxes
                    for box in boxes[1:]:
                        assert abs(box["left"] - boxes[0]["left"]) <= 2, boxes
                        assert abs(box["right"] - boxes[0]["right"]) <= 2, boxes
                    icon = page.locator("[data-cal-settings] svg").bounding_box()
                    assert icon["width"] >= 18 and icon["height"] >= 18, icon
                    if width >= 1024:
                        pill_heights = page.locator(".dashboard-stat").evaluate_all(
                            "nodes => nodes.map(node => node.getBoundingClientRect().height)"
                        )
                        assert max(pill_heights) <= 40, pill_heights
                        if mode == "calendar":
                            heights = page.locator(".cal-week").evaluate_all(
                                "nodes => nodes.map(node => node.getBoundingClientRect().height)"
                            )
                            assert max(heights) <= 102, heights
                            assert boxes[1]["height"] <= 725, boxes
                    control_heights = page.locator(
                        ".cal-view-segment, .cal-scale-segment, [data-cal-property], [data-cal-month], "
                        "[data-cal-year], [data-cal-settings], [data-cal-today], [data-cal-prev], [data-cal-next]"
                    ).evaluate_all(
                        "nodes => nodes.filter(node => node.offsetParent).map(node => node.getBoundingClientRect().height)"
                    )
                    assert control_heights and max(control_heights) - min(control_heights) <= 1, control_heights
                    if width <= 390:
                        buttons = page.locator(".cal-view-segment button, .cal-scale-segment button").evaluate_all(
                            "nodes => nodes.filter(node => node.offsetParent).map(node => node.getBoundingClientRect().height)"
                        )
                        groups = page.locator(".cal-view-segment, .cal-scale-segment, [data-cal-month], [data-cal-year]").evaluate_all(
                            "nodes => nodes.filter(node => node.offsetParent).map(node => node.getBoundingClientRect().height)"
                        )
                        assert min(buttons) >= 44, buttons
                        assert max(groups) - min(groups) <= 2, groups
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
        page.locator("[data-cal-property]").select_option(str(apartment_id))
        page.wait_for_selector(".cal-week")
        segments = page.locator(f'.cal-event[data-cal-event="{stay_id}"]')
        assert segments.count() == 2
        first, second = segments.nth(0), segments.nth(1)
        assert first.get_attribute("class").find("continues-end") >= 0
        assert second.get_attribute("class").find("continues-start") >= 0
        first_box, second_box = first.bounding_box(), second.bounding_box()
        sun = page.locator('.cal-day[data-date="2026-10-18"]').bounding_box()
        mon = page.locator('.cal-day[data-date="2026-10-19"]').last.bounding_box()
        tue = page.locator('.cal-day[data-date="2026-10-20"]').last.bounding_box()
        expected_start = sun["x"] + sun["width"] * 15 / 24
        expected_first_right = sun["x"] + sun["width"]
        expected_monday = mon["x"]
        expected_checkout = tue["x"] + tue["width"] * 11 / 24
        assert abs(first_box["x"] - expected_start) <= 4, (first_box, expected_start)
        assert abs(first_box["x"] + first_box["width"] - expected_first_right) <= 4, (first_box, expected_first_right)
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

        page.locator('[data-calendar-add][data-cal-create-type="cleaning"]').click()
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
        cleaning_page.goto(f"{calendar_origin}/cleaning?lang=en&cal_date=2026-10-27")
        cleaning_page.wait_for_selector("[data-calendar]")
        wait_loaded(cleaning_page)
        cleaning_page.locator('[data-cal-view="calendar"]').click()
        cleaning_page.wait_for_selector(".cal-week")
        wait_loaded(cleaning_page)
        cleaning_marker = cleaning_page.locator(
            f'.cal-week-events .cal-event[data-cal-event="{cleaning_event_id}"]'
        )
        cleaning_marker.wait_for(state="visible")
        assert "Calendar popup" in cleaning_page.locator(f'#cleaning-{created_cleaning["id"]}').inner_text()
        shot(cleaning_page, "cleaning-calendar-created-marker-en")
        cleaning_page.close()

        booking = page.locator(f'.cal-event[data-cal-event="{existing_stay}"]:visible')
        assert booking.count() == 1
        booking.click()
        action = page.locator("[data-cal-details] [data-cal-open]")
        assert action.is_visible() and action.inner_text().strip() == "Open stay"
        page.locator("[data-cal-details] [data-cal-close]").click()

        page.locator('[data-calendar-add][data-cal-create-type="stay"]').click()
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
        attention_before = int(page.locator('[data-dashboard-refresh="stats"] .dashboard-stat.action strong').inner_text())
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  response.url.split("?")[0].endswith("/reservations")) as stay_result:
            page.locator("[data-cal-save]").click()
        created_stay = stay_result.value.json()
        assert stay_result.value.status == 201
        assert page.evaluate("location.pathname") == pathname
        page.wait_for_function("""before => {
            const strong = document.querySelector('[data-dashboard-refresh="stats"] .dashboard-stat.action strong');
            return !!strong && Number(strong.textContent.trim()) === before + 1;
        }""", arg=attention_before)
        row = page.locator(f'[data-dashboard-refresh="work"] .dashboard-row[data-stay-id="{created_stay["id"]}"]')
        # The work list shows at most five rows (reporting.py limit), so the new stay is
        # counted above but only rendered when it ranks in the top five. Row checks run then.
        row_rendered = row.count() > 0
        if row_rendered:
            row.wait_for(state="visible")
            assert "Popup row refresh" in row.inner_text()

            # Re-delivering the scoped update must not double-bind imported controls.
            page.evaluate("""() => {
                const root = document.querySelector('[data-dashboard-refresh="work"]');
                document.dispatchEvent(new CustomEvent("ubyhost:content-updated", {detail: {root}}));
                document.dispatchEvent(new CustomEvent("ubyhost:content-updated", {detail: {root}}));
            }""")
            row.locator(".row-menu-trigger").click()
            menu = page.locator(".row-menu-panel:visible").last
            menu.wait_for(state="visible")
            assert menu.locator(".row-menu-item").count() >= 1
            copy_button = menu.locator("button[data-copy]")
            assert copy_button.count() == 1
            copy_button_id = "refresh-copy-action"
            copy_button.evaluate("(button, id) => { button.id = id; }", copy_button_id)
            copy_button.click()
            page.wait_for_function("""id => {
                const button = document.getElementById(id);
                return !!button && (button.classList.contains("is-copy-confirmed") ||
                    !!document.querySelector("[data-copy-manual-visible]"));
            }""", arg=copy_button_id)

            if not menu.is_visible():
                row.locator(".row-menu-trigger").click()
                menu = page.locator(".row-menu-panel:visible").last
                menu.wait_for(state="visible")
            archive_posts = []
            page.on("request", lambda request: archive_posts.append(request.url)
                   if request.method == "POST" and request.url.split("?")[0].endswith("/archive") else None)
            archive_form = menu.locator('form[data-confirm][action$="/archive"]')
            assert archive_form.count() == 1
            archive_form.locator('button[type="submit"]').click()
            confirmation = page.locator("#confirm-dialog")
            confirmation.wait_for(state="visible")
            confirmation.locator("[data-confirm-cancel]").click()
            assert not confirmation.is_visible()
            assert archive_posts == []
            assert row.is_visible()

        # Dashboard has no dismissible banner in every fixture; exercise the same
        # scoped binder with a transient banner under the refreshed work region.
        banner_id = page.evaluate("""() => {
            const root = document.querySelector('[data-dashboard-refresh="work"]');
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
        if row_rendered:
            with page.expect_navigation():
                row.focus()
                row.press("Enter")
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
                rows: [...document.querySelectorAll('[data-dashboard-refresh="work"] .dashboard-row')].filter(row => !row.closest("noscript")).map(row => ({
                    id: row.getAttribute("data-stay-id"),
                    text: normalize(row.querySelector(".dashboard-row-copy")?.textContent)
                }))
            };
        }""")
        assert before["rows"], "fixture should render work rows before the committed save"
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
        page.locator('[data-calendar-add][data-cal-create-type="stay"]').click()
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
        overlap = form.locator('input[name="allow_overlap"]')
        if overlap.count() and overlap.is_visible():
            overlap.check()
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

        # The work list is intentionally capped at five rows. Change an existing visible
        # synthetic manual label so the successful retry proves it replaced stale HTML.
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
            const normalize = value => (value || "").replace(/\\s+/g, " ").trim();
            return {
                stats: normalize(doc.querySelector('[data-dashboard-refresh="stats"]')?.textContent),
                rows: [...doc.querySelectorAll('[data-dashboard-refresh="work"] .dashboard-row')].filter(row => !row.closest("noscript")).map(row => ({
                    id: row.getAttribute("data-stay-id"),
                    text: normalize(row.textContent)
                }))
            };
        }""", fresh_html)
        assert any(row["id"] == target_id and sentinel in row["text"] for row in expected["rows"])
        saved_row = db.query_one("SELECT date_from, date_to, expected_guests_override, summary FROM reservation WHERE id = ?", (saved["id"],))
        assert (saved_row["date_from"], saved_row["date_to"], saved_row["expected_guests_override"], saved_row["summary"]) == (
            arrival, departure, 2, "Refresh retry stay"
        )
        page.wait_for_function("""expected => {
            const normalize = value => (value || "").replace(/\\s+/g, " ").trim();
            const actual = {
                stats: normalize(document.querySelector('[data-dashboard-refresh="stats"]')?.textContent),
                rows: [...document.querySelectorAll('[data-dashboard-refresh="work"] .dashboard-row')].filter(row => !row.closest("noscript")).map(row => ({
                    id: row.getAttribute("data-stay-id"),
                    text: normalize(row.querySelector(".dashboard-row-copy")?.textContent)
                }))
            };
            return JSON.stringify(actual) === JSON.stringify(expected);
        }""", arg=expected)
        assert len(posts) == 1
        assert db.query_one("SELECT COUNT(*) AS n FROM reservation WHERE id = ?", (saved["id"],))["n"] == 1
        shot(page, "dashboard-refresh-retry-en")
        context.close()
        browser.close()
