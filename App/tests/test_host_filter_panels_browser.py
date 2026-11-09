"""Real-browser coverage for host filter disclosure, date controls and layout."""
from __future__ import annotations

import os
import secrets
import socket
import threading
import time
from pathlib import Path

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.browser_support import chromium_launch_kwargs, settle_motion
from tests.conftest import login_as, mark_security_prompt_seen


@pytest.fixture(scope="module")
def host():
    db.init_db()
    username = f"filters-{secrets.token_hex(4)}"
    owner = mark_security_prompt_seen(auth.create_account(
        f"{username}@example.test", "Filter Test", role="host", username=username
    ))
    entity = db.insert("legal_entity", {
        "name": "Filter Test s.r.o.", "owner_user_id": owner, "created_at": db.utcnow(),
    })
    apartment_ids = []
    for suffix in ("One", "Two"):
        apartment_ids.append(db.insert("apartment", {
            "internal_name": f"Filter Property {suffix}",
            "owner_user_id": owner,
            "legal_entity_id": entity,
            "permalink_token": f"filter{suffix.lower()}{secrets.token_hex(3)}",
            "active": 1,
            "stay_fee_rate_czk": 50,
            "stay_fee_cadence": "monthly",
            "stay_fee_vs": "123456",
            "stay_fee_authority_name": "Test City Office",
            "stay_fee_council_account": "19-2000781379/0800",
            "stay_fee_council_iban": "CZ3008000000192000781379",
            "created_at": db.utcnow(),
        }))
    now = db.utcnow()
    reservation_ids = []
    for suffix, start, end, status, archived_at in (
        ("past", "2020-01-10", "2020-01-12", "active", None),
        ("future", "2099-04-10", "2099-04-13", "active", None),
        ("archived", "2026-03-10", "2026-03-12", "cancelled", now),
    ):
        apartment_id = apartment_ids[1] if suffix == "archived" else apartment_ids[0]
        reservation_ids.append(db.insert("reservation", {
            "apartment_id": apartment_id, "source": "manual",
            "uid": f"filter-{suffix}-{secrets.token_hex(4)}",
            "date_from": start, "date_to": end, "summary": f"Filter {suffix} stay",
            "status": status, "archived_at": archived_at, "created_at": now, "updated_at": now,
        }))
    guest_id = db.insert("guest", {
        "reservation_id": reservation_ids[1], "surname": "Filter Guest",
        "first_name": "Sample", "birth_date": "1990-02-03", "nationality": "CZE",
        "doc_number": "TEST-123", "purpose": "10", "created_at": now,
        "updated_at": now,
    })
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner, "entity": entity,
           "apartments": apartment_ids, "reservations": reservation_ids,
           "guest": guest_id, "username": username}
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM reservation WHERE apartment_id IN (?, ?)", apartment_ids)
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner,))


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def base(host):
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("the filter browser server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def _capture(page, name):
    if os.environ.get("UBYHOST_CAPTURE_FILTERS") == "1":
        configured = os.environ.get("UBYHOST_FILTERS_DIR")
        shots = os.environ.get("UBYHOST_SHOTS_DIR")
        if configured:
            target = Path(configured)
        elif shots:
            target = Path(shots) / "filters"
        else:
            target = Path("/workspace/generated_images/host-design-application/filters")
        target.mkdir(parents=True, exist_ok=True)
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(target / f"{name}.png"), full_page=True)


def _browser_context(playwright, host, base, *, width=1280, javascript=True):
    browser = playwright.chromium.launch(**chromium_launch_kwargs())
    context = browser.new_context(
        viewport={"width": width, "height": 1000},
        java_script_enabled=javascript,
        has_touch=width <= 600,
    )
    context.add_cookies([{
        "name": auth.SESSION_COOKIE,
        "value": host["client"].cookies.get(auth.SESSION_COOKIE),
        "url": base + "/",
    }])
    return browser, context, context.new_page()


