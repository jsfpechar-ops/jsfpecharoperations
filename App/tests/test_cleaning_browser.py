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
from tests.browser_support import chromium_launch_kwargs, settle_motion
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


def _client_geometry_box(locator):
    """Geometry for an element that may sit in a scroll container (gantt track).

    Playwright's bounding_box() can return None when the node is not considered
    layout-visible even though getBoundingClientRect() has size. The gantt
    also replaces those nodes while a scroll is in progress, so a detached
    read is retried instead of failing the test.
    """
    last = {"x": 0, "y": 0, "width": 0, "height": 0}
    for _ in range(8):
        try:
            box = locator.evaluate(
                """node => {
                  if (!node.isConnected) return null;
                  const r = node.getBoundingClientRect();
                  return {x: r.x, y: r.y, width: r.width, height: r.height};
                }"""
            )
        except sync_api.Error:
            box = None
        if box and box["width"] > 0 and box["height"] > 0:
            return box
        if box:
            last = box
        try:
            locator.scroll_into_view_if_needed(timeout=1000)
        except sync_api.Error:
            pass
        locator.page.wait_for_timeout(50)
    return last


@pytest.mark.parametrize("width", [768, 1024, 1280])
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
        assert page.locator('.cleaning-section tr[id^="cleaning-"]').count() == 3
        # 0834 tile UI: the host calendar shows no booking bars. Each cleaning is a
        # tile chip on its day, and the day sheet names it with its full property label.
        assert page.locator(".cal-week-events").count() == 0
        tagged = page.locator(".cal-day.has-cleaning")
        assert tagged.count() >= 1
        chip = tagged.first.locator(".cal-tile-chip.cal-clean-chip")
        assert chip.is_visible() and chip.locator("svg").count() >= 1
        page.locator('.cal-day[data-date="2026-10-19"] .cal-day-number').click(position={"x": 12, "y": 10})  # 0956: stay bars sit under the day number, so click the number band
        dialog = page.locator("[data-cal-day-dialog]")
        assert dialog.is_visible()
        dialog_markers = dialog.locator(".cal-day-list .cal-event.is-cleaning-marker")
        assert dialog_markers.count() >= 1
        for index in range(dialog_markers.count()):
            dialog_marker = dialog_markers.nth(index)
            assert dialog_marker.is_visible()
            assert dialog_marker.locator(".cal-cleaning-label").is_visible()
            assert ("Cleaning" if lang == "en" else "Úklid") in dialog_marker.locator(".cal-cleaning-label").inner_text()
            assert dialog_marker.locator(".cal-cleaning-property").inner_text().strip()
        page.locator("[data-cal-day-dialog] [data-cal-close]").click()
        assert page.locator(".cleaning-pin").count() == 0
        assert page.locator("#cleaning-list input[type=checkbox]").count() == 0
        assert page.locator("#cleaning-list").is_hidden()
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        assert page.locator('a.nav[href="/cleaning"] svg').count() == 1
        shot(page, f"host-{lang}-{width}")
        page.locator("[data-cal-property]").select_option(str(workspace["homes"][1]))
        page.wait_for_function("() => document.querySelectorAll('.cleaning-section tr[id^=cleaning-]').length === 1")
        assert "Garden / 2" in page.locator('.cleaning-section tr[id^="cleaning-"]').inner_text()
        assert not page.locator(".cleaning-pin").count()
        assert not errors
        context.close()
        browser.close()


