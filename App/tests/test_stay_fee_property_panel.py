"""Host-only stay-fee property settings."""
from __future__ import annotations

from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app
from tests.conftest import login_as

USERNAME = "stay-fee-panel-host"


def _cleanup() -> None:
    user = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )
    if not user:
        return
    owner_id = user["id"]
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))


def _form_data(**overrides):
    data = {
        "internal_name": "Panel Test Flat",
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
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Stay fee test host", username=USERNAME)
    client = TestClient(app)
    login = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert login.status_code == 303, login.text
    created = client.post(
        "/apartments",
        data=_form_data(),
        follow_redirects=False,
    )
    assert created.status_code == 303, created.text
    owner_id = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )["id"]
    apartment_id = db.query_one(
        "SELECT id FROM apartment WHERE owner_user_id = ?", (owner_id,)
    )["id"]
    try:
        yield client, apartment_id, owner_id
    finally:
        _cleanup()


def _stay_fee_data(**overrides):
    data = {
        "stay_fee_rate_czk": "0",
        "stay_fee_cadence": "monthly",
        "stay_fee_vs": "",
        "stay_fee_council_account": "",
        "stay_fee_authority_name": "",
        "stay_fee_authority_address": "",
        "stay_fee_authority_contact": "",
        "stay_fee_payee": "",
        "stay_fee_instruction": "",
    }
    data.update(overrides)
    return data


def test_edit_page_has_stay_fee_panel_and_create_page_does_not(host):
    client, apartment_id, _owner_id = host

    edit = client.get(f"/apartments/{apartment_id}?lang=en")
    create = client.get("/apartments/new?lang=en")

    assert edit.status_code == 200
    assert '<details class="panel property-section" id="stay-fee-settings"' in edit.text
    assert 'href="#stay-fee-settings"' in edit.text
    assert 'Optional stay fee' in edit.text
    assert create.status_code == 200
    assert 'id="stay-fee-settings"' not in create.text
    assert 'href="#stay-fee-settings"' not in create.text


@pytest.mark.parametrize(("raw_rate", "expected_rate"), [("75", 50), ("abc", 0)])
def test_rate_is_clamped_and_invalid_text_turns_it_off(host, raw_rate, expected_rate):
    client, apartment_id, _owner_id = host
    response = client.post(
        f"/apartments/{apartment_id}",
        data=_form_data(**_stay_fee_data(stay_fee_rate_czk=raw_rate)),
        follow_redirects=False,
    )

    assert response.status_code == 303
    saved = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    assert saved["stay_fee_rate_czk"] == expected_rate


def test_variable_symbol_keeps_only_digits(host):
    client, apartment_id, _owner_id = host
    response = client.post(
        f"/apartments/{apartment_id}",
        data=_form_data(**_stay_fee_data(stay_fee_vs="12 34-56")),
        follow_redirects=False,
    )

    assert response.status_code == 303
    saved = db.query_one("SELECT stay_fee_vs FROM apartment WHERE id = ?", (apartment_id,))
    assert saved["stay_fee_vs"] == "123456"


def test_account_is_normalised_and_invalid_account_saves_nothing(host):
    client, apartment_id, _owner_id = host
    valid = client.post(
        f"/apartments/{apartment_id}",
        data=_form_data(
            **_stay_fee_data(
                stay_fee_rate_czk="25",
                stay_fee_vs="1234",
                stay_fee_authority_name="Council office",
                stay_fee_council_account="19-2000781379/0800",
            )
        ),
        follow_redirects=False,
    )
    assert valid.status_code == 303
    saved = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    assert saved["stay_fee_council_account"] == "19-2000781379/0800"
    assert saved["stay_fee_council_iban"] == "CZ3008000000192000781379"

    invalid = client.post(
        f"/apartments/{apartment_id}",
        data=_form_data(
            internal_name="Must not be saved",
            **_stay_fee_data(
                stay_fee_rate_czk="49",
                stay_fee_vs="9876",
                stay_fee_authority_name="Changed office",
                stay_fee_council_account="not-an-account",
            ),
        ),
        follow_redirects=False,
    )
    assert invalid.status_code == 303
    assert "#stay-fee-settings" in invalid.headers["location"]
    assert "Enter a valid Czech bank account or IBAN." in unquote(
        invalid.headers["location"]
    )
    unchanged = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    assert unchanged["internal_name"] == "Panel Test Flat"
    assert unchanged["stay_fee_rate_czk"] == 25
    assert unchanged["stay_fee_vs"] == "1234"
    assert unchanged["stay_fee_authority_name"] == "Council office"
    assert unchanged["stay_fee_council_account"] == "19-2000781379/0800"
    assert unchanged["stay_fee_council_iban"] == "CZ3008000000192000781379"


