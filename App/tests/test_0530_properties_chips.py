"""0530: the Properties list is one table with four setup chips per property."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as
from tests.test_properties_table_chips import USERNAME, _cleanup

CHIP = re.compile(r'data-setup-chip="(\w+)" data-state="(\w+)" href="([^"]+)"')


@pytest.fixture
def clean():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


COMPLETE_UBY = {
    "uby_idub": "123456789012",
    "uby_mark": "AAKLI",
    "uby_name": "Vinohrady Flat",
    "uby_ws_user": "uby-ws1a2b3c",
    "uby_ws_password_enc": db.encrypt_secret("ws-secret"),
}


def _seed(*, lock=False, fee=False, feed_status=None, auth_alert=False, police=False, manual_stay=False) -> None:
    auth.create_account(f"{USERNAME}@example.test", "Properties Host", username=USERNAME)
    owner_id = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Properties s.r.o.", "seat": "Praha", "ico": "12345678",
            "contact_email": "host@properties.test", "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id, "owner_user_id": owner_id, "internal_name": "Flat chips",
            "addr_obec": "Praha", "addr_house_no": "1", "addr_zip": "12000",
            "permalink_token": "chips0530", "permalink_pin": "123456", "automation_mode": "manual",
            "submit_after_hours": 24, "active": 1, "created_at": db.utcnow(),
            "lock_id": "lock-0530" if lock else None,
            "stay_fee_rate_czk": 50 if fee else 0,
            **(COMPLETE_UBY if police else {}),
        },
    )
    if feed_status is not None:
        db.insert(
            "ical_feed",
            {
                "apartment_id": apartment_id, "label": "Booking", "url": "https://example.test/cal.ics",
                "active": 1, "last_status": feed_status, "created_at": db.utcnow(),
            },
        )
    if auth_alert:
        db.insert(
            "alert",
            {
                "level": "error", "kind": "ubyport_auth_failed", "apartment_id": apartment_id,
                "owner_user_id": owner_id, "message": "UbyPort sign-in failed", "created_at": db.utcnow(),
            },
        )
    if manual_stay:
        db.insert(
            "reservation",
            {
                "apartment_id": apartment_id, "source": "manual", "uid": "manual-0530",
                "date_from": "2026-12-01", "date_to": "2026-12-03", "status": "active",
                "created_at": db.utcnow(), "updated_at": db.utcnow(),
            },
        )


def _page(**kwargs) -> str:
    _seed(**kwargs)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    page = client.get("/apartments?lang=en")
    assert page.status_code == 200
    return page.text


def _chips(page: str) -> dict:
    return {m.group(1): (m.group(2), m.group(3)) for m in CHIP.finditer(page)}


def test_bare_property_shows_missing_and_unused_chips(clean):
    page = _page()
    chips = _chips(page)
    assert set(chips) == {"police", "calendar", "lock", "fee"}
    assert chips["police"][0] == "bad"
    assert chips["calendar"][0] == "bad"
    assert chips["lock"][0] == "off"
    assert chips["fee"][0] == "off"
    assert chips["police"][1].endswith("#ubyport")
    assert chips["calendar"][1].endswith("#calendars")
    assert chips["lock"][1].endswith("#basics")
    assert chips["fee"][1].endswith("#stay-fee-settings")
    assert "property-summaries" not in page


def test_configured_property_shows_done_chips(clean):
    chips = _chips(_page(lock=True, fee=True, feed_status="ok"))
    assert chips["calendar"][0] == "ok"
    assert chips["lock"][0] == "ok"
    assert chips["fee"][0] == "ok"
    assert chips["lock"][1].endswith("#door-code")


def test_complete_ubyport_and_address_mark_police_done(clean):
    chips = _chips(_page(police=True))
    assert chips["police"][0] == "ok"


def test_open_auth_alert_marks_police_missing(clean):
    chips = _chips(_page(lock=True, fee=True, feed_status="ok", auth_alert=True))
    assert chips["police"][0] == "bad"


def test_feed_error_marks_calendar_missing(clean):
    chips = _chips(_page(lock=True, fee=True, feed_status="error"))
    assert chips["calendar"][0] == "bad"


def test_manual_stay_without_feed_marks_calendar_not_used(clean):
    chips = _chips(_page(manual_stay=True))
    assert chips["calendar"][0] == "off"


def test_no_feed_and_no_manual_stay_marks_calendar_missing(clean):
    chips = _chips(_page())
    assert chips["calendar"][0] == "bad"


def test_app2_phone_missing_status_uses_bad_token_not_brand():
    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app2.css").read_text(encoding="utf-8")
    rule = re.search(r"body\.v2 \.props-phone \.st\.r\{([^}]*)\}", css)
    assert rule is not None
    assert "var(--bad)" in rule.group(1)
    assert "var(--acc-text)" not in rule.group(1)


PHONE_CARD = re.compile(r'<a class="card prop" href="([^"]+)">(.*?)</a>', re.S)


def test_phone_cards_one_per_property_with_one_status_line(clean):
    # 0533: below 1024 px each property is one mockup card (a link) with one status line
    # 0740: the phone card shows one status line (g = ready, r = missing), not four chips.
    page = _page()
    cards = PHONE_CARD.findall(page)
    assert len(cards) == 1
    href, body = cards[0]
    assert href.startswith("/apartments/")
    assert f'data-href="{href}"' in page
    assert len(re.findall(r'<span class="st (?:g|r)">', body)) == 1
