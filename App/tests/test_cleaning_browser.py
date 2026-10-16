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

from app import auth, cleaning, cleaning_codes, db
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
        if width <= 760:
            assert summaries.first.bounding_box()["height"] >= 44
        assert ("Cleaning" if lang == "en" else "Úklid") in summaries.first.inner_text()
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


def test_fractional_checkout_and_same_day_cleaning_geometry(workspace, origin):
    ws = workspace
    booking_id = stay(ws["home"], "2026-10-15", "2026-10-17")
    scheduled = cleaning.schedule(ws["owner"], cleaning.today(), cleaning.today() + timedelta(days=30))
    booking_event = f"reservation:{booking_id}"
    cleaning_event = next(item for item in scheduled["cleanings"] if item["checkout"] == "2026-10-17")
    assert cleaning_event["displayStart"] == "2026-10-17T11:00"
    assert cleaning_event["displayEnd"] == "2026-10-17T15:00"
    for width in (1280, 360):
        with sync_api.sync_playwright() as playwright:
            browser, context = browser_context(playwright, ws, origin, width)
            page = context.new_page()
            page.goto(origin + "/cleaning?lang=en")
            loaded(page)
            if width <= 760:
                summary = page.locator('.cal-day-summary[data-cal-more="2026-10-17"]')
                assert summary.count() == 1
                assert summary.bounding_box()["height"] >= 44
                assert "Cleaning" in summary.inner_text()
                summary.click()
                assert page.locator("[data-cal-day-dialog]").is_visible()
                page.locator("[data-cal-day-dialog] [data-cal-close]").click()
            else:
                _assert_fractional_bar(page, booking_event, "2026-10-15", 15, "2026-10-17", 11)
                _assert_fractional_bar(page, cleaning_event["id"], "2026-10-17", 11, "2026-10-17", 15)
                page.locator('[data-cal-view="gantt"]').click()
                page.wait_for_selector(".cal-gantt-row")
                _assert_fractional_bar(page, booking_event, "2026-10-15", 15, "2026-10-17", 11, ws["home"])
                _assert_fractional_bar(page, cleaning_event["id"], "2026-10-17", 11, "2026-10-17", 15, ws["home"])
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
