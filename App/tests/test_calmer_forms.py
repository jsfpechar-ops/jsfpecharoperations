"""Calmer property and guest forms: more-options, defaults, operator pick."""
from __future__ import annotations

import re
from datetime import timedelta
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app import auth, claim, db, host_i18n
from app.main import app
from tests.conftest import complete_guest_claim, login_as

USERNAME = "calmer-forms-host"
GUEST_TOKEN = "calmer-guest-token"
SIGNATURE = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


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
            db.execute("DELETE FROM guest WHERE reservation_id IN "
                       "(SELECT id FROM reservation WHERE apartment_id = ?)", (apartment_id,))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _owner_id():
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _new_payload(**overrides):
    data = {
        "internal_name": "Calmer Flat",
        "addr_obec": "Praha",
        "addr_house_no": "12",
        "addr_zip": "12000",
        "active": "on",
        "automation_mode": "manual",
        "submit_after_hours": "24",
        "default_purpose": "10",
    }
    data.update(overrides)
    return data


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Calmer Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    try:
        yield client
    finally:
        _cleanup()


def _more_options_tag(page: str) -> str:
    match = re.search(r"<details class=\"more-options\"[^>]*>", page)
    assert match, "expected a more-options block"
    return match.group(0)


def test_new_property_form_has_no_folded_options(host):
    """0092: nothing on the short create page is hidden behind More options."""
    page = host.get("/apartments/new?lang=en").text
    assert '<details class="more-options"' not in page
    assert 'id="automation_mode"' not in page
    assert 'id="internal_name"' in page and 'id="addr_zip"' in page


def test_more_options_open_when_controller_still_missing(host):
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Solo Operator s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "",
            "owner_user_id": _owner_id(),
            "created_at": db.utcnow(),
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": _owner_id(),
            "internal_name": "Open More Flat",
            "permalink_token": "calmeropen1",
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    # 0094: guest-link settings are always visible; a missing controller is a
    # visible Setup checklist item linking to the field that answers it.
    page = host.get(f"/apartments/{apartment_id}?lang=en").text
    assert '<details class="more-options"' not in page
    assert 'id="permalink_window_days"' in page
    assert '<a href="#basics">' in page


def test_one_operator_posts_legal_entity_and_saves(host):
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Only Operator s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "solo@example.test",
            "owner_user_id": _owner_id(),
            "created_at": db.utcnow(),
        },
    )
    page = host.get("/apartments/new?lang=en").text
    assert 'name="legal_entity_id"' in page
    assert "Only Operator" in page
    # 0088: one visible control, the sole operator chosen, no empty choice.
    assert page.count('name="legal_entity_id"') == 1
    assert f'<option value="{entity_id}" selected>' in page
    assert '(none)' not in page
    response = host.post(
        "/apartments",
        data=_new_payload(legal_entity_id=str(entity_id)),
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.query_one(
        "SELECT legal_entity_id FROM apartment WHERE owner_user_id = ? ORDER BY id DESC LIMIT 1",
        (_owner_id(),),
    )
    assert row["legal_entity_id"] == entity_id


def test_two_operators_show_the_entity_select(host):
    for name in ("Operator A", "Operator B"):
        db.insert(
            "legal_entity",
            {
                "name": name,
                "seat": "Praha",
                "ico": "12345678",
                "contact_email": f"{name.lower().replace(' ', '')}@example.test",
                "owner_user_id": _owner_id(),
                "created_at": db.utcnow(),
            },
        )
    page = host.get("/apartments/new?lang=en").text
    assert 'id="legal_entity_id"' in page
    assert "operator-only-line" not in page


def _operator_id():
    return db.insert(
        "legal_entity",
        {"name": "Message Operator", "owner_user_id": _owner_id(), "created_at": db.utcnow()},
    )


def test_create_with_blank_guest_message_stores_default(host):
    response = host.post(
        "/apartments",
        data=_new_payload(guest_message="", legal_entity_id=str(_operator_id())),
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.query_one(
        "SELECT guest_message FROM apartment WHERE owner_user_id = ? ORDER BY id DESC LIMIT 1",
        (_owner_id(),),
    )
    assert row["guest_message"] == host_i18n.STRINGS["en"]["apartment.form.guest_message.default"]


def test_update_with_blank_guest_message_stores_blank(host):
    operator = str(_operator_id())
    created = host.post(
        "/apartments",
        data=_new_payload(guest_message="Keep me", legal_entity_id=operator),
        follow_redirects=False,
    )
    path = urlparse(created.headers["location"]).path
    apartment_id = int(path.rstrip("/").split("/")[-1])
    host.post(
        f"/apartments/{apartment_id}",
        data=_new_payload(guest_message="", internal_name="Calmer Flat", legal_entity_id=operator),
        follow_redirects=False,
    )
    row = db.query_one("SELECT guest_message FROM apartment WHERE id = ?", (apartment_id,))
    assert row["guest_message"] == ""


def _guest_stay():
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Guest Entity",
            "created_at": now,
            "owner_user_id": _owner_id(),
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": _owner_id(),
            "internal_name": "Guest Flat",
            "permalink_token": GUEST_TOKEN,
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    stay_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "manual",
            "uid": "calmer-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=2)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return stay_id


def _res_country_selected(page: str, code: str) -> bool:
    return bool(
        re.search(
            rf'<option value="{code}"[^>]*selected',
            page,
        )
    )


def test_guest_residence_follows_nationality_when_empty(host):
    stay_id = _guest_stay()
    client = TestClient(app)
    complete_guest_claim(client, GUEST_TOKEN, stay_id)
    today = claim.prague_today()
    response = client.post(
        f"/l/{GUEST_TOKEN}/{stay_id}/save",
        params={"lang": "en"},
        data={
            "stay_from": today.isoformat(),
            "stay_to": (today + timedelta(days=2)).isoformat(),
            "party_size": "1",
            "nationality": "DEU",
            "res_country": "",
            "first_name": "Anna",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert _res_country_selected(response.text, "DEU")


def test_saved_residence_is_not_replaced_by_nationality(host):
    stay_id = _guest_stay()
    client = TestClient(app)
    complete_guest_claim(client, GUEST_TOKEN, stay_id)
    today = claim.prague_today()
    response = client.post(
        f"/l/{GUEST_TOKEN}/{stay_id}/save",
        params={"lang": "en"},
        data={
            "stay_from": today.isoformat(),
            "stay_to": (today + timedelta(days=2)).isoformat(),
            "party_size": "1",
            "nationality": "DEU",
            "res_country": "AUT",
            "first_name": "Anna",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert _res_country_selected(response.text, "AUT")
