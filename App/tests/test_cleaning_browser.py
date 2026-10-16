"""Real cleaning calendar/list sync, mobile readability, and external access."""
from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path
from datetime import timedelta

import pytest
import uvicorn

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, cleaning, cleaning_codes, cleaning_i18n, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs
from tests.test_cleaning import workspace, stay  # noqa: F401


@pytest.fixture
def origin(workspace):
    ws = workspace
    stay(ws["home"])
    stay(ws["home"], "2026-10-20", "2026-10-24")
    stay(ws["homes"][1], "2026-10-17", "2026-10-19")
    cleaning.save_settings(ws["home"], {"instructions": "1. Replace linen.\n2. Fresh towels.\n3. Check supplies."})
    cleaning_codes.save_manual(ws["home"], "001234")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(.05)
    assert server.started
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def browser_context(playwright, ws, origin, width=1280, js=True, signed_in=True):
    try:
        browser = playwright.chromium.launch(**chromium_launch_kwargs())
    except Exception:
        if REQUIRE_BROWSER:
            raise
        pytest.skip("Chromium is required for cleaning browser coverage")
    context = browser.new_context(viewport={"width": width, "height": 1000}, java_script_enabled=js)
    if signed_in:
        context.add_cookies([{"name": auth.SESSION_COOKIE, "value": ws["client"].cookies.get(auth.SESSION_COOKIE),
                             "url": origin + "/"}])
    return browser, context


def loaded(page):
    page.wait_for_selector("[data-cal-body]", state="attached", timeout=10000)
    page.wait_for_function("() => document.querySelector('[data-cal-body]')?.getAttribute('aria-busy') === 'false'")
    page.wait_for_selector(".cal-gantt-row, .cal-week, .cal-year")


def shot(page, name):
    directory = os.environ.get("UBYHOST_SHOTS_DIR")
    if directory:
        Path(directory).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(directory) / f"cleaning-{name}.png"), full_page=True)


@pytest.mark.parametrize("width", [360, 390, 1024, 1280])
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_calendar_and_large_list_geometry_and_filtering(workspace, origin, width, lang):
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, workspace, origin, width)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(f"{origin}/cleaning?lang={lang}")
        loaded(page)
        assert page.locator("[data-cal-auto]").count() == 1
        assert page.locator(".cal-week").count() > 0
        assert page.locator(".cal-gantt-row").count() == 0
        assert page.locator('[data-cal-view="calendar"]').get_attribute("aria-pressed") == "true"
        assert page.locator(".cleaning-card").count() == 3
        summaries = page.locator(".cal-day-summary")
        assert summaries.count() >= 1
        marker = page.locator(".cal-week-events .cal-event.is-cleaning-marker").first
        assert marker.count() == 1 and marker.is_visible()
        marker_box = marker.bounding_box()
        if width <= 760:
            assert marker_box["height"] >= 44
            marker.click()
            dialog = page.locator("[data-cal-day-dialog]")
            assert dialog.is_visible()
            dialog_marker = dialog.locator(".cal-day-list .cal-event.is-cleaning-marker")
            assert dialog_marker.is_visible()
            assert dialog_marker.locator(".cal-cleaning-label").is_visible()
            assert ("Cleaning" if lang == "en" else "Úklid") in dialog_marker.locator(".cal-cleaning-label").inner_text()
            assert dialog_marker.locator(".cal-cleaning-property").inner_text().strip()
            page.locator("[data-cal-day-dialog] [data-cal-close]").click()
        else:
            assert ("Cleaning" if lang == "en" else "Úklid") in marker.get_attribute("aria-label")
        assert page.locator(".cleaning-pin").first.inner_text() == "001234"
        assert page.locator("#cleaning-list input[type=checkbox]").count() == 0
        assert page.locator("#cleaning-list").bounding_box()["y"] > page.locator("#calendar").bounding_box()["y"]
        date_heading = page.locator(".cleaning-date-group h3").first
        assert 16 <= date_heading.evaluate("el => parseFloat(getComputedStyle(el).fontSize)") <= 18
        assert page.locator(".cleaning-card h4").first.evaluate("el => parseFloat(getComputedStyle(el).fontSize)") <= 16
        assert page.locator(".cleaning-card").first.evaluate("el => parseFloat(getComputedStyle(el).paddingTop)") <= 14
        assert page.locator(".cleaning-instructions").first.evaluate("el => parseFloat(getComputedStyle(el).fontSize)") >= 14
        assert page.locator(".cleaning-pin").first.evaluate("el => parseFloat(getComputedStyle(el).fontSize)") >= 20
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        assert page.locator('.sidebar-nav a[href="/cleaning"] svg').count() == 1
        shot(page, f"host-{lang}-{width}")
        page.locator("[data-cal-property]").select_option(str(workspace["homes"][1]))
        page.wait_for_function("() => document.querySelectorAll('.cleaning-card').length === 1")
        assert "Garden / 2" in page.locator(".cleaning-card").inner_text()
        assert not page.locator(".cleaning-pin").count()
        assert not errors
        context.close()
        browser.close()


