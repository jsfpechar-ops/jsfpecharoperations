"""Copy settings from another property on the apartment form."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

USERNAME = "copy-property-host"
OTHER_USERNAME = "copy-property-other"


def _cleanup() -> None:
    for username in (USERNAME, OTHER_USERNAME):
        user = db.query_one(
            "SELECT id FROM user_account WHERE username = ?", (username,)
        )
        if not user:
            continue
        owner_id = user["id"]
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _form_data(**overrides):
    data = {
        "internal_name": "Target flat",
        "city_en": "",
        "addr_okres": "",
        "addr_obec": "",
        "addr_obec_cast": "",
        "addr_street": "",
        "addr_house_no": "",
        "addr_orient_no": "",
        "addr_zip": "",
        "uby_idub": "",
        "uby_mark": "",
        "uby_name": "",
        "uby_contact": "",
        "uby_ws_user": "",
        "guest_message": "",
        "notes": "",
        "legal_entity_id": "",
        "data_controller_entity_id": "",
        "permalink_window_days": "2",
        "permalink_reachback_days": "365",
        "passport_photo_policy": "off",
        "active": "on",
    }
    data.update(overrides)
    return data


@pytest.fixture
def host_pair():
    db.init_db()
    _cleanup()
    owner_id = auth.create_account(
        f"{USERNAME}@example.test", "Copy property host", username=USERNAME
    )
    other_id = auth.create_account(
        f"{OTHER_USERNAME}@example.test", "Other host", username=OTHER_USERNAME
    )
    entity_id = db.insert(
        "legal_entity",
        {
            "owner_user_id": owner_id,
            "name": "Operator A",
            "created_at": db.utcnow(),
        },
    )
    controller_id = db.insert(
        "legal_entity",
        {
            "owner_user_id": owner_id,
            "name": "Controller B",
            "created_at": db.utcnow(),
        },
    )
    source_id = db.insert(
        "apartment",
        {
            "owner_user_id": owner_id,
            "internal_name": "Source flat",
            "legal_entity_id": entity_id,
            "data_controller_entity_id": controller_id,
            "automation_mode": "scheduled",
            "submit_after_hours": 12,
            "default_purpose": "20",
            "permalink_window_days": 5,
            "permalink_reachback_days": 180,
            "stay_fee_rate_czk": 21,
            "stay_fee_cadence": "quarterly",
            "stay_fee_vs": "1234567890",
            "stay_fee_council_account": "123456/0100",
            "stay_fee_authority_name": "City office",
            "addr_obec": "Brno",
            "addr_house_no": "12",
            "uby_idub": "IDUB-SOURCE",
            "uby_mark": "MARK1",
            "uby_name": "Source facility",
            "uby_ws_user": "ws-source",
            "uby_ws_password_enc": db.encrypt_secret("secret-source"),
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": auth.new_permalink_pin(),
            "created_at": db.utcnow(),
            "active": 1,
        },
    )
    target_id = db.insert(
        "apartment",
        {
            "owner_user_id": owner_id,
            "internal_name": "Target flat",
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": auth.new_permalink_pin(),
            "created_at": db.utcnow(),
            "active": 1,
        },
    )
    foreign_id = db.insert(
        "apartment",
        {
            "owner_user_id": other_id,
            "internal_name": "Foreign flat",
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": auth.new_permalink_pin(),
            "created_at": db.utcnow(),
            "active": 1,
        },
    )
    client = TestClient(app)
    login = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert login.status_code == 303, login.text
    try:
        yield client, source_id, target_id, foreign_id, entity_id, controller_id
    finally:
        _cleanup()


def test_allowed_settings_are_copied_on_edit(host_pair):
    client, source_id, target_id, _foreign_id, entity_id, controller_id = host_pair
    page = client.get(f"/apartments/{target_id}?copy_from={source_id}&lang=en")
    assert page.status_code == 200
    text = page.text
    assert "Copied from Source flat" in text
    assert f'<option value="{entity_id}"' in text and "selected" in text
    assert f'<option value="{controller_id}"' in text and "selected" in text
    assert 'name="automation_mode"' not in text  # edit shows automation summary only
    assert 'name="stay_fee_rate_czk"' in text
    assert 'value="21"' in text
    assert "City office" in text
    assert 'name="account_number"' in text
    assert "123456" in text
    assert "IDUB-SOURCE" not in text
    assert "MARK1" not in text
    assert "ws-source" not in text
    assert "Brno" not in text
    assert 'id="stay_fee_vs"' in text
    assert 'name="stay_fee_vs"' in text and 'value="1234567890"' not in text


def test_new_property_form_shows_copy_select_and_prefills_automation(host_pair):
    client, source_id, _target_id, _foreign_id, entity_id, _controller_id = host_pair
    page = client.get(f"/apartments/new?copy_from={source_id}&lang=en")
    assert page.status_code == 200
    assert 'name="copy_from"' in page.text
    assert f'<option value="{source_id}"' in page.text
    assert f'<option value="{entity_id}"' in page.text
    assert 'value="scheduled"' in page.text or "scheduled" in page.text
    assert 'name="submit_after_hours"' in page.text
    assert 'value="12"' in page.text
    assert 'id="stay-fee-settings"' in page.text


def test_foreign_copy_from_returns_404(host_pair):
    client, _source_id, target_id, foreign_id, *_ = host_pair
    assert (
        client.get(f"/apartments/{target_id}?copy_from={foreign_id}&lang=en").status_code
        == 404
    )
    assert client.get(f"/apartments/new?copy_from={foreign_id}&lang=en").status_code == 404


def test_single_property_host_sees_no_copy_select():
    db.init_db()
    _cleanup()
    auth.create_account(
        f"{USERNAME}@example.test", "Solo host", username=USERNAME
    )
    client = TestClient(app)
    login = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert login.status_code == 303
    db.insert(
        "apartment",
        {
            "owner_user_id": db.query_one(
                "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
            )["id"],
            "internal_name": "Only flat",
            "permalink_token": auth.new_permalink_token(),
            "permalink_pin": auth.new_permalink_pin(),
            "created_at": db.utcnow(),
            "active": 1,
        },
    )
    apartment_id = db.query_one(
        "SELECT id FROM apartment WHERE internal_name = ?", ("Only flat",)
    )["id"]
    new_page = client.get("/apartments/new?lang=en")
    edit_page = client.get(f"/apartments/{apartment_id}?lang=en")
    assert 'name="copy_from"' in new_page.text
    assert 'name="copy_from"' not in edit_page.text
    _cleanup()
