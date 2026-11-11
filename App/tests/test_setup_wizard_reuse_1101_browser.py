"""1101: a new property walks calendar, police (with paste), guest link and done in the browser.

Fake ``SAMPLE_*`` values and a fake police client only. Set UBYHOST_SHOTS_1101 to a
folder to write the review screenshots.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from app import db
from tests.browser_support import settle_motion
from tests.test_host_police_letter_browser import FULL_LETTER, live  # noqa: F401
from tests.test_police_letter_flow import USERNAME, _operator_id, fake_client, host  # noqa: F401

if os.environ.get("UBYHOST_REQUIRE_BROWSER") == "1":
    import playwright.sync_api  # noqa: F401
else:
    pytest.importorskip("playwright.sync_api")

WIDTHS = [390, 768, 1280]
SHOTS = os.environ.get("UBYHOST_SHOTS_1101")
TEST_BUTTON = '.setup-wizard-foot button[form="police-form"][formaction$="/test-connection"]'
SKIP = ".setup-wizard-skip button[value=skip]"


def shot(page, name, width):
    if not SHOTS:
        return
    page.wait_for_timeout(500)
    settle_motion(page)
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(Path(SHOTS) / f"{name}-{width}.png"), full_page=True)


def new_property(host, name) -> int:
    response = host.post(
        "/apartments",
        data={
            "internal_name": name, "city_en": "Praha", "legal_entity_id": str(_operator_id(USERNAME)),
            "addr_obec": "Praha", "addr_street": "Synthetic", "addr_house_no": "12", "addr_zip": "120 00",
            "checkin_hour": "14", "checkout_hour": "10",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "/setup/calendar" in response.headers["location"]
    return db.query_one("SELECT id FROM apartment WHERE internal_name = ?", (name,))["id"]


def fits(page) -> bool:
    return page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")


def foot_ok(page):
    """Footer buttons are 44 px tall on touch widths (36 px at 1024+, by design) and do not overlap."""
    boxes = []
    minimum = 43.5 if page.viewport_size["width"] < 1024 else 35.5
    for button in page.locator(".setup-wizard-foot .ui-btn:visible").all():
        box = button.bounding_box()
        assert box and box["height"] >= minimum, box
        boxes.append(box)
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            apart = (a["x"] + a["width"] <= b["x"] + 1 or b["x"] + b["width"] <= a["x"] + 1
                     or a["y"] + a["height"] <= b["y"] + 1 or b["y"] + b["height"] <= a["y"] + 1)
            assert apart, (a, b)


def paste_js(page):
    page.locator("details.police-letter-paste").evaluate("d => { d.open = true; }")
    page.fill("#letter_text", FULL_LETTER)
    page.dispatch_event("#letter_text", "paste")
    page.wait_for_function("() => document.getElementById('uby_idub').value !== ''", timeout=3000)
    page.wait_for_function(
        "() => !!document.querySelector('#police-letter-status').textContent.trim()", timeout=3000)


def dialog_closed(page):
    return page.evaluate("() => { const d = document.getElementById('unsaved-dialog'); return !d || !d.open; }")


@pytest.mark.parametrize("width", WIDTHS)
def test_new_property_walks_to_the_ready_card(live, fake_client, width):  # noqa: F811
    base = live.plain.split("/apartments")[0]
    apartment_id = new_property(live_host(live), f"Walk {width}")
    page = live.open(width)
    page.goto(f"{base}/apartments/{apartment_id}/setup/calendar?lang=en")
    assert fits(page)
    foot_ok(page)
    shot(page, "calendar", width)
    page.locator(SKIP).click()
    page.wait_for_url("**/setup/police**")
    assert page.locator(".setup-wizard-back").is_visible()
    paste_js(page)
    assert dialog_closed(page)
    for name in ("uby_idub", "uby_ws_user", "uby_ws_password", "uby_mark", "uby_name"):
        assert page.input_value(f"#{name}"), name
    assert fits(page)
    foot_ok(page)
    shot(page, "police", width)
    page.locator(TEST_BUTTON).click()
    page.wait_for_url("**/setup/guest_link**")
    assert fits(page)
    foot_ok(page)
    shot(page, "guest_link", width)
    page.locator("button[value='done']").click()
    page.wait_for_url("**/setup/done**")
    card = page.locator("[data-ready-card]")
    assert card.is_visible()
    qr = page.locator(".ready-card-qr").bounding_box()
    assert qr and qr["width"] >= 120 and qr["x"] >= 0 and qr["x"] + qr["width"] <= width + 1
    assert fits(page)
    foot_ok(page)
    shot(page, "done", width)
    assert len(fake_client["made"]) >= 1


def live_host(live):  # noqa: F811
    from tests.test_police_letter_flow import _login

    return _login(USERNAME)


def test_back_from_police_leaves_without_a_dialog(live, fake_client):  # noqa: F811
    base = live.plain.split("/apartments")[0]
    apartment_id = new_property(live_host(live), "Back Check")
    page = live.open(390)
    page.goto(f"{base}/apartments/{apartment_id}/setup/calendar?lang=en")
    page.locator(SKIP).click()
    page.wait_for_url("**/setup/police**")
    paste_js(page)
    assert dialog_closed(page)
    page.locator(".setup-wizard-back").click()
    page.wait_for_url("**/setup/calendar**")
    assert dialog_closed(page)


def test_first_setup_editor_has_no_archive_row(live):  # noqa: F811
    base = live.plain.split("/apartments")[0]
    apartment_id = new_property(live_host(live), "Editor First")
    page = live.open(390)
    page.goto(f"{base}/apartments/{apartment_id}?view=settings&lang=en")
    assert page.locator("#sec-archive").count() == 0
    assert fits(page)
    shot(page, "editor-first-setup", 390)


def test_whole_walk_works_without_javascript(live, fake_client):  # noqa: F811
    base = live.plain.split("/apartments")[0]
    apartment_id = new_property(live_host(live), "No JS Walk")
    page = live.open(390, js=False)
    page.goto(f"{base}/apartments/{apartment_id}/setup/calendar?lang=en")
    page.locator(SKIP).click()
    page.wait_for_url("**/setup/police**")
    read = page.locator("[data-letter-read]")
    assert read.is_visible()
    page.fill("#letter_text", FULL_LETTER)
    with page.expect_response(lambda r: r.url.endswith("/police-letter")) as reply:
        read.click()
    assert reply.value.status == 422
    assert page.input_value("#uby_idub")
    assert re.search(r"/setup/police|police-letter", page.url)
    page.locator(TEST_BUTTON).click()
    page.wait_for_url("**/setup/guest_link**")
    page.locator("button[value='done']").click()
    page.wait_for_url("**/setup/done**")
    assert page.locator("[data-ready-card]").is_visible()
    assert fits(page)


def test_enter_in_a_police_box_runs_the_test_not_wait(live, fake_client):  # noqa: F811
    base = live.plain.split("/apartments")[0]
    apartment_id = new_property(live_host(live), "Enter Key")
    page = live.open(390)
    page.goto(f"{base}/apartments/{apartment_id}/setup/calendar?lang=en")
    page.locator(SKIP).click()
    page.wait_for_url("**/setup/police**")
    paste_js(page)
    page.fill("#uby_contact", "typed@example.test")
    with page.expect_response(lambda r: r.url.endswith("/test-connection")) as reply:
        page.press("#uby_contact", "Enter")
    assert reply.value.status == 303
    page.wait_for_url("**/setup/guest_link**")
    assert len(fake_client["made"]) >= 1
    row = db.query_one("SELECT uby_contact, uby_idub FROM apartment WHERE id = ?", (apartment_id,))
    assert row["uby_contact"] == "typed@example.test" and row["uby_idub"]