def _assert_fractional_bar(page, event_id, start_day, start_hour, end_day, end_hour, property_id=None):
    link = page.locator(f'.cal-event[data-cal-event="{event_id}"]')
    assert link.count() == 1 and link.is_visible()
    bar = link.bounding_box()
    start_slot = page.locator(
        f'.cal-day[data-date="{start_day}"]' if property_id is None else
        f'.cal-gantt-slot[data-date="{start_day}"][data-property="{property_id}"]'
    ).bounding_box()
    end_slot = page.locator(
        f'.cal-day[data-date="{end_day}"]' if property_id is None else
        f'.cal-gantt-slot[data-date="{end_day}"][data-property="{property_id}"]'
    ).bounding_box()
    expected_left = start_slot["x"] + start_slot["width"] * start_hour / 24
    expected_right = end_slot["x"] + end_slot["width"] * end_hour / 24
    assert abs(bar["x"] - expected_left) <= 4, (bar, expected_left)
    assert abs(bar["x"] + bar["width"] - expected_right) <= 4, (bar, expected_right)


def _assert_cleaning_day_marker(page, event_id, day, property_name, lang, mobile):
    link = page.locator(f'.cal-week-events .cal-event.is-cleaning-marker[data-cal-event="{event_id}"]')
    assert link.count() == 1 and link.is_visible()
    box = link.bounding_box()
    cell = page.locator(f'.cal-day[data-date="{day}"]').bounding_box()
    assert box["x"] >= cell["x"] and box["x"] + box["width"] <= cell["x"] + cell["width"]
    assert box["width"] >= cell["width"] - 6
    details = link.get_attribute("aria-label") or ""
    expected = "Úklid" if lang == "cs" else "Cleaning"
    assert expected in details and property_name in details
    visual = link.evaluate("""element => {
      const css = getComputedStyle(element);
      const label = element.querySelector('.cal-cleaning-label');
      const icon = element.querySelector('svg');
      const count = element.querySelector('.cal-cleaning-count');
      const rgb = value => value.match(/[\\d.]+/g).slice(0, 3).map(Number);
      const linear = channel => (channel / 255 <= .04045 ? channel / 255 / 12.92 : ((channel / 255 + .055) / 1.055) ** 2.4);
      const luminance = value => {
        const channels = rgb(value).map(linear);
        return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2];
      };
      const a = luminance(css.backgroundColor), b = luminance(css.color);
      return {
        background: css.backgroundColor, color: css.color, border: css.borderTopStyle,
        contrast: (Math.max(a, b) + .05) / (Math.min(a, b) + .05),
        labelDisplay: label && getComputedStyle(label).display,
        labelFits: label && label.scrollWidth <= label.clientWidth + 1,
        labelText: label && label.textContent,
        iconVisible: !!icon && getComputedStyle(icon).display !== 'none',
        countVisible: !!count && getComputedStyle(count).display !== 'none'
      };
    }""")
    assert visual["background"] == "rgb(245, 185, 66)"
    assert visual["color"] == "rgb(32, 32, 30)"
    assert visual["border"] == "solid"
    assert visual["contrast"] >= 7
    assert visual["iconVisible"]
    if mobile:
        assert box["height"] >= 44
        assert visual["countVisible"] and visual["labelDisplay"] == "none"
    else:
        assert box["width"] >= 120
        assert visual["labelDisplay"] != "none" and visual["labelFits"]
        assert expected in visual["labelText"]