def test_default_stays_are_unbounded_and_native_get_filters_work_without_javascript(host, base):
    response = host["client"].get("/reservations?range=all&lang=en")  # 0285: the default is now Upcoming & current
    assert response.status_code == 200, response.text
    assert "10.01.2020" in response.text
    assert "10.04.2099" in response.text
    assert "All properties" in response.text
    assert "Active" in response.text
    assert 'name="from"' in response.text and 'name="to"' in response.text

    with sync_api.sync_playwright() as playwright:
        browser, _context, page = _browser_context(
            playwright, host, base, javascript=False
        )
        page.goto(base + "/reservations?range=all&lang=en")
        panel = page.locator("#stays-filter-panel")
        assert panel.is_visible()
        page.locator("#stays-from").fill("2020-01-01")
        page.locator("#stays-until").fill("2020-01-31")
        with page.expect_navigation():
            panel.locator('button[type="submit"]').click()
        assert "range=custom" in page.url
        assert "from=2020-01-01" in page.url
        assert "to=2020-01-31" in page.url
        page.goto(base + "/reservations?range=archive&lang=en")
        page.locator('#stays-filter-panel [name="apartment"]').select_option(str(host["apartments"][1]))
        page.locator('#stays-filter-panel [name="status"]').select_option("cancelled")
        with page.expect_navigation():
            page.locator("#stays-filter-panel .filter-apply").click()
        assert "range=custom" in page.url and "archive_scope=1" in page.url
        assert page.locator('.stays-desk tbody tr[aria-label*="10.03.2026"]').count() == 1
        page.goto(base + "/invoices?lang=en")
        empty_month = page.locator(".month-control.is-empty")
        assert empty_month.is_visible()
        assert page.locator("[data-month-all]").is_visible()
        assert page.locator("[data-month-native]").is_visible()
        assert page.locator("[data-month-trigger]").is_hidden()
        assert empty_month.evaluate("element => getComputedStyle(element).borderLeftStyle") == "dashed"
        browser.close()


