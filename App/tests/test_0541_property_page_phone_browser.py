"""0541: on a phone the property page opens with the basics section closed."""
from __future__ import annotations

import json

from app import auth, config, db
from tests.test_0710_v2_mockup_match_browser import (  # noqa: F401  (0541 browser fixtures)
    _open_app,
    _path,
    _placeholders,
    dashboard_rich_host,
)
from tests.test_host_quiet_dashboard_browser import (  # noqa: F401  (0541 browser fixtures)
    _launch,
    base,
    dashboard_host,
    sync_api,
)
from tests.v2_mockup import PAGES

LOCK = {"lock_id": "70940001", "alias": "Synthetic Door", "battery": 90, "tz_offset_ms": 3600000}


def test_0541_phone_basics_closed_on_load(base, dashboard_rich_host):  # noqa: F811
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    spec = next(s for s in PAGES if s["name"] == "property")
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, cookie, _path(spec, dashboard_rich_host), 390)
        try:
            assert page.locator("#sec-basics[open]").count() == 0
        finally:
            context.close()
            browser.close()


def test_0547_phone_property_switch_invalid_field_calendar_and_return(base, dashboard_rich_host, monkeypatch):  # noqa: F811
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    spec = next(s for s in PAGES if s["name"] == "property")
    apartment = _path(spec, dashboard_rich_host)
    apartment_id = _placeholders(dashboard_rich_host)["first_property"]
    owner = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (apartment_id,))["owner_user_id"]
    # Seed one door-code lock on this property (as the host fixture in test_property_navigation_browser.py does) so the switch renders.
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    db.insert("lock_account", {"owner_user_id": owner, "provider": "ttlock", "username": "synthetic_0541",
                               "status": "ok", "locks_json": json.dumps([LOCK]),
                               "created_at": db.utcnow(), "updated_at": db.utcnow()})
    db.execute("UPDATE apartment SET lock_provider = 'ttlock', lock_id = ? WHERE id = ?", (LOCK["lock_id"], apartment_id))
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        context, page = _open_app(browser, base, cookie, apartment, 390)
        try:
            # 0954: the status block replaces the switch; its one button is a form submit.
            page.goto(f"{base}{apartment}?view=settings&section=lock&lang=en")
            page.wait_for_load_state("networkidle")
            block = page.locator(".lock-state")
            assert block.get_attribute("data-state") in ("on", "off", "offline", "times")
            assert block.locator("button").count() == 1
            assert page.locator("#door_codes").count() == 0

            # 0547: an invalid required field in a closed section opens that section on submit.
            page.goto(f"{base}{apartment}?lang=en")
            page.wait_for_load_state("networkidle")
            assert page.locator("#sec-messages[open]").count() == 0
            # On a phone the save bar shows only while a section is open, so open basics first.
            page.locator("#sec-basics > summary").click()
            assert page.locator("#sec-messages[open]").count() == 0
            page.evaluate("document.getElementById('permalink_pin').value = ''; document.getElementById('permalink_pin').dispatchEvent(new Event('input', { bubbles: true }))")
            page.locator(".savebar button[type=submit]").click()
            page.wait_for_timeout(300)
            assert page.locator("#sec-messages[open]").count() == 1

            # 0547: ?add_calendar=1 shows the calendar connect form without is-collapsed.
            page.goto(f"{base}{apartment}?add_calendar=1&lang=en")
            page.wait_for_load_state("networkidle")
            assert page.locator("#calendar-connect").count() == 1
            assert "is-collapsed" not in page.locator("#calendar-connect").get_attribute("class").split()

            # 0547: saving from an opened section returns to that section. Fresh page per section;
            # the submit is dispatched synthetically so browser validation on the fixture cannot block it.
            submit_js = """() => {
                const form = document.getElementById('property-settings-form');
                form.addEventListener('submit', e => e.preventDefault());
                form.dispatchEvent(new Event('submit', {cancelable: true}));
            }"""
            page.goto(f"{base}{apartment}?lang=en")
            page.wait_for_load_state("networkidle")
            arm_toggle = "id => { window.__toggled = new Promise(r => document.getElementById(id).addEventListener('toggle', r, {once: true})); }"
            page.evaluate(arm_toggle, "sec-lock")
            page.locator("#sec-lock > summary").click()
            page.evaluate("() => window.__toggled")
            page.evaluate(submit_js)
            return_value = page.locator("input[data-property-return]").input_value()
            assert "section=lock" in return_value, return_value

            page.goto(f"{base}{apartment}?lang=en")
            page.wait_for_load_state("networkidle")
            page.evaluate(arm_toggle, "sec-police")
            page.locator("#sec-police > summary").click()
            page.evaluate("() => window.__toggled")
            page.evaluate(submit_js)
            return_value = page.locator("input[data-property-return]").input_value()
            assert "section=reporting" in return_value, return_value
        finally:
            context.close()
            browser.close()
            db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (owner,))
            db.execute("UPDATE apartment SET lock_provider = NULL, lock_id = NULL WHERE id = ?", (apartment_id,))