@pytest.mark.parametrize(("width", "lang"), [(1280, "en"), (1280, "cs"), (360, "en"), (390, "cs")])
def test_fractional_checkout_and_same_day_cleaning_geometry(workspace, origin, width, lang):
    ws = workspace
    booking_id = stay(ws["home"], "2026-10-15", "2026-10-17")
    # A second property checks out the same day, so overflow must name cleaning
    # and the two date-wide layout footprints cannot collapse into one lane.
    second_booking_id = stay(ws["homes"][1], "2026-10-15", "2026-10-17")
    short_jobs = [
        cleaning.save_event(ws["home"], {"scheduled_date": "2026-10-25", "start_time": "09:00", "end_time": "10:00"}),
        cleaning.save_event(ws["home"], {"scheduled_date": "2026-10-25", "start_time": "14:00", "end_time": "15:00"}),
    ]
    scheduled = cleaning.schedule(ws["owner"], cleaning.today(), cleaning.today() + timedelta(days=30))
    booking_event = f"reservation:{booking_id}"
    day_cleanings = [item for item in scheduled["cleanings"] if item["checkout"] == "2026-10-17"]
    assert len(day_cleanings) == 2
    home_cleaning = next(item for item in day_cleanings if item["propertyId"] == ws["home"])
    assert home_cleaning["displayStart"] == "2026-10-17T11:00"
    assert home_cleaning["displayEnd"] == "2026-10-17T15:00"
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang={lang}")
        loaded(page)
        shot(page, f"day-marker-{lang}-{width}")
        visible = [item for item in day_cleanings
                   if page.locator(f'.cal-event[data-cal-event="{item["id"]}"]').is_visible()]
        assert len(visible) == 1
        marker = visible[0]
        property_name = next(prop["internal_name"] for prop in cleaning.properties(ws["owner"])
                             if prop["id"] == marker["propertyId"])
        mobile = width <= 760
        _assert_cleaning_day_marker(page, marker["id"], "2026-10-17", property_name, lang, mobile)
        visible_booking_boxes = [
            page.locator(f'.cal-event[data-cal-event="reservation:{stay_id}"]')
            for stay_id in (booking_id, second_booking_id)
        ]
        visible_booking_boxes = [item.bounding_box() for item in visible_booking_boxes if item.is_visible()]
        assert visible_booking_boxes
        marker_box = page.locator(f'.cal-event[data-cal-event="{marker["id"]}"]').bounding_box()
        assert marker_box["y"] + marker_box["height"] <= min(item["y"] for item in visible_booking_boxes) + 1
        overflow = page.locator('.cal-day-summary.has-cleaning-overflow[data-cal-more="2026-10-17"]')
        assert overflow.count() == 1 and overflow.is_visible()
        overflow_label = overflow.get_attribute("aria-label") or ""
        assert ("úklid" if lang == "cs" else "cleaning") in overflow_label.casefold()
        overflow_visual = overflow.evaluate("""element => {
          const css = getComputedStyle(element);
          return {
            background: css.backgroundColor,
            icon: !!element.querySelector('svg') && getComputedStyle(element.querySelector('svg')).display !== 'none',
            count: element.querySelector('.cal-cleaning-overflow-count')?.textContent,
            height: element.getBoundingClientRect().height
          };
        }""")
        assert overflow_visual["background"] == "rgb(245, 185, 66)" and overflow_visual["icon"]
        assert overflow_visual["count"] == "+1"
        if mobile:
            assert overflow_visual["height"] >= 44
        overflow.click()
        assert page.locator("[data-cal-day-dialog]").is_visible()
        dialog_marker = page.locator("[data-cal-day-dialog] .cal-day-list .cal-event.is-cleaning-marker")
        assert dialog_marker.locator(".cal-cleaning-label").is_visible()
        assert property_name in dialog_marker.locator(".cal-cleaning-property").inner_text()
        page.locator("[data-cal-day-dialog] [data-cal-close]").click()
        single_cleaning_overflow = page.locator('.cal-day-summary.has-cleaning-overflow[data-cal-more="2026-10-19"]')
        assert single_cleaning_overflow.count() == 0
        if not mobile:
            link = page.locator(f'.cal-event[data-cal-event="{marker["id"]}"]')
            link.focus()
            link.press("Enter")
            assert page.locator("[data-cal-details]").is_visible()
            page.locator("[data-cal-details] [data-cal-close]").click()
            _assert_fractional_bar(page, booking_event, "2026-10-15", 15, "2026-10-17", 11)
            page.locator('[data-cal-view="gantt"]').click()
            page.wait_for_selector(".cal-gantt-row")
            # Gantt starts on Oct 16; the reservation is clipped at that range edge,
            # while its checkout and the real cleaning time remain independent.
            _assert_fractional_bar(page, booking_event, "2026-10-16", 0, "2026-10-17", 11, ws["home"])
            gantt_marker = page.locator(f'.cal-event.is-gantt-cleaning[data-cal-event="{marker["id"]}"]')
            slot = page.locator(
                f'.cal-gantt-slot[data-date="2026-10-17"][data-property="{marker["propertyId"]}"]'
            ).bounding_box()
            box = gantt_marker.bounding_box()
            assert box["x"] >= slot["x"] and box["x"] + box["width"] <= slot["x"] + slot["width"]
            assert box["width"] >= slot["width"] - 6
            assert gantt_marker.is_visible() and gantt_marker.get_attribute("aria-label")
            assert gantt_marker.locator("svg").is_visible()
            short_markers = [page.locator(f'.cal-event.is-gantt-cleaning[data-cal-event="cleaning:{job_id}"]')
                             for job_id in short_jobs]
            assert all(item.is_visible() for item in short_markers)
            short_boxes = [item.bounding_box() for item in short_markers]
            assert abs(short_boxes[0]["y"] - short_boxes[1]["y"]) >= 20
            short_slot = page.locator(f'.cal-gantt-slot[data-date="2026-10-25"][data-property="{ws["home"]}"]').bounding_box()
            assert all(box["width"] >= short_slot["width"] - 6 for box in short_boxes)
            shot(page, f"day-marker-gantt-{lang}-{width}")
        _, token = cleaning.new_share(ws["owner"], [marker["propertyId"]])
        page.goto(f"{origin}/cleaning/shared/{token}?lang={lang}")
        loaded(page)
        calendar_mode = page.locator('[data-cal-view="calendar"]')
        if calendar_mode.count() and calendar_mode.get_attribute("aria-pressed") != "true":
            calendar_mode.click()
            loaded(page)
        shared_marker = page.locator(f'.cal-event.is-cleaning-marker[data-cal-event="{marker["id"]}"]')
        assert shared_marker.is_visible()
        shared_box = shared_marker.bounding_box()
        shared_cell = page.locator('.cal-day[data-date="2026-10-17"]').bounding_box()
        assert shared_box["width"] >= shared_cell["width"] - 6
        assert shared_marker.get_attribute("draggable") != "true"
        _assert_cleaning_day_marker(page, marker["id"], "2026-10-17", property_name, lang, mobile)
        shot(page, f"day-marker-shared-{lang}-{width}")
        context.close()
        browser.close()