def test_post_without_stay_fee_fields_keeps_stored_values(host):
    client, apartment_id, _owner_id = host
    db.update(
        "apartment",
        apartment_id,
        {
            "stay_fee_rate_czk": 25,
            "stay_fee_cadence": "quarterly",
            "stay_fee_vs": "123456",
            "stay_fee_council_account": "19-2000781379/0800",
            "stay_fee_council_iban": "CZ3008000000192000781379",
            "stay_fee_authority_name": "Council office",
            "stay_fee_authority_address": "Town Hall",
            "stay_fee_authority_contact": "office@example.test",
            "stay_fee_payee": "Municipality",
            "stay_fee_instruction": "Send by post",
        },
    )

    response = client.post(
        f"/apartments/{apartment_id}",
        data=_form_data(internal_name="Updated without fee fields"),
        follow_redirects=False,
    )

    assert response.status_code == 303
    saved = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    assert saved["internal_name"] == "Updated without fee fields"
    assert (
        saved["stay_fee_rate_czk"],
        saved["stay_fee_cadence"],
        saved["stay_fee_vs"],
        saved["stay_fee_council_account"],
        saved["stay_fee_council_iban"],
        saved["stay_fee_authority_name"],
        saved["stay_fee_authority_address"],
        saved["stay_fee_authority_contact"],
        saved["stay_fee_payee"],
        saved["stay_fee_instruction"],
    ) == (
        25,
        "quarterly",
        "123456",
        "19-2000781379/0800",
        "CZ3008000000192000781379",
        "Council office",
        "Town Hall",
        "office@example.test",
        "Municipality",
        "Send by post",
    )


def test_fee_template_peers_excludes_current_and_zero_rate_properties(host):
    client, apartment_id, owner_id = host
    now = db.utcnow()
    peer_id = db.insert(
        "apartment",
        {
            "internal_name": "Fee Template Peer",
            "owner_user_id": owner_id,
            "stay_fee_rate_czk": 12,
            "created_at": now,
        },
    )
    zero_rate_id = db.insert(
        "apartment",
        {
            "internal_name": "Fee Disabled Peer",
            "owner_user_id": owner_id,
            "stay_fee_rate_czk": 0,
            "created_at": now,
        },
    )

    page = client.get(f"/apartments/{apartment_id}?lang=en")

    assert page.status_code == 200
    assert f'<option value="{peer_id}"' in page.text
    assert f'<option value="{apartment_id}"' not in page.text
    assert f'<option value="{zero_rate_id}"' not in page.text


def test_missing_fee_details_warning_shows_for_enabled_rate_without_vs(host):
    client, apartment_id, _owner_id = host
    db.update(
        "apartment",
        apartment_id,
        {
            "stay_fee_rate_czk": 25,
            "stay_fee_vs": None,
            "stay_fee_council_account": None,
            "stay_fee_authority_name": None,
        },
    )

    page = client.get(f"/apartments/{apartment_id}?lang=en")

    assert page.status_code == 200
    assert (
        "Add the variable symbol, the council account and the office name to create "
        "the report and the payment QR."
    ) in page.text
