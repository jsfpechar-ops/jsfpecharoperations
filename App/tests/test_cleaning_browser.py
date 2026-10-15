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
    page.wait_for_selector(".cal-gantt-row")


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
        assert page.locator(".cleaning-card").count() == 3
        assert page.locator(".cleaning-pin").first.inner_text() == "001234"
        assert page.locator("#cleaning-list input[type=checkbox]").count() == 0
        assert page.locator("#cleaning-list").bounding_box()["y"] > page.locator("#calendar").bounding_box()["y"]
        assert page.locator(".cleaning-instructions").first.evaluate("el => parseFloat(getComputedStyle(el).fontSize)") >= 18
        assert page.locator(".cleaning-pin").first.evaluate("el => parseFloat(getComputedStyle(el).fontSize)") >= 24
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
        first = next(item for item in cleaning.schedule(ws["owner"], cleaning.today(), cleaning.today() + timedelta(days=30))["cleanings"]
                     if item["propertyId"] == ws["home"])
        source = page.locator(f'[data-cal-event="cleaning:{first["eventId"]}"]')
        target = page.locator(f'[data-date="2026-10-22"][data-property="{ws["home"]}"]')
        with page.expect_response(lambda response: response.url.endswith(f"/cleaning/events/{first['eventId']}") and response.request.method == "POST") as saved:
            source.drag_to(target)
        assert saved.value.status == 200
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
