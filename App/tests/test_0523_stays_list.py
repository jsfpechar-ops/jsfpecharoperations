"""0523: the stays list columns, the guest name, the deadline badge, the payment preselect and the housebook link."""
from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as
from tests.test_host_stay_actions_browser import (  # noqa: F401  (fixtures)
    _browser, stay_actions_base, stay_actions_host,
)
from tests.test_signed_in_chrome import USERNAME, empty_host, host_with_property  # noqa: F401

_OTHER = "0523-other-owner"
EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "tasks" / "screenshots-0523"
CAPTURE = os.environ.get("UBYHOST_CAPTURE_0523") == "1"


def _owner_id() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _apartment_id() -> int:
    return db.query_one(
        "SELECT id FROM apartment WHERE owner_user_id = ? AND internal_name = ?",
        (_owner_id(), "Chrome Flat"),
    )["id"]


def _reservation(apartment_id: int, uid: str, date_from: str, date_to: str, status: str = "active") -> int:
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": uid,
            "date_from": date_from,
            "date_to": date_to,
            "status": status,
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )


def _guest(reservation_id: int, first_name: str, surname: str) -> None:
    now = db.utcnow()
    db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "is_lead": 1,
            "first_name": first_name,
            "surname": surname,
            "created_at": now,
            "updated_at": now,
        },
    )


def _clean_other_owner() -> None:
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (_OTHER,))
    if not row:
        return
    owner_id = row["id"]
    db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _row(page: str, reservation_id: int) -> str:
    start = page.index(f'data-href="/reservations/{reservation_id}?return_to=')
    start = page.rfind("<tr", 0, start)
    return page[start : page.index("</tr>", start)]


def test_the_headers_are_in_order_guest_property_arrival_departure_reporting(host_with_property):
    stay = _reservation(_apartment_id(), "0523-order", "2026-09-20", "2026-09-22")
    _guest(stay, "Sofia", "Costa")
    page = host_with_property.get("/reservations?range=all&lang=en").text
    thead = page[page.index("<thead>") : page.index("</thead>")]
    assert len(re.findall(r"<th[\s>]", thead)) == 6
    assert [x.strip() for x in re.findall(r"<th>(?:<span[^>]*>)?([^<]*)", thead)][:5] == [
        "Guest",
        "Property",
        "Arrival",
        "Departure",
        "Reporting",
    ]


def test_a_row_shows_the_lead_guest_and_the_property_column(host_with_property):
    stay = _reservation(_apartment_id(), "0523-lead", "2026-09-20", "2026-09-22")
    _guest(stay, "Sofia", "Costa")
    page = host_with_property.get("/reservations?range=all&lang=en").text
    row = _row(page, stay)
    assert "Sofia Costa" in row
    assert re.search(r'<td data-card="meta"[^>]*>\s*Chrome Flat\s*</td>', row)


def test_a_stay_without_guests_shows_the_no_name_text(host_with_property):
    stay = _reservation(_apartment_id(), "0523-noname", "2026-10-03", "2026-10-05")
    page = host_with_property.get("/reservations?range=all&lang=en").text
    assert "No name yet" in _row(page, stay)


def test_an_active_stay_still_shows_the_deadline_badge(host_with_property):
    stay = _reservation(_apartment_id(), "0523-deadline", "2026-10-10", "2026-10-12")
    page = host_with_property.get("/reservations?range=all&lang=en").text
    assert "data-deadline=" in _row(page, stay)


def test_the_payment_link_preselects_the_stay(host_with_property):
    stay = _reservation(_apartment_id(), "0523-pay", "2026-10-20", "2026-10-22")
    page = host_with_property.get("/reservations?range=all&lang=en").text
    assert re.search(rf'<a class="row-menu-item" href="/payments\?reservation_id={stay}#new-request" role="menuitem">', _row(page, stay))

    payments = host_with_property.get(f"/payments?reservation_id={stay}&lang=en").text
    assert re.search(rf'<option value="{stay}"\s+selected>', payments)


def test_another_owners_stay_preselects_nothing(host_with_property):
    _clean_other_owner()
    try:
        other_id = auth.create_account(f"{_OTHER}@example.test", "Other Host", role="host", username=_OTHER)
        entity = db.insert(
            "legal_entity",
            {"name": "Other entity", "owner_user_id": other_id, "created_at": db.utcnow()},
        )
        other_apartment = db.insert(
            "apartment",
            {
                "legal_entity_id": entity,
                "owner_user_id": other_id,
                "internal_name": "Other flat",
                "permalink_token": "0523-other-flat",
                "permalink_pin": "1234",
                "automation_mode": "manual",
                "submit_after_hours": 24,
                "permalink_window_days": 3,
                "default_purpose": "10",
                "active": 1,
                "created_at": db.utcnow(),
            },
        )
        foreign = _reservation(other_apartment, "0523-foreign", "2026-10-25", "2026-10-26")
        payments = host_with_property.get(f"/payments?reservation_id={foreign}&lang=en").text
        assert not re.search(rf'<option value="{foreign}"[^>]*selected', payments)
        assert "selected" not in payments.split('name="reservation_id"', 1)[1].split("</select>", 1)[0]
        # A non-numeric value is ignored too.
        odd = host_with_property.get("/payments?reservation_id=abc&lang=en").text
        assert "selected" not in odd.split('name="reservation_id"', 1)[1].split("</select>", 1)[0]
    finally:
        _clean_other_owner()


def test_the_header_housebook_link_points_at_the_csv(host_with_property):
    _reservation(_apartment_id(), "0523-housebook", "2026-10-28", "2026-10-29")
    page = host_with_property.get("/reservations?range=all&lang=en").text
    assert re.search(r'<a [^>]*href="/housebook\.csv\?[^"]*"[^>]*data-stays-housebook', page)


def test_capture_stays_list_screenshots(stay_actions_host, stay_actions_base):
    """Writes docs/tasks/screenshots-0523 only when UBYHOST_CAPTURE_0523=1; overflow is checked by the layout tests."""
    from playwright.sync_api import sync_playwright

    cookie = stay_actions_host["client"].cookies.get(auth.SESSION_COOKIE)
    with sync_playwright() as playwright:
        browser = _browser(playwright)
        for width in (1280, 390):
            context = browser.new_context(viewport={"width": width, "height": 900})
            context.add_cookies([{"name": auth.SESSION_COOKIE, "value": cookie, "url": stay_actions_base + "/"}])
            page = context.new_page()
            page.goto(f"{stay_actions_base}/reservations?range=all&lang=cs")
            page.wait_for_load_state("networkidle")
            later = page.locator("#security-prompt [data-security-prompt-later]")
            if later.is_visible():
                later.click()
            assert page.locator(".stays-desk").count() == 1, width
            if CAPTURE:
                EVIDENCE.mkdir(parents=True, exist_ok=True)
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(EVIDENCE / f"reservations-cs-{width}.png"), full_page=True)
            context.close()
        browser.close()