def _assert_fractional_bar(page, event_id, start_day, start_hour, end_day, end_hour, property_id=None):
    event_container = ".cal-gantt-events" if property_id is not None else ".cal-week-events"
    link = page.locator(f'{event_container} .cal-event[data-cal-event="{event_id}"]')
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
      const prop = element.querySelector('.cal-cleaning-property');
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
        ariaLabel: element.getAttribute('aria-label') || '',
        titleAttr: element.getAttribute('title') || '',
        propertyText: prop ? prop.textContent : '',
        propertyWidth: prop ? prop.getBoundingClientRect().width : 0,
        propertyDisplay: prop && getComputedStyle(prop).display,
        iconVisible: !!icon && getComputedStyle(icon).display !== 'none',
        countVisible: !!count && getComputedStyle(count).display !== 'none'
      };
    }""")
    assert visual["background"] == "rgb(255, 244, 214)"  # --amber-bg (0106 quiet amber pill)
    assert visual["color"] == "rgb(107, 58, 0)"  # --status-action-ink
    assert visual["border"] == "solid"
    assert visual["contrast"] >= 7
    assert visual["iconVisible"]
    if mobile:
        assert box["height"] >= 44
        assert visual["countVisible"] and visual["labelDisplay"] == "none"
    else:
        assert box["width"] >= 120
        # The visible word stays hidden on desktop (the icon carries it); the
        # localized word must reach assistive tech and hover via aria-label/title.
        assert expected in visual["ariaLabel"] and expected in visual["titleAttr"]
        assert property_name in visual["propertyText"]
        assert visual["propertyDisplay"] != "none" and visual["propertyWidth"] > 0


@pytest.mark.parametrize(("width", "lang"), [(1280, "en"), (1280, "cs")])
def test_fractional_checkout_and_same_day_cleaning_geometry(workspace, origin, width, lang):
    ws = workspace
    stay(ws["home"], "2026-10-15", "2026-10-17")
    # A second property checks out the same day, so the 17th carries two cleaning tags.
    stay(ws["homes"][1], "2026-10-15", "2026-10-17")
    short_jobs = [
        cleaning.save_event(ws["home"], {"scheduled_date": "2026-10-25", "start_time": "09:00", "end_time": "10:00"}),
        cleaning.save_event(ws["home"], {"scheduled_date": "2026-10-25", "start_time": "14:00", "end_time": "15:00"}),
    ]
    scheduled = cleaning.schedule(ws["owner"], cleaning.today(), cleaning.today() + timedelta(days=30))
    day_cleanings = [item for item in scheduled["cleanings"] if item["checkout"] == "2026-10-17"]
    assert len(day_cleanings) == 2
    home_cleaning = next(item for item in day_cleanings if item["propertyId"] == ws["home"])
    assert home_cleaning["displayStart"] == "2026-10-17T11:00"
    assert home_cleaning["displayEnd"] == "2026-10-17T15:00"
    marker = home_cleaning
    property_name = next(prop["internal_name"] for prop in cleaning.properties(ws["owner"])
                         if prop["id"] == marker["propertyId"])
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang={lang}")
        loaded(page)
        shot(page, f"day-marker-{lang}-{width}")
        day = page.locator('.cal-day[data-date="2026-10-17"]')
        chips = day.locator(".cal-tile-chip.cal-clean-chip")
        assert chips.count() == 2
        assert all(chips.nth(index).is_visible() for index in range(2))
        # Tile chips carry the localized word; the real start time is checked on the gantt marker below.
        word = "Úklid" if lang == "cs" else "Cleaning"
        assert all(word in chips.nth(index).inner_text() for index in range(2))
        assert day.locator(".cal-tile-more").count() == 0
        day.locator(".cal-day-number").click(position={"x": 12, "y": 10})  # 0905: stacked pills cover the tile centre
        dialog = page.locator("[data-cal-day-dialog]")
        assert dialog.is_visible()
        dialog_marker = dialog.locator(f'.cal-day-list .cal-event.is-cleaning-marker[data-cal-event="{marker["id"]}"]')
        assert dialog_marker.is_visible()
        assert dialog_marker.locator(".cal-cleaning-label").is_visible()
        assert property_name in dialog_marker.locator(".cal-cleaning-property").inner_text()
        # Queue close and move focus in one task so the delayed close handler
        # cannot steal focus back from the day that opened the sheet.
        focus_kept = page.evaluate("""async selector => {
          const dialog = document.querySelector('[data-cal-day-dialog]');
          const target = document.querySelector(selector);
          const closed = new Promise(resolve =>
            dialog.addEventListener('close', resolve, {once: true}));
          dialog.querySelector('[data-cal-close]').click();
          target.focus();
          await closed;
          return document.activeElement === target;
        }""", '.cal-day[data-date="2026-10-17"] .cal-day-number')
        assert focus_kept, "The day dialog close handler stole focus from the day tile"
        day.locator(".cal-day-number").click()
        dialog_marker.focus()
        dialog_marker.press("Enter")
        page.locator("[data-cal-details]").wait_for(state="visible")
        page.locator("[data-cal-details] [data-cal-close]").click()
        # 0956: Gantt is offered only with 3+ active properties. The workspace can be shared
        # with the en run, so add an empty third property only when fewer than three exist.
        if len(cleaning.properties(ws["owner"])) < 3:
            db.insert("apartment", {
                "owner_user_id": ws["owner"], "internal_name": "Third test property", "active": 1,
                "created_at": db.utcnow(), "automation_mode": "manual", "checkin_hour": 15, "checkout_hour": 11,
            })
        # Explicit cal_date: a reload could race the calendar's async URL update and open on today.
        page.goto(f"{origin}/cleaning?lang={lang}&cal_date=2026-10-17")
        loaded(page)
        page.locator('[data-cal-view="gantt"]').click()
        page.wait_for_selector(".cal-gantt-row")
        # 0834: the host gantt draws cleaning markers only, so booking-bar geometry
        # is no longer asserted here. The cleaning time is checked on its marker.
        gantt_marker = page.locator(f'.cal-gantt-events .cal-event.is-gantt-cleaning[data-cal-event="{marker["id"]}"]')
        slot_locator = page.locator(
            f'.cal-gantt-slot[data-date="2026-10-17"][data-property="{marker["propertyId"]}"]'
        )
        gantt_marker.wait_for(state="visible")
        slot_locator.wait_for(state="visible")
        # Layout can paint the gantt after the first frame; avoid null bounding boxes (flaky on cs; repro on base 7b0355c).
        page.wait_for_function(
            'sel => {\n              const slot = document.querySelector(sel[0]);\n              const mark = document.querySelector(sel[1]);\n              if (!slot || !mark) return false;\n              const a = slot.getBoundingClientRect();\n              const b = mark.getBoundingClientRect();\n              return a.width > 0 && a.height > 0 && b.width > 0 && b.height > 0;\n            }',
            arg=[
                f'.cal-gantt-slot[data-date="2026-10-17"][data-property="{marker["propertyId"]}"]',
                f'.cal-gantt-events .cal-event.is-gantt-cleaning[data-cal-event="{marker["id"]}"]',
            ],
        )
        slot = _client_geometry_box(slot_locator)
        box = _client_geometry_box(gantt_marker)
        assert slot["width"] > 0 and slot["height"] > 0 and box["width"] > 0 and box["height"] > 0, (
            "Gantt slot or cleaning marker has no usable box")
        assert box["x"] >= slot["x"] and box["x"] + box["width"] <= slot["x"] + slot["width"]
        assert box["width"] >= slot["width"] - 6
        assert gantt_marker.is_visible() and gantt_marker.get_attribute("aria-label")
        assert gantt_marker.locator("svg").is_visible()
        short_markers = [page.locator(f'.cal-gantt-events .cal-event.is-gantt-cleaning[data-cal-event="cleaning:{job_id}"]')
                         for job_id in short_jobs]
        assert all(item.is_visible() for item in short_markers)
        short_boxes = [_client_geometry_box(item) for item in short_markers]
        assert abs(short_boxes[0]["y"] - short_boxes[1]["y"]) >= 20
        short_slot = _client_geometry_box(
            page.locator(f'.cal-gantt-slot[data-date="2026-10-25"][data-property="{ws["home"]}"]'))
        assert all(b["width"] >= short_slot["width"] - 6 for b in short_boxes)
        shot(page, f"day-marker-gantt-{lang}-{width}")
        _, token = cleaning.new_share(ws["owner"], [marker["propertyId"]])
        page.goto(f"{origin}/cleaning/shared/{token}?lang={lang}&from=2026-09-28&to=2026-11-02")
        loaded(page)
        calendar_mode = page.locator('[data-cal-view="calendar"]')
        if calendar_mode.count() and calendar_mode.get_attribute("aria-pressed") != "true":
            calendar_mode.click()
            loaded(page)
        shared_marker = page.locator(f'.cal-week-events .cal-event.is-cleaning-marker[data-cal-event="{marker["id"]}"]')
        assert shared_marker.is_visible()
        shared_box = shared_marker.bounding_box()
        shared_cell = page.locator('.cal-day[data-date="2026-10-17"]').bounding_box()
        assert shared_box["width"] >= shared_cell["width"] - 6
        assert shared_marker.get_attribute("draggable") != "true"
        _assert_cleaning_day_marker(page, marker["id"], "2026-10-17", property_name, lang, False)
        shot(page, f"day-marker-shared-{lang}-{width}")
        context.close()
        browser.close()


@pytest.mark.parametrize(("width", "lang"), [(768, "en"), (768, "cs"), (1280, "en")])
def test_three_property_auto_gantt_keeps_cleaning_markers_visible(workspace, origin, width, lang):
    ws = workspace
    third = db.insert("apartment", {
        "owner_user_id": ws["owner"], "internal_name": "Third test property", "active": 1,
        "created_at": db.utcnow(), "automation_mode": "manual", "checkin_hour": 15, "checkout_hour": 11,
    })
    stay(third, "2026-10-15", "2026-10-17")
    scheduled = cleaning.schedule(ws["owner"], cleaning.today(), cleaning.today() + timedelta(days=30))
    expected = {item["id"]: item for item in scheduled["cleanings"]}
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width=width)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang={lang}")
        loaded(page)
        assert page.locator('[data-cal-view="gantt"]').get_attribute("aria-pressed") == "true"
        assert page.locator(".cal-gantt-row").count() == 3
        for event_id, item in expected.items():
            marker = page.locator(f'.cal-gantt-events .cal-event[data-cal-event="{event_id}"]')
            marker.wait_for(state="visible")
            assert ("Úklid" if lang == "cs" else "Cleaning") in (marker.get_attribute("aria-label") or "")
            slot = page.locator(f'.cal-gantt-slot[data-date="{item["date"]}"][data-property="{item["propertyId"]}"]')
            slot_box, marker_box = slot.bounding_box(), marker.bounding_box()
            assert marker_box["width"] >= slot_box["width"] - 6
            if width <= 760:
                assert marker.locator("svg").is_visible()
                assert marker.locator(".cal-cleaning-count").is_visible()
                assert marker_box["height"] >= 44
        shot(page, f"three-property-gantt-{lang}-{width}")
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
        assert page.locator(".cleaning-section .cleaning-access").count() == 0
        assert page.locator(".cleaning-section").get_by_text("Door code unavailable", exact=False).count() == 0
        page.locator(".cal-day.has-cleaning .cal-day-number").first.click(position={"x": 12, "y": 10})  # 0956: stay bars sit under the day number, so click the number band
        block = page.locator('[data-cal-day-dialog] .cal-event[data-event-kind="cleaning"]').first
        block.click()
        assert page.locator("[data-cal-details]").is_visible()
        assert page.locator("[data-cal-detail-content] .cleaning-access").count() == 0
        assert page.locator("[data-cal-detail-content]").get_by_text("Door code unavailable", exact=False).count() == 0
        _, token = cleaning.new_share(ws["owner"], [ws["home"]])
        page.goto(f"{origin}/cleaning/shared/{token}?lang=en&from=2026-09-28&to=2026-11-02")
        loaded(page)
        assert page.locator(".cleaning-card .cleaning-access").count() == 0
        assert page.locator(".cleaning-card").get_by_text("Door code unavailable", exact=False).count() == 0
        page.locator('.cal-event[data-event-kind="cleaning"]').first.click()
        assert page.locator("[data-cal-detail-content] .cleaning-access").count() == 0
        assert page.locator("[data-cal-detail-content]").get_by_text("Door code unavailable", exact=False).count() == 0
        context.close()
        browser.close()


def test_host_crud_and_drag_change_cleanings_without_moving_bookings(workspace, origin):
    # 0834 part B: the tile calendar has no drag and no table rows. Create runs from the
    # header, the day sheet opens the details, and edit and remove use the edit page.
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
        page.goto(origin + "/cleaning?lang=en&cal_date=2026-10-27")
        loaded(page)
        pathname = page.evaluate("location.pathname")
        page.locator('[data-calendar-add][data-cal-create-type="cleaning"]').click()
        create = page.locator("[data-cal-create]")
        assert create.is_visible()
        assert page.locator('[data-cal-type-choice="cleaning"]').get_attribute("aria-pressed") == "true"
        page.locator("#cal-property").select_option(str(ws["home"]))
        page.locator("#cal-clean-date").fill("2026-10-23")
        page.locator("#cal-clean-notes").fill("Mid-stay refresh")
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  response.url.split("?")[0].endswith("/cleaning/events")) as created:
            page.locator("[data-cal-save]").click()
        assert created.value.status == 201
        created_id = created.value.json()["id"]
        assert page.evaluate("location.pathname") == pathname
        page.locator('.cal-day[data-date="2026-10-23"].has-cleaning').wait_for(state="visible")
        page.locator('.cal-day[data-date="2026-10-23"] .cal-day-number').click(position={"x": 12, "y": 10})  # 0956: stay bars sit under the day number, so click the number band
        marker = page.locator(f'[data-cal-day-list] .cal-event[data-cal-event="cleaning:{created_id}"]')
        marker.wait_for(state="visible")
        marker.click()
        page.locator("[data-cal-details]").wait_for(state="visible")
        assert page.locator("[data-cal-details] [data-cal-open]").get_attribute("href") == f"#cleaning-{created_id}"
        page.locator("[data-cal-details] [data-cal-close]").click()
        if page.locator("[data-cal-day-dialog][open]").count():
            page.locator("[data-cal-day-dialog] [data-cal-close]").click()
        # A move is a date change on the edit page now; the bookings must stay where they are.
        page.goto(f"{origin}/cleaning/events/{created_id}/edit?lang=en")
        page.fill("#clean-date", "2026-10-25")
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  f"/cleaning/events/{created_id}" in response.url) as saved:
            page.get_by_role("button", name="Save", exact=True).click()
        assert saved.value.status < 400
        moved = db.query_one("SELECT scheduled_date FROM cleaning_event WHERE id = ?", (created_id,))
        assert str(moved["scheduled_date"])[:10] == "2026-10-25"
        page.goto(f"{origin}/cleaning?lang=en&cal_date=2026-10-25")
        loaded(page)
        page.locator('.cal-day[data-date="2026-10-25"].has-cleaning').wait_for(state="visible")
        page.goto(f"{origin}/cleaning/events/{created_id}/edit?lang=en")
        page.locator(".cleaning-remove summary").click()
        page.get_by_role("button", name="Remove cleaning", exact=True).click()
        page.locator("#confirm-dialog [data-confirm-proceed]").click()
        page.wait_for_url(lambda url: f"/cleaning/events/{created_id}" not in url, timeout=10000)
        loaded(page)
        scheduled = cleaning.schedule(ws["owner"], cleaning.today() - timedelta(days=30), cleaning.today() + timedelta(days=30))["cleanings"]
        assert all(item["eventId"] != created_id for item in scheduled)
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
        # October view, so the tile tag for the created cleaning is on screen.
        page.goto(f"{origin}/cleaning?lang=cs&cal_date=2026-10-27")
        loaded(page)
        pathname = page.evaluate("location.pathname")

        page.locator('[data-calendar-add][data-cal-create-type="cleaning"]').click()
        dialog = page.locator("[data-cal-create]")
        assert dialog.is_visible()
        assert page.locator('[data-cal-type-choice="cleaning"]').get_attribute("aria-pressed") == "true"
        clean_date = page.locator("#cal-clean-date").input_value()
        page.locator('[data-cal-type-choice="stay"]').click()
        assert page.locator("#cal-arrival").input_value() == clean_date
        shot(page, "cleaning-stay-popup-cs")
        page.locator('[data-cal-type-choice="cleaning"]').click()
        assert page.locator("#cal-clean-date").input_value() == clean_date
        page.locator("[data-cal-create] .cal-close").click()

        page.locator('[data-calendar-add][data-cal-create-type="cleaning"]').click()
        dialog = page.locator("[data-cal-create]")
        page.locator("#cal-property").select_option(str(ws["home"]))
        page.locator("#cal-clean-date").fill("2026-10-27")
        page.locator("#cal-clean-notes").fill("Popup cleaning note")
        shot(page, "cleaning-create-popup-cs")
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  response.url.split("?")[0].endswith("/cleaning/events")) as result:
            page.locator("[data-cal-save]").click()
        response = result.value
        assert response.status == 201
        created = response.json()
        assert page.evaluate("location.pathname") == pathname
        page.locator('.cal-day[data-date="2026-10-27"].has-cleaning').wait_for(state="visible")
        page.locator('.cal-day[data-date="2026-10-27"] .cal-day-number').click()
        sheet_marker = page.locator(f'[data-cal-day-list] .cal-event[data-cal-event="cleaning:{created["id"]}"]')
        sheet_marker.wait_for(state="visible")
        page.locator("[data-cal-day-dialog] [data-cal-close]").click()
        shot(page, "cleaning-create-result-cs")

        page.locator('[data-calendar-add][data-cal-create-type="cleaning"]').click()
        page.locator("#cal-clean-date").fill("2026-10-27")
        before_invalid_save = db.query_one("SELECT COUNT(*) AS n FROM cleaning_event")["n"]
        notes = page.locator("#cal-clean-notes")
        notes.evaluate("(field) => field.removeAttribute('maxlength')")
        notes.fill("x" * 5001)
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  response.url.split("?")[0].endswith("/cleaning/events")) as failure:
            page.locator("[data-cal-form]").evaluate("(form) => form.requestSubmit()")
        assert failure.value.status == 422
        expected = cleaning_i18n.translator("cs")("notes_error")
        error = page.locator('[data-cal-error-for="notes"]')
        page.wait_for_function("""expected => document.querySelector('[data-cal-error-for="notes"]')?.textContent === expected""", arg=expected)
        assert error.is_visible() and error.inner_text() == expected
        assert db.query_one("SELECT COUNT(*) AS n FROM cleaning_event")["n"] == before_invalid_save
        assert page.locator("[data-cal-create]").is_visible()
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
        browser, context = browser_context(playwright, ws, origin, width=1280)
        page = context.new_page()
        # 0834: the tile tag and day sheet replace the week-view marker; the marker keeps its full-day label.
        page.goto(f"{origin}/cleaning?lang=en&cal_date=2026-10-26")
        loaded(page)
        tag_day = page.locator('.cal-day[data-date="2026-10-26"].has-cleaning')
        tag_day.wait_for(state="visible")
        assert tag_day.locator(".cal-clean-tag").count() >= 1
        tag_day.locator(".cal-day-number").click()
        marker = page.locator(f'[data-cal-day-list] .cal-event.is-cleaning-marker[data-cal-event="cleaning:{event_id}"]')
        marker.wait_for(state="visible")
        details = marker.get_attribute("aria-label") or ""
        assert "Cleaning" in details and property_name in details
        marker.click()
        assert page.locator("[data-cal-details] .cleaning-warning").count() >= 1
        shot(page, "cleaning-marker-unset-hours-mobile")
        context.close()
        browser.close()


def test_cleaning_calendar_can_create_stay_and_refresh_turnover_in_place(workspace, origin):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width=1280)
        page = context.new_page()
        # 0834: the /cleaning tiles show cleaning tags only, so the stay itself is checked in the database
        # and the turnover is checked on its day tag and day sheet.
        page.goto(f"{origin}/cleaning?lang=en&cal_date=2026-10-26")
        loaded(page)
        pathname = page.evaluate("location.pathname")
        page.locator('[data-calendar-add][data-cal-create-type="cleaning"]').click()
        page.locator('[data-cal-type-choice="stay"]').click()
        form = page.locator("[data-cal-form]")
        assert page.locator('[data-cal-type-choice="stay"]').get_attribute("aria-pressed") == "true"
        form.locator("#cal-property").select_option(str(ws["homes"][1]))
        form.locator("#cal-arrival").fill("2026-10-26")
        form.locator("#cal-departure").fill("2026-10-28")
        form.locator("#cal-label").fill("Cleaning page booking")
        shot(page, "cleaning-page-stay-popup-en")
        assert form.locator('[name="start_time"], [name="end_time"], [name*="code"]').count() == 0
        with page.expect_response(lambda response: response.request.method == "POST" and
                                  response.url.split("?")[0].endswith("/reservations")) as result:
            page.locator("[data-cal-save]").click()
        saved = result.value.json()
        assert result.value.status == 201 and page.evaluate("location.pathname") == pathname
        # The turnover is reconciled by the refresh after save, so wait for its tag before reading it.
        turnover_day = page.locator('.cal-day[data-date="2026-10-28"].has-cleaning')
        turnover_day.wait_for(state="visible")
        turnover = db.query_one("SELECT id, scheduled_date FROM cleaning_event WHERE source_reservation_id = ?", (saved["id"],))
        assert turnover and turnover["scheduled_date"] == "2026-10-28"
        apartment_name = db.query_one("SELECT internal_name FROM apartment WHERE id = ?", (ws["homes"][1],))["internal_name"]
        turnover_day.locator(".cal-day-number").click()
        card = page.locator(f'[data-cal-day-list] .cal-event[data-cal-event="cleaning:{turnover["id"]}"]')
        card.wait_for(state="visible")
        assert apartment_name in card.inner_text()
        page.locator("[data-cal-day-dialog] [data-cal-close]").click()
        shot(page, "cleaning-calendar-created-stay-turnover")
        context.close()
        browser.close()


CREATE_CENTRE_JS = """() => {
  const r = document.querySelector('[data-cal-create]').getBoundingClientRect();
  return { cx: r.left + r.width / 2, cy: r.top + r.height / 2, top: r.top,
           vx: document.documentElement.clientWidth / 2, vy: document.documentElement.clientHeight / 2 };
}"""


def _open_create_dialog(page, kind):
    if kind == "stay":
        # The header has no "add stay" button; stay opens from the cleaning dialog's type switch.
        _open_create_dialog(page, "cleaning")
        page.locator('[data-cal-type-choice="stay"]').click()
        return
    controls = page.locator(f'[data-calendar-add][data-cal-create-type="{kind}"]')
    for index in range(controls.count()):
        if controls.nth(index).is_visible():
            controls.nth(index).click()
            break
    else:
        # The secondary "Add stay" action is hidden in the phone action bar; its handler still opens the dialog.
        controls.first.dispatch_event("click")
    page.wait_for_selector("[data-cal-create][open]")


def _assert_dialog_centred(page, label):
    settle_motion(page)
    box = page.evaluate(CREATE_CENTRE_JS)
    assert abs(box["cx"] - box["vx"]) <= 8 and abs(box["cy"] - box["vy"]) <= 8, (label, box)
    return box


@pytest.mark.parametrize(("width", "height"), [(1280, 800), (768, 844)])
def test_add_stay_and_cleaning_dialogs_open_centred_in_both_tabs(workspace, origin, width, height):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width=width)
        try:
            page = context.new_page()
            page.set_viewport_size({"width": width, "height": height})
            page.goto(f"{origin}/cleaning?lang=en")
            loaded(page)
            for scrolled in (False, True):
                page.evaluate("y => window.scrollTo(0, y)", 600 if scrolled else 0)
                for kind, other in (("stay", "cleaning"), ("cleaning", "stay")):
                    _open_create_dialog(page, kind)
                    first = _assert_dialog_centred(page, f"{kind} scrolled={scrolled}")
                    shot(page, f"add-{kind}-{width}{'-scrolled' if scrolled else ''}")
                    page.locator(f'[data-cal-type-choice="{other}"]').click()
                    second = _assert_dialog_centred(page, f"{other} tab scrolled={scrolled}")
                    assert abs(first["cy"] - first["vy"]) <= 8 and abs(second["cy"] - second["vy"]) <= 8, (first, second)
                    page.locator("[data-cal-create] .cal-close").click()
                    page.wait_for_function("() => !document.querySelector('[data-cal-create]').open")
        finally:
            browser.close()


def test_cleaning_chip_label_starts_with_cleaning(workspace, origin):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width=1280)
        try:
            page = context.new_page()
            page.goto(f"{origin}/cleaning?lang=en")
            loaded(page)
            # 0834: tile chips show the start time, so the "Cleaning" label is
            # checked in the day sheet, where each cleaning marker carries it.
            page.locator(".cal-day.has-cleaning .cal-day-number").first.click(position={"x": 12, "y": 10})  # 0956: stay bars sit under the day number, so click the number band
            labels = page.locator("[data-cal-day-dialog] .cal-day-list .cal-cleaning-label")
            assert labels.count() > 0
            for index in range(labels.count()):
                text = labels.nth(index).inner_text().strip()
                assert text.startswith("Cleaning"), text
            shot(page, "calendar-1280-chips")
        finally:
            browser.close()


@pytest.mark.parametrize("width", [1280, 768])
def test_cleaning_form_pages_fit_the_viewport_and_take_screenshots(workspace, origin, width):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width=width)
        try:
            page = context.new_page()
            page.set_viewport_size({"width": width, "height": 844 if width == 768 else 800})
            page.goto(f"{origin}/cleaning?lang=en")
            loaded(page)
            shot(page, f"calendar-{width}")
            event_link = page.locator("a[href*='/cleaning/events/']").first.get_attribute("href")
            pages = {
                f"instructions-{width}": f"{origin}/cleaning/properties/{ws['home']}?lang=en",
                f"share-{width}": f"{origin}/cleaning/shares?lang=en",
                f"edit-{width}": f"{origin}{event_link}" if event_link else f"{origin}/cleaning/new?lang=en",
            }
            for name, url in pages.items():
                page.goto(url)
                page.wait_for_selector(".cleaning-form")
                assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), name
                shot(page, name)
        finally:
            browser.close()


def _save_cleaning_shot(page, name):
    """0815 screenshots: written only when UBYHOST_TASK_SHOTS=1."""
    if os.environ.get("UBYHOST_TASK_SHOTS") == "1":
        page.screenshot(path=str(Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0814" / name))


@pytest.mark.parametrize("width", [390, 320])
def test_phone_cleaning_calendar_tags_only(workspace, origin, width):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width)
        page = context.new_page()
        page.goto(origin + "/cleaning?lang=en")
        loaded(page)
        assert page.locator("#cleaning-list").is_hidden()
        assert page.locator(".cleaning-legend").is_hidden()
        assert page.locator(".cal-week-events").count() == 0
        assert page.locator(".cal-day.has-stays").count() == 0
        tagged = page.locator(".cal-day.has-cleaning")
        assert tagged.count() >= 1
        assert tagged.first.locator(".cal-clean-tag svg").count() >= 1
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        page.evaluate("scrollTo(0, 0)")
        _save_cleaning_shot(page, "cleaning-390.png") if width == 390 else None
        tagged.first.locator(".cal-day-number").click()
        assert page.locator("[data-cal-day-dialog][open]").is_visible()
        assert page.locator("[data-cal-day-list] .cal-event").count() >= 1
        assert page.locator("[data-cal-day-list] .cal-event.is-cleaning-marker").count() >= 1  # 0896: stays are listed too
        page.locator("[data-cal-day-add]").click()
        assert page.locator("[data-cal-create]").is_visible()
        assert page.locator('[data-cal-type-choice="cleaning"]').get_attribute("aria-pressed") == "true"
        context.close()
        browser.close()


@pytest.mark.parametrize("width", [768, 1280])
def test_desktop_cleaning_calendar_tags_and_side_panel(workspace, origin, width):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang=en&cal_view=calendar&cal_property={ws['home']}")
        loaded(page)
        assert page.locator("#cleaning-list").is_hidden()
        assert page.locator(".cal-week-events").count() == 0
        tagged = page.locator(".cal-day.has-cleaning")
        assert tagged.count() >= 1
        assert tagged.first.locator(".cal-tile-chip.cal-clean-chip").is_visible()
        _save_cleaning_shot(page, f"cleaning-{width}.png")
        tagged.first.locator(".cal-day-number").click()
        assert page.locator("[data-cal-day-dialog][open]").is_visible()
        assert page.locator("[data-cal-day-list] .cal-event").count() >= 1
        assert page.locator("[data-calendar]").evaluate("element => element.classList.contains('has-panel')")
        context.close()
        browser.close()


def _touch_context(playwright, ws, origin, width, height=844):
    browser = playwright.chromium.launch(**chromium_launch_kwargs())
    context = browser.new_context(viewport={"width": width, "height": height}, has_touch=True, is_mobile=True)
    context.add_cookies([{"name": auth.SESSION_COOKIE, "value": ws["client"].cookies.get(auth.SESSION_COOKIE),
                         "url": origin + "/"}])
    return browser, context


@pytest.mark.parametrize("width", [768, 1280])
def test_0835_cleaning_header_has_no_long_text(workspace, origin, width):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang=en&cal_view=calendar&cal_property={ws['home']}")
        loaded(page)
        long_texts = page.evaluate("""() => {
          const roots = [...document.querySelectorAll('.cleaning-page header, .cleaning-head, .cleaning-page .cal-heading, .cleaning-page .cal-toolbar')];
          const out = [];
          for (const root of roots) for (const el of [root, ...root.querySelectorAll('*')]) {
            const text = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
            if (text.length > 90) out.push(text.slice(0, 120));
          }
          return out; }""")
        assert long_texts == []
        context.close()
        browser.close()


def test_0835_cleaning_range_shot_390_long_press(workspace, origin):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = _touch_context(playwright, ws, origin, 390)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang=en&cal_view=calendar&cal_property={ws['home']}&cal_date=2026-10-01")
        loaded(page)
        cdp = context.new_cdp_session(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_function("scrollY === 0")
        box_a = page.locator('.cal-day[data-date="2026-10-03"]').bounding_box()
        box_b = page.locator('.cal-day[data-date="2026-10-05"]').bounding_box()
        x, y = box_a["x"] + box_a["width"] / 2, box_a["y"] + box_a["height"] / 2
        tx, ty = box_b["x"] + box_b["width"] / 2, box_b["y"] + box_b["height"] / 2
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        page.wait_for_timeout(400)
        for step in (1, 2, 3):
            point = {"x": x + (tx - x) * step / 3, "y": y + (ty - y) * step / 3}
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [point]})
            page.wait_for_timeout(50)
        selected = page.eval_on_selector_all(".cal-day.is-selected", "els => els.map(e => e.dataset.date)")
        assert selected == ["2026-10-03", "2026-10-04", "2026-10-05"], selected
        _save_cleaning_shot(page, "cleaning-range-390.png")
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        context.close()
        browser.close()


def test_0835_cleaning_range_shot_1280_mouse_drag(workspace, origin):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, 1280)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang=en&cal_view=calendar&cal_property={ws['home']}&cal_date=2026-10-01")
        loaded(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_function("scrollY === 0")
        page.locator('.cal-day[data-date="2026-10-12"]').scroll_into_view_if_needed()
        page.wait_for_timeout(300)  # the calendar settles its scroll after load
        box_a = page.locator('.cal-day[data-date="2026-10-12"]').bounding_box()
        box_b = page.locator('.cal-day[data-date="2026-10-14"]').bounding_box()
        page.mouse.move(box_a["x"] + box_a["width"] / 2, box_a["y"] + box_a["height"] / 2)
        page.mouse.down()
        page.mouse.move(box_b["x"] + box_b["width"] / 2, box_b["y"] + box_b["height"] / 2, steps=8)
        page.wait_for_timeout(150)
        selected = page.eval_on_selector_all(".cal-day.is-selected", "els => els.map(e => e.dataset.date)")
        assert selected == ["2026-10-12", "2026-10-13", "2026-10-14"], selected
        _save_cleaning_shot(page, "cleaning-range-1280.png")
        page.mouse.up()
        context.close()
        browser.close()


ROW1_0842 = ["h3[data-cal-period]", "[data-cal-prev]", "[data-cal-today]", "[data-cal-next]"]  # 0955: title, Today and arrows
ROW2_0842 = ["[data-cal-property]", "[data-cal-settings]", "[data-cal-scales]"]  # 0956: no view toggle while a property is picked
FITS = "document.documentElement.scrollWidth <= window.innerWidth"


def test_0842_cleaning_toolbar_stable_two_rows_at_1280(workspace, origin):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, 1280)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang=en&cal_view=calendar&cal_property={ws['home']}")
        loaded(page)
        row1 = [page.locator(".cleaning-page " + sel).first.bounding_box() for sel in ROW1_0842]
        row2 = [page.locator(".cleaning-page " + sel).first.bounding_box() for sel in ROW2_0842]
        boxes = row1 + row2
        assert all(boxes), list(zip(ROW1_0842 + ROW2_0842, boxes))
        for row in (row1, row2):
            assert max(b["y"] for b in row) < min(b["y"] + b["height"] for b in row), row
        assert max(b["y"] + b["height"] for b in row1) <= min(b["y"] for b in row2), (row1, row2)
        assert row1[0]["x"] + row1[0]["width"] <= min(b["x"] for b in row1[1:]), row1  # title left, Today and arrows right
        assert row2[2]["x"] >= row2[1]["x"] + row2[1]["width"], row2  # scale segment right of settings
        for row in (row1, row2):
            ordered = sorted(row, key=lambda b: b["x"])
            gaps = [round(b["x"] - (a["x"] + a["width"])) for a, b in zip(ordered, ordered[1:])]
            assert min(gaps) >= 11, gaps
        for sel, b in zip(ROW1_0842[1:] + ROW2_0842, row1[1:] + row2):
            assert abs(b["height"] - 40) <= 1, (sel, b)
        title = page.locator(".cleaning-page h3[data-cal-period]").evaluate(
            "e => [getComputedStyle(e).fontSize, getComputedStyle(e).fontWeight]")
        assert title == ["32px", "700"], title  # 0891: Airbnb title size at 1024 px+
        assert page.get_by_role("button", name="Gantt", exact=True).count() == 0  # 0956: one property, no Gantt
        body = page.locator(".cleaning-page [data-cal-body]").bounding_box()
        assert body["y"] >= max(b["y"] + b["height"] for b in boxes), body
        head = [page.locator(f'.cleaning-head a[href="{href}"]').bounding_box()
                for href in ("/cleaning/new", "/cleaning/properties", "/cleaning/shares")]
        assert all(abs(b["height"] - 40) <= 1 for b in head), head
        assert round(head[1]["x"] - head[0]["x"] - head[0]["width"]) >= 11, head
        assert page.evaluate(FITS)
        context.close()
        browser.close()


@pytest.mark.parametrize("width", [390, 320])
def test_0842_phone_cleaning_header(workspace, origin, width):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang=en&cal_view=calendar&cal_property={ws['home']}")
        loaded(page)
        select = page.locator(".cleaning-page [data-cal-property]").bounding_box()
        title = page.locator(".cleaning-page h3[data-cal-period]").bounding_box()
        prev = page.locator(".cleaning-page [data-cal-prev]").bounding_box()
        nxt = page.locator(".cleaning-page [data-cal-next]").bounding_box()
        assert abs(select["height"] - 48) <= 1, select
        assert select["y"] + select["height"] <= title["y"], (select, title)
        for b in (prev, nxt):
            assert b["y"] < title["y"] + title["height"] and title["y"] < b["y"] + b["height"], (title, b)
        assert abs(title["x"] - select["x"]) <= 2, (title, select)
        assert title["x"] + title["width"] <= prev["x"], (title, prev)
        assert page.evaluate(FITS)
        context.close()
        browser.close()


@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1280, 1440])
def test_0842_cleaning_no_horizontal_overflow(workspace, origin, width):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang=cs&cal_view=calendar&cal_property={ws['home']}")
        loaded(page)
        assert page.evaluate(FITS), (width, "month")
        if width >= 768:
            page.locator('.cleaning-page [data-cal-scale="week"]').click()
            page.wait_for_function("() => document.querySelector('[data-cal-body]')?.getAttribute('aria-busy') === 'false'")
            assert page.evaluate(FITS), (width, "week")
        context.close()
        browser.close()


# 0891: the host cleaning page uses the Airbnb month scroll with amber cleaning tags and no stay pills.
SHOTS_0891 = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0891"
ROWS_0891 = """() => [...document.querySelectorAll('.cal-month .cal-week.is-dots')].map(row => ({
    s: [...document.querySelectorAll('.cal-month')].indexOf(row.closest('.cal-month')),
    t: [...row.querySelectorAll('.cal-day[data-date]')].map(tile => { const r = tile.getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; })
})).filter(row => row.t.length)"""


@pytest.mark.parametrize("width", [390, 768, 1280])
def test_0891_cleaning_airbnb_month(workspace, origin, width):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width)
        page = context.new_page()
        page.goto(f"{origin}/cleaning?lang=en&cal_view=calendar&cal_property={ws['home']}")
        loaded(page)
        page.wait_for_selector(".cal-month")
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        assert page.locator(".cal-month").count() == 6
        assert page.locator(".cal-pill").count() >= 1  # 0896: stay pills show their end dates
        assert page.locator(".cal-day.has-cleaning").count() >= 1
        gap = 12 if width >= 768 else 4
        rows = page.evaluate(ROWS_0891)
        assert rows
        for row in rows:
            for a, b in zip(row["t"], row["t"][1:]):
                assert abs(b[0] - a[1] - gap) <= 1, (width, a, b)
        if width >= 768:
            chip = page.locator(".cal-day.has-cleaning .cal-tile-chip.cal-clean-chip").first
            assert chip.is_visible()
            assert chip.evaluate("node => getComputedStyle(node).borderTopLeftRadius") == "12px"
        else:
            assert page.locator(".cal-day.has-cleaning .cal-clean-tag").first.is_visible()
        assert page.evaluate(FITS)
        if os.environ.get("UBYHOST_TASK_SHOTS") == "1":
            SHOTS_0891.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS_0891 / f"cleaning-{width}.png"), full_page=False)
        context.close()
        browser.close()


# ---- 0971: one success pattern, independent cleaning save forms ----

_NOTICE_FIXTURE = """
document.addEventListener('readystatechange', () => {
  if (document.readyState !== 'interactive') return;
  const main = document.querySelector('main') || document.body;
  const long = 'Averyveryveryveryverylongunbrokensuccesstext'.repeat(6);
  main.insertAdjacentHTML('afterbegin',
    '<div id="fx-section" class="banner ok section-notice" role="status" tabindex="-1" data-section-notice><span class="grow">' + long + '</span></div>' +
    '<p id="fx-cleaning" class="cleaning-notice" role="status">Saved.</p>');
  const rail = document.querySelector('[data-feedback-rail]');
  if (rail) rail.insertAdjacentHTML('beforeend',
    '<div id="fx-toast" class="toast" data-toast data-toast-kind="success"><span class="grow">Saved.</span>' +
    '<button type="button" data-toast-close aria-label="Dismiss">\\u00d7</button></div>');
  const src = document.createElement('input');
  src.id = 'fx-copy-source'; src.className = 'sr-only'; src.value = 'synthetic-link'; src.readOnly = true;
  const btn = document.createElement('button');
  btn.id = 'fx-copy'; btn.type = 'button'; btn.className = 'btn small'; btn.dataset.copy = 'fx-copy-source';
  btn.dataset.copyLabel = 'Copy link'; btn.dataset.copiedLabel = document.documentElement.lang === 'cs' ? 'Zkopírováno' : 'Copied';
  btn.textContent = 'Copy link';
  main.append(src, btn);
});
"""


def _saved_state(ws):
    prop = cleaning.properties(ws["owner"], [ws["home"]])[0]
    return prop["cleaning_instructions"], cleaning._code(prop)["value"]


@pytest.mark.parametrize("width", [390, 768, 1280])
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_0971_each_cleaning_save_commits_only_its_own_form(workspace, origin, width, lang):
    ws = workspace
    url = f"{origin}/cleaning/properties/{ws['home']}?lang={lang}"
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width=width)
        try:
            page = context.new_page()
            page.goto(url)
            page.wait_for_selector("form[aria-label]")
            forms = page.locator("form.cleaning-panel[aria-label]")
            assert forms.count() == 2
            geometry = page.evaluate("""() => {
              const [a, b] = Array.from(document.querySelectorAll('form.cleaning-panel[aria-label]'));
              const ba = a.querySelector('button[type=submit]'), bb = b.querySelector('button[type=submit]');
              const ra = ba.getBoundingClientRect(), rb = bb.getBoundingClientRect();
              return { nested: a.contains(b) || b.contains(a), submits: [a.querySelectorAll('button[type=submit]').length, b.querySelectorAll('button[type=submit]').length],
                sameClass: ba.className === bb.className, sameHeight: Math.abs(ra.height - rb.height) < 1,
                boxed: [a, b].map((f) => getComputedStyle(f).borderTopWidth !== '0px' || getComputedStyle(f).boxShadow !== 'none'),
                overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
                actions: [a.getAttribute('action'), b.getAttribute('action')] };
            }""")
            assert not geometry["nested"] and geometry["submits"] == [1, 1], geometry
            assert geometry["sameClass"] and geometry["sameHeight"], geometry
            assert geometry["boxed"] == [True, True] and not geometry["overflow"], geometry
            shot(page, f"0971-settings-{lang}-{width}")
            before_text, before_code = _saved_state(ws)
            # Save instructions with an unsaved manual code typed in the other form.
            page.fill("#property-instructions", "0971 instructions only")
            page.fill("#manual-code", "UNSAVED-1")
            page.locator("form[aria-label] button[type=submit]").first.click()
            page.wait_for_url("**notice=saved**")
            text, code = _saved_state(ws)
            assert text == "0971 instructions only" and code == before_code, (text, code, before_code)
            # Save the manual code with an unsaved instruction edit typed in the other form.
            page.fill("#property-instructions", "UNSAVED instructions")
            page.fill("#manual-code", "7710")
            page.locator("form[aria-label] button[type=submit]").nth(1).click()
            page.wait_for_url("**notice=saved**")
            text, code = _saved_state(ws)
            assert text == "0971 instructions only" and code == "7710", (text, code)
            assert page.locator("[data-success-notice]").count() == 1
            assert page.locator("[data-success-notice] [role=button], [data-success-notice] button").count() == 1
        finally:
            browser.close()


@pytest.mark.parametrize("width", [390, 768, 1280])
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_0971_success_notices_share_one_pattern_and_dismiss(workspace, origin, width, lang):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width=width)
        try:
            context.add_init_script(_NOTICE_FIXTURE)
            page = context.new_page()
            page.goto(f"{origin}/cleaning/properties/{ws['home']}?lang={lang}&notice=saved")
            page.wait_for_selector("[data-success-notice]")
            page.wait_for_selector("#fx-section [data-success-dismiss]", state="attached")
            page.wait_for_selector("#fx-cleaning [data-success-dismiss]", state="attached")
            look = page.evaluate("""() => {
              const pick = (el) => { const s = getComputedStyle(el); const r = el.getBoundingClientRect();
                const b = el.querySelector('[data-success-dismiss]').getBoundingClientRect();
                return { border: s.borderLeftWidth + s.borderLeftColor, radius: s.borderTopLeftRadius, bg: s.backgroundColor, size: s.fontSize,
                  mark: getComputedStyle(el, '::before').content, inside: r.left >= 0 && r.right <= innerWidth + 0.5 && b.right <= r.right + 0.5 && b.left >= r.left,
                  close: [Math.round(b.width), Math.round(b.height)] }; };
              return { macro: pick(document.querySelector('[data-success-notice]')), section: pick(document.querySelector('#fx-section')),
                cleaning: pick(document.querySelector('#fx-cleaning')),
                toast: (() => { const i = document.querySelector('#fx-toast .feedback-card-icon'); return i ? [i.textContent, Math.round(i.getBoundingClientRect().width)] : null; })(),
                overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
                live: document.querySelectorAll('[data-feedback-live]').length };
            }""")
            for key in ("section", "cleaning"):
                for field in ("border", "radius", "bg", "size", "mark"):
                    assert look[key][field] == look["macro"][field], (key, field, look)
            for key in ("macro", "section", "cleaning"):
                assert look[key]["inside"] and look[key]["close"] == [44, 44], (key, look)
            assert look["toast"] == ["✓", 24], look
            assert not look["overflow"] and look["live"] == 1, look
            assert page.locator("[role=status][data-success-notice]").count() == 1
            shot(page, f"0971-notices-{lang}-{width}")
            # Pointer dismiss.
            page.locator("#fx-section [data-success-dismiss]").click()
            assert page.locator("#fx-section").count() == 0
            # Keyboard dismiss: Tab to the macro notice's button, press Enter; focus lands on a heading.
            page.locator("[data-success-notice] [data-success-dismiss]").focus()
            page.keyboard.press("Enter")
            assert page.locator("[data-success-notice]").count() == 0
            assert page.evaluate("document.activeElement && /^H[12]$/.test(document.activeElement.tagName)")
            page.locator("#fx-cleaning [data-success-dismiss]").focus()
            page.keyboard.press("Space")
            assert page.locator("#fx-cleaning").count() == 0
        finally:
            browser.close()


@pytest.mark.parametrize("width", [390, 768, 1280])
@pytest.mark.parametrize("lang", ["en", "cs"])
def test_0971_copy_link_keeps_size_and_label_and_does_not_stack(workspace, origin, width, lang):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width=width)
        try:
            context.add_init_script("""Object.defineProperty(navigator, 'clipboard', { configurable: true,
              value: { writeText: () => Promise.resolve() } });""" + _NOTICE_FIXTURE)
            page = context.new_page()
            page.goto(f"{origin}/cleaning/properties/{ws['home']}?lang={lang}")
            page.wait_for_selector("#fx-copy")
            button = page.locator("#fx-copy")
            before = button.bounding_box()
            copied = "Zkopírováno" if lang == "cs" else "Copied"
            for _ in range(3):
                button.click()
                page.wait_for_function("(c) => document.querySelector('#fx-copy').getAttribute('aria-label') === c", arg=copied)
            after = button.bounding_box()
            assert after["width"] == pytest.approx(before["width"], abs=0.5)
            assert after["height"] == pytest.approx(before["height"], abs=0.5)
            state = page.evaluate("""() => ({ icons: document.querySelectorAll('[data-copy-state-icon]').length,
              toasts: document.querySelectorAll('[data-feedback-rail] [data-toast]:not(#fx-toast)').length,
              live: document.querySelector('[data-feedback-live]').textContent,
              visible: Array.from(document.querySelectorAll('#fx-copy .copy-label-default, #fx-copy .copy-label-confirmed')).map(
                (n) => getComputedStyle(n).visibility + ':' + n.textContent.trim()) })""")
            assert state["icons"] == 0 and state["toasts"] == 0, state
            page.wait_for_timeout(100)
            assert page.evaluate("document.querySelector('[data-feedback-live]').textContent") == copied
            assert any(item == f"visible:{copied}" for item in state["visible"]), state
            shot(page, f"0971-copy-{lang}-{width}")
            page.wait_for_function("() => !document.querySelector('#fx-copy').classList.contains('is-copy-confirmed')", timeout=4000)
            assert "Copy link" in button.inner_text()
        finally:
            browser.close()


@pytest.mark.parametrize("width", [390, 1280])
def test_0971_cleaning_list_notice_is_one_dismissible_success_notice(workspace, origin, width):
    ws = workspace
    with sync_api.sync_playwright() as playwright:
        browser, context = browser_context(playwright, ws, origin, width=width)
        try:
            page = context.new_page()
            page.goto(f"{origin}/cleaning?lang=en&notice=saved")
            page.wait_for_selector("p.cleaning-notice [data-success-dismiss]")
            assert page.locator("p.cleaning-notice").count() == 1
            assert page.locator("p.cleaning-notice [data-success-dismiss]").count() == 1
            assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
            shot(page, f"0971-list-notice-{width}")
            page.locator("p.cleaning-notice [data-success-dismiss]").click()
            assert page.locator("p.cleaning-notice").count() == 0
        finally:
            browser.close()