def test_three_property_auto_gantt_keeps_cleaning_markers_visible(workspace, origin):
    ws = workspace
    third = db.insert("apartment", {
        "owner_user_id": ws["owner"], "internal_name": "Third test property", "active": 1,
        "created_at": db.utcnow(), "automation_mode": "manual", "checkin_hour": 15, "checkout_hour": 11,
    })
    stay(third, "2026-10-15", "2026-10-17")
    scheduled = cleaning.schedule(ws["owner"], cleaning.today(), cleaning.today() + timedelta(days=30))
    expected = {item["id"] for item in scheduled["cleanings"]}
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin)
        page = context.new_page()
        page.goto(origin + "/cleaning?lang=en")
        loaded(page)
        assert page.locator('[data-cal-view="gantt"]').get_attribute("aria-pressed") == "true"
        assert page.locator(".cal-gantt-row").count() == 3
        for event_id in expected:
            assert page.locator(f'.cal-event[data-cal-event="{event_id}"]').is_visible()
        context.close()
        browser.close()


def test_missing_code_is_omitted_from_host_list_and_calendar_dialog(workspace, origin):
    ws = workspace
    db.update("cleaning_property", ws["home"], {"code_id": None})
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin)
        page = context.new_page()
        page.goto(origin + "/cleaning?lang=en")
        loaded(page)
        assert page.locator(".cleaning-card .cleaning-access").count() == 0
        assert page.locator(".cleaning-card").get_by_text("Door code unavailable", exact=False).count() == 0
        block = page.locator('.cal-event[data-event-kind="cleaning"]').first
        block.click()
        assert page.locator("[data-cal-details]").is_visible()
        assert page.locator("[data-cal-detail-content] .cleaning-access").count() == 0
        assert page.locator("[data-cal-detail-content]").get_by_text("Door code unavailable", exact=False).count() == 0
        _, token = cleaning.new_share(ws["owner"], [ws["home"]])
        page.goto(f"{origin}/cleaning/shared/{token}?lang=en")
        loaded(page)
        assert page.locator(".cleaning-card .cleaning-access").count() == 0
        assert page.locator(".cleaning-card").get_by_text("Door code unavailable", exact=False).count() == 0
        page.locator('.cal-event[data-event-kind="cleaning"]').first.click()
        assert page.locator("[data-cal-detail-content] .cleaning-access").count() == 0
        assert page.locator("[data-cal-detail-content]").get_by_text("Door code unavailable", exact=False).count() == 0
        context.close()
        browser.close()