def test_0948_strip_shares_form_edges_and_columns(base, dashboard_rich_host):  # noqa: F811
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    spec = next(s for s in PAGES if s["name"] == "property")
    path = _path(spec, dashboard_rich_host)
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for width, columns in ((390, 2), (768, 3), (1280, 3), (1600, 3)):
                context, page = _open_app(browser, base, cookie, path, width)
                try:
                    strip = page.locator(".prop-strip").bounding_box()
                    form = page.locator(".form").bounding_box()
                    assert abs(strip["x"] - form["x"]) <= 1, width
                    assert abs(strip["x"] + strip["width"] - (form["x"] + form["width"])) <= 1, width
                    count = page.evaluate(
                        "getComputedStyle(document.querySelector('.prop-strip')).gridTemplateColumns.split(' ').length"
                    )
                    assert count == columns, (width, count)
                    if width <= 768:
                        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), width
                finally:
                    context.close()
        finally:
            browser.close()


def test_0948_police_card_opens_its_section(base, dashboard_rich_host):  # noqa: F811
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    spec = next(s for s in PAGES if s["name"] == "property")
    path = _path(spec, dashboard_rich_host)
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            context, page = _open_app(browser, base, cookie, path, 1280)
            try:
                assert page.locator("#sec-police[open]").count() == 0
                page.locator("[data-strip='police']").click()
                assert page.locator("#sec-police[open]").count() == 1
            finally:
                context.close()
        finally:
            browser.close()


def test_0948_copy_settings_button_sits_in_the_header_row(base, dashboard_rich_host):  # noqa: F811
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    path = "/apartments/new"  # copy is offered on the new page; settings hide it once setup is finished
    with sync_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for width in (390, 768, 1280):
                context, page = _open_app(browser, base, cookie, path, width)
                try:
                    button = page.locator(".airbnb-actions .copy-settings-open").first.bounding_box()
                    title = page.locator("h1").first.bounding_box()
                    form = page.locator(".property-create-lane").bounding_box()
                    assert button["x"] >= form["x"] - 1, width
                    assert button["x"] + button["width"] <= form["x"] + form["width"] + 1, width
                    overlaps = not (button["y"] + button["height"] <= title["y"] or title["y"] + title["height"] <= button["y"]
                                    or button["x"] + button["width"] <= title["x"] or title["x"] + title["width"] <= button["x"])
                    assert not overlaps, width
                    if width == 390:
                        assert button["height"] >= 44, width
                        assert button["y"] >= title["y"] + title["height"] - 1, width
                    if width == 390:
                        page.locator(".airbnb-actions .copy-settings-open").first.click()
                        assert page.locator("#copy-settings[open]").count() == 1
                finally:
                    context.close()
        finally:
            browser.close()
