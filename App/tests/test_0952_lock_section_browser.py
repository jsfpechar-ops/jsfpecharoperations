"""0952: the one Smart lock section: an edit outside the property form marks it dirty,
the #door-code and #smart-locks anchors open #sec-lock, and screenshots for the report."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

REQUIRE_BROWSER = os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1"
if REQUIRE_BROWSER:
    import playwright.sync_api as sync_api
else:
    sync_api = pytest.importorskip("playwright.sync_api")

from app import auth, config, db
from tests.test_0541_property_page_phone_browser import (  # noqa: F401  (0541 browser fixtures)
    LOCK, _launch, _open_app, _path, _placeholders, base, dashboard_rich_host,
)
from tests.test_host_quiet_dashboard_browser import dashboard_host  # noqa: F401  (base fixture chain)
from tests.v2_mockup import PAGES

PANEL = {"smart_locks_enabled": True, "account": None, "receiver": "", "locks": [], "fetched_at": None,
         "reauth": False, "return_to": "/smart-locks", "properties_using": {}}
SHOTS = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0952"


def _with_lock_account(monkeypatch, host):
    apartment_id = _placeholders(host)["first_property"]
    owner = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (apartment_id,))["owner_user_id"]
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(config, "TTLOCK_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "TTLOCK_CLIENT_SECRET", "csecret")
    db.insert("lock_account", {"owner_user_id": owner, "provider": "ttlock", "username": "synthetic_0952",
                               "status": "ok", "locks_json": __import__("json").dumps([LOCK]),
                               "created_at": db.utcnow(), "updated_at": db.utcnow()})
    db.execute("UPDATE apartment SET lock_provider = 'ttlock', lock_id = ? WHERE id = ?", (LOCK["lock_id"], apartment_id))
    return apartment_id, owner


def _teardown(apartment_id, owner):
    db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (owner,))
    db.execute("UPDATE apartment SET lock_provider = NULL, lock_id = NULL WHERE id = ?", (apartment_id,))


def _spec_path(host):
    return _path(next(s for s in PAGES if s["name"] == "property"), host)


def test_0952_door_code_edit_outside_form_marks_it_dirty(base, dashboard_rich_host, monkeypatch):  # noqa: F811
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    apartment = _spec_path(dashboard_rich_host)
    apartment_id, owner = _with_lock_account(monkeypatch, dashboard_rich_host)
    try:
        with sync_api.sync_playwright() as playwright:
            browser = _launch(playwright)
            context, page = _open_app(browser, base, cookie, apartment, 390)
            try:
                page.goto(f"{base}{apartment}?view=settings&section=lock&lang=en")
                page.wait_for_load_state("networkidle")
                form = page.locator("form#property-settings-form")
                # The check-in time select sits outside the form and names it with form="...".
                assert page.evaluate("document.getElementById('lock_checkin_hour').form.id") == "property-settings-form"
                assert page.evaluate("!document.getElementById('property-settings-form').contains(document.getElementById('lock_checkin_hour'))")
                assert form.get_attribute("data-dirty") is None
                # The Turn on / Turn off buttons submit their own forms: focusing one is no edit of the property form.
                page.locator(".lock-state-form button").first.focus()
                assert form.get_attribute("data-dirty") is None
                loaded = page.input_value("#lock_checkin_hour")
                page.select_option("#lock_checkin_hour", "23" if loaded != "23" else "22")
                page.wait_for_timeout(200)
                assert form.get_attribute("data-dirty") == "1"
                assert page.locator(".savebar[data-for='property-settings-form']").is_visible()
            finally:
                context.close()
                browser.close()
    finally:
        _teardown(apartment_id, owner)


def test_0952_door_code_and_smart_locks_anchors_open_the_lock_section(base, dashboard_rich_host, monkeypatch):  # noqa: F811
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    assert cookie
    apartment = _spec_path(dashboard_rich_host)
    apartment_id, owner = _with_lock_account(monkeypatch, dashboard_rich_host)
    try:
        with patch("app.routes.admin._smart_lock_panel_context", return_value=PANEL), \
                sync_api.sync_playwright() as playwright:
            browser = _launch(playwright)
            context, page = _open_app(browser, base, cookie, apartment, 390)
            try:
                for anchor in ("door-code", "smart-locks"):
                    page.goto(f"{base}{apartment}?view=settings&lang=en#{anchor}")
                    page.wait_for_load_state("networkidle")
                    assert page.locator("#sec-lock[open]").count() == 1, anchor
                    # The section itself may have no box (display: contents); its controls must be visible.
                    assert page.locator(f"#{anchor} :is(select, input, button, a, p, h2, h3):visible").count() > 0, anchor
                assert page.locator("[id='sec-lock']").count() == 1
                assert page.locator("#sec-lock-account").count() == 0
            finally:
                context.close()
                browser.close()
    finally:
        _teardown(apartment_id, owner)


def test_0952_capture_lock_section_screenshots(base, dashboard_rich_host, monkeypatch):  # noqa: F811
    if os.environ.get("UBYHOST_CAPTURE_0952") != "1":
        return  # capture only when asked (orchestrator report run)
    cookie = dashboard_rich_host["client"].cookies.get(auth.SESSION_COOKIE)
    apartment = _spec_path(dashboard_rich_host)
    apartment_id, owner = _with_lock_account(monkeypatch, dashboard_rich_host)
    SHOTS.mkdir(parents=True, exist_ok=True)
    try:
        with patch("app.routes.admin._smart_lock_panel_context", return_value=PANEL), \
                sync_api.sync_playwright() as playwright:
            browser = _launch(playwright)
            for width in (390, 768, 1280):
                context, page = _open_app(browser, base, cookie, apartment, width)
                try:
                    page.goto(f"{base}{apartment}?view=settings&section=lock&lang=en")
                    page.wait_for_load_state("networkidle")
                    page.locator("#sec-lock").scroll_into_view_if_needed()
                    page.screenshot(path=str(SHOTS / f"lock-section-{width}.png"), full_page=False)
                finally:
                    context.close()
            browser.close()
    finally:
        _teardown(apartment_id, owner)