def test_host_crud_and_drag_change_cleanings_without_moving_bookings(workspace, origin):
    ws = workspace
    before = [dict(row) for row in db.query("SELECT id, date_from, date_to FROM reservation ORDER BY id")]
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin)
        page = context.new_page()
        # The calendar may load before its list consumer on a slow connection.
        def delayed_list_script(route):
            time.sleep(.3)
            route.continue_()
        page.route("**/static/cleaning.js?*", delayed_list_script)
        page.goto(origin + "/cleaning?lang=en")
        loaded(page)
        page.locator('[data-cal-view="gantt"]').click()
        page.wait_for_selector(".cal-gantt-row")
        first = next(item for item in cleaning.schedule(ws["owner"], cleaning.today(), cleaning.today() + timedelta(days=30))["cleanings"]
                     if item["propertyId"] == ws["home"])
        source = page.locator(f'[data-cal-event="cleaning:{first["eventId"]}"]')
        target = page.locator(f'[data-date="2026-10-22"][data-property="{ws["home"]}"]')
        with page.expect_response(lambda response: response.url.endswith(f"/cleaning/events/{first['eventId']}") and response.request.method == "POST") as saved:
            source.drag_to(target)
        assert saved.value.status == 200
        persisted_times = db.query_one("SELECT start_time, end_time FROM cleaning_event WHERE id = ?", (first["eventId"],))
        assert persisted_times["start_time"] is None and persisted_times["end_time"] is None
        page.wait_for_function(
            "(id) => document.querySelector('#cleaning-' + id).closest('.cleaning-date-group').querySelector('time').dateTime === '2026-10-22'",
            arg=first["eventId"],
        )
        page.get_by_role("link", name="Add cleaning", exact=True).click()
        page.select_option("#clean-property", str(ws["home"]))
        page.fill("#clean-date", "2026-10-23")
        page.fill("#clean-notes", "Mid-stay refresh")
        page.get_by_role("button", name="Save", exact=True).click()
        loaded(page)
        card = page.locator(".cleaning-card").filter(has_text="Mid-stay refresh")
        card.get_by_role("link", name="Edit cleaning", exact=True).click()
        page.fill("#clean-date", "2026-10-25")
        page.get_by_role("button", name="Save", exact=True).click()
        loaded(page)
        card = page.locator(".cleaning-card").filter(has_text="Mid-stay refresh")
        assert card.locator("xpath=..").locator("time").get_attribute("datetime") == "2026-10-25"
        card.get_by_role("link", name="Edit cleaning", exact=True).click()
        page.locator(".cleaning-remove summary").click()
        page.get_by_role("button", name="Remove cleaning", exact=True).click()
        page.locator("#confirm-dialog [data-confirm-proceed]").click()
        loaded(page)
        assert page.locator(".cleaning-card").filter(has_text="Mid-stay refresh").count() == 0
        shot(page, "host-after-drag-1280")
        assert [dict(row) for row in db.query("SELECT id, date_from, date_to FROM reservation ORDER BY id")] == before
        context.close()
        browser.close()