def test_guest_register_delete_label_keeps_soft_archive_route(host):
    page = host["client"].get("/housebook?lang=en")
    assert page.status_code == 200, page.text
    assert f'action="/guests/{host["guest"]}/archive"' in page.text
    assert 'data-confirm-message="This item will move to Archived."' in page.text
    assert ">Delete</button>" in page.text

    response = host["client"].post(
        f"/guests/{host['guest']}/archive",
        data={"return_to": "/housebook"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    archived = db.query_one("SELECT id, archived_at FROM guest WHERE id = ?", (host["guest"],))
    assert archived and archived["archived_at"], "Delete must retain the guest as an archived row"
    register_after = host["client"].get("/housebook?lang=en")
    assert "Archived entries" in register_after.text


def _keep_page_error(errors, error):
    # A goto during a cross-document view transition makes Chromium abort it with this
    # rejection; it comes from the browser, not from our scripts.
    if not str(error).startswith("Transition was aborted"):
        errors.append(str(error))


def test_filter_draft_calendar_and_month_grid_commit_once(host, base):
    with sync_api.sync_playwright() as playwright:
        browser, context, page = _browser_context(playwright, host, base)
        requests = []
        page_errors = []
        page.on("pageerror", lambda error: _keep_page_error(page_errors, error))
        page.on("request", lambda request: requests.append(request) if request.method == "GET" else None)

        page.goto(base + "/reservations?range=all&lang=en")
        _capture(page, "stays-en-desktop-collapsed")
        toggle = page.locator("[data-filter-toggle]")
        assert toggle.is_visible()
        assert toggle.get_attribute("aria-expanded") == "false"
        toggle.click()
        assert page.locator("#stays-filter-panel").is_visible()
        _capture(page, "stays-en-desktop-expanded")
        initial_url = page.url

        trigger = page.locator("[data-range-trigger]")
        assert trigger.is_visible()
        assert page.locator("[data-range-popover]").get_attribute("role") == "dialog"
        assert page.locator("[data-range-caption]").inner_text().strip() == "All dates"
        trigger.click()
        _capture(page, "stays-en-desktop-day-calendar")
        first_day = page.locator(".range-day:not(.outside-month)").first
        first_value = first_day.get_attribute("data-range-date")
        first_day.click()
        assert page.locator(f'.range-day[data-range-date="{first_value}"]').evaluate("element => document.activeElement === element")
        page.keyboard.press("ArrowRight")
        next_day = page.evaluate("date => { const d=new Date(date+'T00:00:00'); d.setDate(d.getDate()+1); return d.toISOString().slice(0,10); }", first_value)
        assert page.locator(f'.range-day[data-range-date="{next_day}"]').evaluate("element => document.activeElement === element")
        page.keyboard.press("Escape")
        trigger.click()
        page.locator("[data-range-draft-from]").fill("2026-11-12")
        page.keyboard.press("Escape")
        assert page.locator("[data-range-popover]").is_hidden()
        assert page.locator("[data-range-from]").input_value() == ""
        assert page.locator("[data-range-caption]").inner_text().strip() == "All dates"
        assert trigger.evaluate("element => document.activeElement === element")

        trigger.click()
        page.locator("[data-range-draft-from]").fill("2026-11-12")
        page.locator("h1").click()
        assert page.locator("[data-range-popover]").is_hidden()
        assert page.locator("[data-range-from]").input_value() == ""

        trigger.click()
        page.locator("[data-range-draft-from]").fill("2026-11-12")
        page.locator("[data-range-draft-until]").fill("2026-11-08")
        assert page.locator("[data-range-apply]").is_disabled()
        assert page.locator("[data-range-error]").is_visible()
        page.locator("[data-range-draft-until]").fill("2026-11-18")
        assert page.locator("[data-range-apply]").is_enabled()
        before_apply = len(requests)
        page.locator("[data-range-apply]").click()
        assert page.url == initial_url
        assert len(requests) == before_apply, "Apply dates only updates the filter draft"
        assert page.locator("[data-range-from]").input_value() == "2026-11-12"
        assert page.locator("[data-range-until]").input_value() == "2026-11-18"
        page.locator("[data-filter-cancel]").click()
        assert page.url == initial_url
        assert page.locator("[data-range-from]").input_value() == ""
        assert page.locator("[data-range-caption]").inner_text().strip() == "All dates"
        assert toggle.get_attribute("aria-expanded") == "false"

        toggle.click()
        trigger.click()
        page.locator("[data-range-draft-from]").fill("2026-11-12")
        page.locator("[data-range-apply]").click()
        assert page.locator("[data-range-from]").input_value() == "2026-11-12"
        assert page.locator("[data-range-until]").input_value() == ""
        trigger.click()
        page.locator("[data-range-clear]").click()
        page.locator("[data-range-draft-until]").fill("2026-11-18")
        page.locator("[data-range-apply]").click()
        assert page.locator("[data-range-from]").input_value() == ""
        assert page.locator("[data-range-until]").input_value() == "2026-11-18"
        trigger.click()
        page.locator("[data-range-draft-from]").fill("2026-11-12")
        page.locator("[data-range-draft-until]").fill("2026-11-18")
        page.locator("[data-range-apply]").click()
        before_submit = len([request for request in requests if request.url.startswith(base + "/reservations?")])
        with page.expect_navigation():
            page.locator("#stays-filter-panel .filter-apply").click()
        after_submit = len([request for request in requests if request.url.startswith(base + "/reservations?")])
        assert after_submit == before_submit + 1
        assert "range=custom" in page.url
        assert "from=2026-11-12" in page.url and "to=2026-11-18" in page.url
        applied_url = page.url
        toggle.click()
        page.locator('#stays-filter-panel [name="apartment"]').select_option(str(host["apartments"][1]))
        assert page.url == applied_url
        page.locator("[data-filter-cancel]").click()
        page.reload()
        assert page.locator("[data-range-from]").input_value() == "2026-11-12"
        assert page.locator("[data-range-until]").input_value() == "2026-11-18"
        page.goto(base + "/reservations?range=all&lang=en")
        page.go_back()
        assert page.url == applied_url
        assert page.locator("[data-range-from]").input_value() == "2026-11-12"

        page.goto(base + "/invoices?lang=en")
        assert " ".join(page.locator("[data-filter-summary]").inner_text().split()) == "All dates · All properties"
        page.goto(base + f"/invoices?status=paid&q=Sample&apartment={host['apartments'][0]}&lang=en")
        assert "Payment recorded" in page.locator("[data-filter-summary]").inner_text()
        page.locator("[data-filter-toggle]").click()
        month_trigger = page.locator("[data-month-trigger]")
        assert month_trigger.is_visible()
        month_trigger.click()
        grid = page.locator("[data-month-grid]")
        assert grid.locator("[data-month-choice]").count() == 12
        assert page.locator("[data-month-all-choice]").is_visible()
        month_page_url = page.url
        before_step = len([request for request in requests if request.url.startswith(base + "/invoices?")])
        page.locator("[data-month-prev]").click()
        assert page.url == month_page_url
        assert len([request for request in requests if request.url.startswith(base + "/invoices?")]) == before_step
        month_trigger.click()
        month = page.locator('[data-month-choice="2026-09"]')
        if month.is_disabled():
            month = page.locator('[data-month-choice]:not([disabled])').first
        month.click()
        assert page.url == month_page_url
        page.locator("[data-filter-cancel]").click()
        assert page.locator("#filter-month").input_value() == ""
        assert page.locator("[data-month-next]").is_disabled()
        page.locator("[data-filter-toggle]").click()
        month_trigger.click()
        month = page.locator('[data-month-choice="2026-09"]')
        if month.is_disabled():
            month = page.locator('[data-month-choice]:not([disabled])').first
        month.click()
        assert page.url == month_page_url
        before_month_submit = len([request for request in requests if request.url.startswith(base + "/invoices?")])
        with page.expect_navigation():
            page.locator("#list-filter-panel .filter-apply").click()
        after_month_submit = len([request for request in requests if request.url.startswith(base + "/invoices?")])
        assert after_month_submit == before_month_submit + 1
        assert "month=" in page.url
        assert "status=paid" in page.url and "q=Sample" in page.url
        assert f"apartment={host['apartments'][0]}" in page.url

        page.goto(base + "/reservations?range=archive&lang=en")
        page.locator("[data-filter-toggle]").click()
        page.locator('#stays-filter-panel [name="apartment"]').select_option(str(host["apartments"][1]))
        page.locator('#stays-filter-panel [name="status"]').select_option("cancelled")
        with page.expect_navigation():
            page.locator("#stays-filter-panel .filter-apply").click()
        assert "archive_scope=1" in page.url and "range=archive" in page.url
        assert page.locator('.stays-desk tbody tr[aria-label*="10.03.2026"]').count() == 1
        assert "Filter Property Two" in page.locator("[data-filter-summary]").inner_text()
        page.goto(base + f"/reservations?range=custom&archive_scope=1&apartment={host['apartments'][1]}&status=cancelled&lang=en")
        assert "range=archive" in page.locator('.settings-pills .settings-pill.is-current').get_attribute("href")
        assert page.locator("[data-stays-reset]").get_attribute("href") == "/reservations?range=archive"
        assert not page_errors, "browser script errors: " + " | ".join(page_errors)

        page.goto(base + f"/invoices?status=paid&q=Sample&apartment={host['apartments'][0]}&lang=en")
        _capture(page, "invoices-en-desktop-collapsed")
        page.locator("[data-filter-toggle]").click()
        _capture(page, "invoices-en-desktop-expanded")
        page.locator("[data-month-trigger]").click()
        _capture(page, "invoices-en-desktop-month-grid")

        # 1051, owner decision 2026-11-09: stay fees use the compact month control (no Filters
        # toggle, no summary line, no Apply); the month grid opens straight from the trigger.
        page.goto(base + "/stay-fees?lang=en")
        assert page.locator("[data-filter-toggle]").count() == 0
        assert page.locator("form.list-filter--compact").is_visible()
        assert page.locator("#filter-month").get_attribute("required") is not None
        page.locator("[data-month-trigger]").click()
        assert page.locator("[data-month-all-choice]").count() == 0
        assert page.locator("[data-filter-summary]").count() == 0
        _capture(page, "stay-fees-en-desktop-required-month-grid")
        page.goto(base + f"/stay-fees/{host['apartments'][0]}?month=2026-09&lang=en")
        assert page.locator("[data-filter-toggle]").count() == 0
        assert page.locator("#filter-month").get_attribute("required") is not None
        page.locator("[data-month-trigger]").click()
        _capture(page, "stay-fees-detail-en-desktop-month-grid")
        browser.close()


def test_filter_geometry_and_popovers_stay_inside_the_viewport_in_english_and_czech(host, base):
    # 1051, owner decision 2026-11-09: /stay-fees has no filter toolbar any more (compact month
    # control); its geometry and popover fit are covered by test_stay_fee_month_filter_1051_browser.py.
    routes = ("/reservations", "/invoices", "/housebook")
    widths = (360, 390, 471, 760, 850, 1280)
    with sync_api.sync_playwright() as playwright:
        browser, _context, page = _browser_context(playwright, host, base, width=1280)
        page_errors = []
        page.on("pageerror", lambda error: _keep_page_error(page_errors, error))
        for width in widths:
            page.set_viewport_size({"width": width, "height": 1000})
            for lang in ("en", "cs"):
                for route in routes:
                    page.goto(base + route + "?lang=" + lang)
                    if route == "/invoices":
                        page.wait_for_function("document.documentElement.classList.contains('has-js')")
                    lane = ".stays-pills" if route == "/reservations" else "[data-filter-toolbar]"
                    toolbar = page.locator(lane).first
                    assert toolbar.is_visible(), f"{width}px {lang} {route}"
                    capture = width in (390, 1280)
                    name = {"/reservations": "stays", "/invoices": "invoices", "/stay-fees": "stay-fees", "/housebook": "guest-register"}[route]
                    if capture:
                        _capture(page, f"{name}-{lang}-{width}-collapsed")
                    geometry = page.evaluate(
                        """(laneSel) => {
                          const root = document.documentElement;
                          const toolbar = document.querySelector(laneSel).getBoundingClientRect();
                          const summary = document.querySelector('[data-filter-summary]').getBoundingClientRect();
                          const lane = document.querySelector(laneSel);
                          const pageWidth = root.clientWidth;
                          return {
                            overflow: (laneSel !== '.chips' && lane.scrollWidth > lane.clientWidth + 1) || toolbar.left < -1 || toolbar.right > pageWidth + 1 || (pageWidth <= 600 && root.scrollWidth > pageWidth + 1),
                            summaryInside: summary.width === 0 || (summary.left >= toolbar.left - 1 && summary.right <= toolbar.right + 1),  // 0852: the summary line is dropped on phones (no fine print)
                            triggerHeight: Math.round(document.querySelector('[data-filter-toggle]').getBoundingClientRect().height),
                            clipped: [...document.querySelectorAll(laneSel + ' .btn, ' + laneSel + ' .chip')].some((button) => button.scrollWidth > button.clientWidth + 1),
                          };
                        }""",
                        lane,
                    )
                    assert not geometry["overflow"], f"{width}px {lang} {route}: filter lane overflow"
                    assert geometry["summaryInside"], f"{width}px {lang} {route}: summary overflow"
                    assert not geometry["clipped"], f"{width}px {lang} {route}: clipped toolbar label"
                    if width < 1024 and route.startswith("/reservations"):
                        # compact phone rule: the stays list shows the mockup's four chips; filters are on desktop
                        assert geometry["triggerHeight"] == 0
                        continue
                    elif width <= 600:
                        assert geometry["triggerHeight"] >= 44
                    else:
                        assert geometry["triggerHeight"] >= 37  # 0852: the v2 head actions are 37 px (mockup)
                    if capture:
                        page.locator("[data-filter-toggle]").click()
                        _capture(page, f"{name}-{lang}-{width}-expanded")
                    else:
                        page.locator("[data-filter-toggle]").click()
                    if route == "/invoices":
                        month_control = page.locator(".month-control.is-empty")
                        trigger = page.locator("[data-month-trigger]")
                        settle_motion(page)  # 0720: measure after the filter panel motion lands
                        control_box = month_control.bounding_box()
                        trigger_box = trigger.bounding_box()
                        assert control_box and trigger_box and trigger.is_visible(), (
                            f"{width}px {lang}: enhanced All dates month trigger must be visible"
                        )
                        for edge in ("x", "y", "width", "height"):
                            assert abs(control_box[edge] - trigger_box[edge]) <= 1, {
                                "width": width, "lang": lang, "wrapper": control_box, "trigger": trigger_box,
                            }
                        wrapper_style = month_control.evaluate("""element => ({
                          border: getComputedStyle(element).borderLeftWidth,
                          background: getComputedStyle(element).backgroundColor
                        })""")
                        assert wrapper_style["border"] == "0px" and wrapper_style["background"] == "rgba(0, 0, 0, 0)", (
                            width, lang, wrapper_style
                        )
                    date_trigger = page.locator("[data-range-trigger]")
                    if date_trigger.count():
                        date_trigger.click()
                        popover = page.locator("[data-range-popover]")
                        if capture:
                            _capture(page, f"{name}-{lang}-{width}-day-calendar")
                    else:
                        page.locator("[data-month-trigger]").click()
                        popover = page.locator("[data-month-grid-panel]")
                        if capture and route == "/invoices":
                            _capture(page, f"{name}-{lang}-{width}-month-grid")
                    settle_motion(page)  # measure the popover where it lands, not mid-motion
                    bounds = popover.bounding_box()
                    assert bounds is not None, f"{width}px {lang} {route}: popover should be visible"
                    assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width + 1
                    assert bounds["y"] >= 0 and bounds["y"] + bounds["height"] <= 1000 + 1
                    if route == "/reservations" and width <= 390:
                        targets = page.evaluate("""() => {
                          const day = [...document.querySelectorAll('.range-day')].map(e => e.getBoundingClientRect());
                          const fields = [...document.querySelectorAll('.range-draft-fields input')].map(e => e.getBoundingClientRect());
                          return {days: day.every(r => r.width >= 44 && r.height >= 44), fields: fields.every(r => r.height >= 44)};
                        }""")
                        assert targets["days"], f"{width}px {lang}: calendar day target below 44px"
                        assert targets["fields"], f"{width}px {lang}: date draft input below 44px"
                    if route == "/reservations" and width in (360, 390, 471, 760, 850, 1280):
                        _capture(page, f"stays-{lang}-{width}")
                    page.keyboard.press("Escape")
        for width in (390, 1280):
            page.set_viewport_size({"width": width, "height": 1000})
            for lang in ("en", "cs"):
                page.goto(base + f"/stay-fees/{host['apartments'][0]}?month=2026-10&lang={lang}")
                _capture(page, f"stay-fee-detail-{lang}-{width}-collapsed")
                # 1051, owner decision 2026-11-09: no Filters toggle; the compact month control is always shown.
                assert page.locator("[data-filter-toggle]").count() == 0
                assert page.locator("#filter-month").get_attribute("required") is not None
                page.locator("[data-month-trigger]").click()
                bounds = page.locator("[data-month-grid-panel]").bounding_box()
                assert bounds is not None
                assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width + 1
                assert bounds["y"] >= 0 and bounds["y"] + bounds["height"] <= 1000 + 1
                _capture(page, f"stay-fee-detail-{lang}-{width}-month-grid")
                page.keyboard.press("Escape")
        for width in (390, 1280):
            page.set_viewport_size({"width": width, "height": 1000})
            for lang in ("en", "cs"):
                page.goto(base + f"/invoices?month=2026-08&lang={lang}")
                page.locator("[data-filter-toggle]").click()
                page.locator("[data-month-trigger]").click()
                selected_month = page.locator('[data-month-choice="2026-08"].selected')
                assert selected_month.is_visible()
                assert selected_month.evaluate("element => getComputedStyle(element).backgroundColor") == "rgb(249, 233, 231)"  # v2 --brand-soft
                _capture(page, f"invoices-selected-month-{lang}-{width}-month-grid")
        assert not page_errors, "browser script errors: " + " | ".join(page_errors)
        browser.close()


# ---------------------------------------------------------------------------
# 0968: the default Stays tab says it includes overdue stays; the filter panel
# is one compact row; Reset filters sits under the scope line, away from Cancel.
# ---------------------------------------------------------------------------
from datetime import date, timedelta

from app import deadlines, reporting

SCOPE_LABEL = {"en": "Upcoming & current", "cs": "Nadcházející"}


def _past_deadline_arrival():
    now = deadlines.local_now()
    for back in range(10, 21):
        candidate = date.today() - timedelta(days=back)
        if deadlines.reporting_deadline(candidate) < now:
            return candidate
    pytest.fail("no past-deadline arrival found")


def _shots_dir() -> Path:
    target = Path(os.environ.get("UBYHOST_SHOTS_DIR") or "/tmp/ubyhost-b10")
    target.mkdir(parents=True, exist_ok=True)
    return target


@pytest.fixture(scope="module")
def scope_host():
    db.init_db()
    username = f"scope-{secrets.token_hex(4)}"
    owner = mark_security_prompt_seen(auth.create_account(
        f"{username}@example.test", "Scope Test", role="host", username=username
    ))
    entity = db.insert("legal_entity", {
        "name": "Scope Test s.r.o.", "owner_user_id": owner, "created_at": db.utcnow(),
    })
    apartments = []
    for name in ("Scope Alpha", "Scope Beta"):
        apartments.append(db.insert("apartment", {
            "internal_name": name, "owner_user_id": owner, "legal_entity_id": entity,
            "permalink_token": f"scope{secrets.token_hex(4)}", "automation_mode": "manual",
            "active": 1, "created_at": db.utcnow(),
        }))
    alpha, beta = apartments
    now = db.utcnow()
    today = date.today()
    ids = {}

    def add(key, apartment_id, start, end, archived_at=None):
        ids[key] = db.insert("reservation", {
            "apartment_id": apartment_id, "source": "manual",
            "uid": f"scope-{key}-{secrets.token_hex(3)}",
            "date_from": start.isoformat(), "date_to": end.isoformat(),
            "summary": f"Scope {key} stay", "status": "active",
            "expected_guests_override": 1, "archived_at": archived_at,
            "created_at": now, "updated_at": now,
        })
        return ids[key]

    arrival = _past_deadline_arrival()
    overdue = add("overdue", alpha, arrival, arrival + timedelta(days=3))
    db.insert("guest", {
        "reservation_id": overdue, "surname": "SCOPEOVERDUE", "first_name": "ANNA",
        "birth_date": "01011990", "nationality": "DEU", "doc_number": "P9988772",
        "res_street": "Hauptstrasse 5", "res_city": "Berlin", "res_country": "DEU",
        "purpose": "10", "is_lead": 1, "entered_by": "guest", "signature_png": "imported",
        "signed_at": now, "passport_photo_at": now, "identity_verified_at": now,
        "stay_from": arrival.isoformat(), "stay_to": (arrival + timedelta(days=3)).isoformat(),
        "submit_state": reporting.PENDING, "created_at": now, "updated_at": now,
    })
    add("current", alpha, today - timedelta(days=1), today + timedelta(days=2))
    for index in range(5):
        start = today + timedelta(days=10 + index * 4)
        add(f"future{index}", alpha, start, start + timedelta(days=2))
    add("beta", beta, today + timedelta(days=12), today + timedelta(days=14))
    add("archived", alpha, today + timedelta(days=60), today + timedelta(days=62), archived_at=now)
    client = TestClient(app)
    response = login_as(client, username, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    yield {"client": client, "owner": owner, "apartments": apartments, "ids": ids}
    db.execute("DELETE FROM guest WHERE reservation_id IN (?)", (overdue,))
    db.execute("DELETE FROM reservation WHERE apartment_id IN (?, ?)", apartments)
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ? OR actor_user_id = ?", (owner, owner))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner,))


def test_default_stays_tab_label_names_overdue_and_the_note_only_shows_there(scope_host):
    client, ids = scope_host["client"], scope_host["ids"]
    for lang in ("en", "cs"):
        page = client.get(f"/reservations?lang={lang}").text
        label = SCOPE_LABEL[lang].replace("&", "&amp;")
        assert f'aria-current="page">{label}<' in page
        assert f"/reservations/{ids['overdue']}" in page, "overdue stay must stay visible"
        assert f"/reservations/{ids['current']}" in page
        assert f"/reservations/{ids['archived']}" not in page
    assert f"/reservations/{ids['archived']}" in client.get("/reservations?range=archive&lang=en").text


def test_stays_filter_is_one_row_with_reset_apart_from_cancel_and_scope_survives_paging(scope_host, base):
    apartments = scope_host["apartments"]
    alpha, beta = apartments
    shots = _shots_dir()
    with sync_api.sync_playwright() as playwright:
        browser, _context, page = _browser_context(playwright, scope_host, base, width=1280)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base + "/reservations?lang=en")
        page.locator("[data-filter-toggle]").click()
        panel = page.locator("#stays-filter-panel")
        settle_motion(page)
        assert panel.is_visible()
        # No link in the action row: Apply and Cancel only.
        assert page.locator("#stays-filter-panel .filter-panel-actions a").count() == 0
        apply_box = page.locator("#stays-filter-panel .filter-apply").bounding_box()
        cancel_box = page.locator("#stays-filter-panel [data-filter-cancel]").bounding_box()
        fields_box = page.locator("#stays-filter-panel .filter-fields").bounding_box()
        actions_box = page.locator("#stays-filter-panel .filter-panel-actions").bounding_box()
        panel_box = panel.bounding_box()
        (shots / "heights.txt").write_text(f"panel_height_1280={round(panel_box['height'])}\n", encoding="utf-8")
        assert abs(apply_box["y"] - cancel_box["y"]) <= 2, "Apply and Cancel share one row"
        # Compact: the actions sit in the same row as the fields, not under them.
        assert actions_box["y"] < fields_box["y"] + fields_box["height"] - 4, (actions_box, fields_box)
        page.screenshot(path=str(shots / "filter-open-en-1280.png"), full_page=True)

        # Cancel restores the draft and closes the panel without navigating.
        before_url = page.url
        page.locator('#stays-filter-panel [name="apartment"]').select_option(str(alpha))
        page.locator("#stays-filter-panel [data-filter-cancel]").click()
        assert not panel.is_visible()
        assert page.url == before_url
        assert page.locator('#stays-filter-panel [name="apartment"]').input_value() == ""

        # Apply: scope stays visible, Reset filters is above the panel and far from Cancel.
        page.locator("[data-filter-toggle]").click()
        page.locator('#stays-filter-panel [name="apartment"]').select_option(str(alpha))
        with page.expect_navigation():
            page.locator("#stays-filter-panel .filter-apply").click()
        # The default range is kept in the URL; Apply with today as the from-date resolves to "upcoming".
        assert f"apartment={alpha}" in page.url and "range=" in page.url
        assert "Scope Alpha" in page.locator("[data-filter-summary]").inner_text()
        reset = page.locator("[data-stays-reset]")
        assert reset.is_visible() and reset.inner_text().strip() == "Reset filters"
        page.locator("[data-filter-toggle]").click()
        settle_motion(page)
        reset_box = reset.bounding_box()
        cancel_box = page.locator("#stays-filter-panel [data-filter-cancel]").bounding_box()
        assert reset_box["y"] + reset_box["height"] <= panel.bounding_box()["y"] + 1
        assert cancel_box["y"] - (reset_box["y"] + reset_box["height"]) >= 40, "Reset and Cancel are not adjacent"
        page.screenshot(path=str(shots / "filter-applied-en-1280.png"), full_page=True)

        # Pagination keeps the scope: page size is 5, Alpha has 7 stays in this view.
        next_link = page.locator('a[rel="next"]').first
        assert f"apartment={alpha}" in next_link.get_attribute("href")
        assert "range=" in next_link.get_attribute("href")
        assert page.locator(".stays-desk tbody tr").count() == 5
        with page.expect_navigation():
            next_link.click()
        assert "page=2" in page.url and f"apartment={alpha}" in page.url
        assert page.locator(".stays-desk tbody tr").count() == 2
        assert "Scope Alpha" in page.locator("[data-filter-summary]").inner_text()
        assert page.locator(f'a[href^="/reservations/{scope_host["ids"]["beta"]}?"]').count() == 0

        # Reset filters leaves the scope and the link goes away.
        with page.expect_navigation():
            page.locator("[data-stays-reset]").click()
        assert "range=all" in page.url and "apartment=" not in page.url
        assert page.locator("[data-stays-reset]").count() == 0

        # Empty filtered result keeps the way back.
        page.goto(base + f"/reservations?range=custom&apartment={beta}&from=2000-01-01&to=2000-01-02&lang=en")
        assert page.locator(".stays-desk tbody tr").count() == 0
        assert page.get_by_text("No stay matches this filter.").first.is_visible()
        assert page.locator("[data-stays-reset]").is_visible()
        page.screenshot(path=str(shots / "filter-empty-en-1280.png"), full_page=True)
        assert not errors, errors
        browser.close()


def test_stays_default_tab_label_is_not_clipped_at_phone_tablet_and_desktop_in_english_and_czech(scope_host, base):
    shots = _shots_dir()
    with sync_api.sync_playwright() as playwright:
        browser, _context, page = _browser_context(playwright, scope_host, base, width=1280)
        for width in (390, 768, 1280):
            page.set_viewport_size({"width": width, "height": 1000})
            for lang in ("en", "cs"):
                page.goto(base + f"/reservations?lang={lang}")
                current = page.locator(".stays-pills [aria-current=page]").first
                assert " ".join(current.inner_text().split()) == SCOPE_LABEL[lang], f"{width}px {lang}"
                geometry = page.evaluate(
                    """() => {
                      const root = document.documentElement;
                      const pill = document.querySelector('.stays-pills [aria-current=page]');
                      const box = pill.getBoundingClientRect();
                      return {
                        pageOverflow: root.scrollWidth > root.clientWidth + 1,
                        pillClipped: pill.scrollWidth > pill.clientWidth + 1 || box.left < -1 || box.right > root.clientWidth + 1,
                      };
                    }"""
                )
                assert not geometry["pageOverflow"], f"{width}px {lang}: page overflow"
                assert not geometry["pillClipped"], f"{width}px {lang}: tab label clipped"
                page.screenshot(path=str(shots / f"stays-default-{lang}-{width}.png"), full_page=True)
        browser.close()
