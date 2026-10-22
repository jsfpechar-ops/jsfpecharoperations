"""The dashboard names a property whose police setup is unfinished, in one line (0241).

It used to list every missing field in a banner; the owner asked for one short
line and one button that opens the first missing field.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "dashboard-missing-banner-host"

COMPLETE_VALUES = {
    "uby_idub": "123456789012",
    "uby_mark": "AAKLI",
    "uby_name": "Banner Flat",
    "uby_ws_user": "uby-ws1a2b3c",
    "uby_ws_password_enc": db.encrypt_secret("ws-secret"),
    "addr_obec": "Praha",
    "addr_house_no": "12",
    "addr_zip": "12000",
}


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        apartment_ids = [
            row["id"]
            for row in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (user_id,))
        ]
        for apartment_id in apartment_ids:
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _owner_id():
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _insert_apartment(internal_name: str, **overrides) -> int:
    entity_id = db.insert(
        "legal_entity",
        {
            "name": f"{internal_name} s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@banner.test",
            "owner_user_id": _owner_id(),
            "created_at": db.utcnow(),
        },
    )
    payload = {
        "legal_entity_id": entity_id,
        "owner_user_id": _owner_id(),
        "internal_name": internal_name,
        "addr_obec": "Praha",
        "addr_house_no": "12",
        "addr_zip": "12000",
        "permalink_token": f"banner{internal_name.lower().replace(' ', '')}",
        "permalink_pin": "123456",
        "automation_mode": "manual",
        "submit_after_hours": 24,
        "active": 1,
        "created_at": db.utcnow(),
    }
    payload.update(overrides)
    return db.insert("apartment", payload)


def _setup_lines(text: str) -> list[str]:
    return re.findall(r'<li class="needs-you-item"[^>]*data-needs-you="setup"[^>]*>(.*?)</li>', text, re.S)


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Banner Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    client.post("/onboarding/dismiss", data={"return_to": "/"}, follow_redirects=False)
    try:
        yield client
    finally:
        _cleanup()


def test_one_short_line_opens_the_first_missing_police_field(host):
    apartment_id = _insert_apartment("Order Flat")

    page = host.get("/?lang=en")

    lines = _setup_lines(page.text)
    assert len(lines) == 1
    line = lines[0]
    assert "Order Flat" in line
    assert host_i18n.STRINGS["en"]["needs_you.setup"] in line
    assert f'href="/apartments/{apartment_id}?view=settings&amp;section=reporting#ubyport"' in line
    # The owner asked for no field-by-field list on the dashboard.
    assert "IDUB" not in line and "Password" not in line
    assert line.count('class="ui-btn') == 1


def test_no_line_when_reporting_is_ready(host):
    apartment_id = _insert_apartment("Ready Flat", **COMPLETE_VALUES)
    db.update("apartment", apartment_id, COMPLETE_VALUES)

    page = host.get("/?lang=en")

    assert _setup_lines(page.text) == []


def test_lines_past_the_fifth_wait_behind_show_more(host):
    for index in range(1, 7):
        _insert_apartment(f"Banner Flat {index}")

    page = host.get("/?lang=en")

    assert len(_setup_lines(page.text)) == 6
    assert "Show 1 more" in page.text
    before_more = page.text.split('class="needs-you-more"', 1)[0]
    assert len(_setup_lines(before_more)) == 5


def test_inactive_properties_are_omitted(host):
    _insert_apartment("Inactive Flat", active=0)

    page = host.get("/?lang=en")

    assert _setup_lines(page.text) == []


def test_the_setup_line_is_in_czech(host):
    _insert_apartment("Czech Flat")

    page = host.get("/?lang=cs")

    line = _setup_lines(page.text)[0]
    assert host_i18n.STRINGS["cs"]["needs_you.setup"] in line
    assert host_i18n.STRINGS["cs"]["needs_you.action.setup"] in line