def test_external_dual_view_and_no_javascript_list(workspace, origin):
    ws = workspace
    _, token = cleaning.new_share(ws["owner"], [ws["home"]])
    with sync_api.sync_playwright() as playwright:
        for js in (True, False):
            browser, context = browser_context(playwright, ws, origin, width=390, js=js, signed_in=False)
            page = context.new_page()
            page.goto(f"{origin}/cleaning/shared/{token}?lang=cs")
            if js:
                loaded(page)
                assert page.locator("[data-cal-event][draggable=true]").count() == 0
                page.locator("[data-cal-day]").first.click()
                assert not page.locator("[data-cal-create]").is_visible()
            assert page.locator(".cleaning-card").count() == 2
            assert page.locator(".cleaning-pin").first.inner_text() == "001234"
            assert page.locator(".cleaning-card-actions").count() == 0
            assert "Garden / 2" not in page.locator("body").inner_text()
            assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
            if js:
                page.locator("dialog[open] [data-cal-close]").click()
            shot(page, f"shared-cs-390-{'js' if js else 'nojs'}")
            context.close()
            browser.close()


def test_calendar_popup_types_create_in_place_and_localize_validation(workspace, origin):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width=1280)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang=cs")
        loaded(page)
        pathname = page.evaluate("location.pathname")

        page.locator('[data-calendar-add][data-cal-create-type="stay"]').click()
        dialog = page.locator("[data-cal-create]")
        assert dialog.is_visible()
        assert page.locator('[data-cal-type-choice="stay"]').get_attribute("aria-pressed") == "true"
        stay_date = page.locator("#cal-arrival").input_value()
        page.locator('[data-cal-type-choice="cleaning"]').click()
        assert page.locator("#cal-clean-date").input_value() == stay_date
        page.locator('[data-cal-type-choice="stay"]').click()
        assert page.locator("#cal-arrival").input_value() == stay_date
        page.locator("[data-cal-close]").click()

        page.locator('[data-calendar-add][data-cal-create-type="cleaning"]').click()
        dialog = page.locator("[data-cal-create]")
        page.locator("#cal-property").select_option(str(ws["home"]))
        page.locator("#cal-clean-date").fill("2026-10-27")
        page.locator("#cal-clean-notes").fill("Popup cleaning note")
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  response.url.split("?")[0].endswith("/cleaning/events")) as result:
            page.locator("[data-cal-save]").click()
        response = result.value
        assert response.status == 201
        created = response.json()
        assert page.evaluate("location.pathname") == pathname
        assert page.locator(f'.cal-event[data-cal-event="cleaning:{created["id"]}"]').is_visible()
        shot(page, "cleaning-create-popup-cs")

        page.locator('[data-calendar-add][data-cal-create-type="cleaning"]').click()
        invalid_date = page.locator("#cal-clean-date")
        invalid_date.evaluate("(input) => { input.value = ''; input.removeAttribute('required'); }")
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  response.url.split("?")[0].endswith("/cleaning/events")) as failure:
            page.locator("[data-cal-form]").evaluate("(form) => form.requestSubmit()")
        assert failure.value.status == 422
        expected = cleaning_i18n.translator("cs")("dates")
        error = page.locator('[data-cal-error-for="scheduled_date"]')
        assert error.is_visible() and error.inner_text() == expected
        assert page.evaluate("location.pathname") == pathname
        shot(page, "cleaning-create-error-cs")
        context.close()
        browser.close()


def test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults(workspace, origin):
    ws = workspace
    db.update("apartment", ws["home"], {"checkin_hour": None, "checkout_hour": None})
    event_id = cleaning.save_event(ws["home"], {"scheduled_date": "2026-10-26", "notes": "Unset hours"})
    scheduled = cleaning.schedule(ws["owner"], cleaning.today(), cleaning.today() + timedelta(days=30))
    item = next(event for event in scheduled["cleanings"] if event["eventId"] == event_id)
    assert item["timingUnavailable"] is True
    saved = db.query_one("SELECT checkin_hour, checkout_hour FROM apartment WHERE id = ?", (ws["home"],))
    assert saved["checkin_hour"] is None and saved["checkout_hour"] is None
    property_name = next(prop["internal_name"] for prop in cleaning.properties(ws["owner"])
                         if prop["id"] == ws["home"])
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width=360)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang=en")
        loaded(page)
        _assert_cleaning_day_marker(page, f"cleaning:{event_id}", "2026-10-26", property_name, "en", True)
        marker = page.locator(f'.cal-week-events .cal-event.is-cleaning-marker[data-cal-event="cleaning:{event_id}"]')
        marker.click()
        assert page.locator("[data-cal-details] .cleaning-warning").count() >= 1
        shot(page, "cleaning-marker-unset-hours-mobile")
        context.close()
        browser.close()
