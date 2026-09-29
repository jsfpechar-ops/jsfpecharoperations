"""The automation card has to say what is missing, and where to fix it.

A red "N to fix" pill named a number and nothing else, and some of the things it
counted (the address) are not even fields on this page, so the host had no way
to finish what the pill complained about. The card now lists each missing item
as a link to the field on the property form.

The credentials test on this page had a second problem: it saved the posted
values through the *property* payload, which the card does not post, so testing
the connection blanked the property's name, address and entity.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import alerts, auth, db
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "automation-missing-host"


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _owner_id():
    return db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )["id"]


def _apartment():
    return db.query_one(
        "SELECT * FROM apartment WHERE owner_user_id = ?", (_owner_id(),)
    )


def _payload(**overrides):
    """The automation card as a browser posts it: no name, no address, no entity."""
    data = {
        "automation_mode": "manual",
        "submit_after_hours": "24",
        "default_purpose": "10",
        "uby_idub": "",
        "uby_mark": "",
        "uby_name": "",
        "uby_contact": "",
        "uby_ws_user": "",
        "uby_ws_password": "",
        "return_to": "/automation",
        "form_source": "automation",
    }
    data.update(overrides)
    return data


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(USERNAME, PASSWORD, "Automation Host", must_change_password=False)
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Automation s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@automation.test",
            "owner_user_id": _owner_id(),
            "created_at": db.utcnow(),
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": _owner_id(),
            "internal_name": "Automation Flat",
            "addr_obec": "Praha",
            "addr_house_no": "12",
            "addr_zip": "12000",
            "permalink_token": "automationmissing1",
            "permalink_pin": "123456",
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
        },
    )
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    try:
        yield client, apartment_id
    finally:
        _cleanup()


def test_the_card_names_each_missing_item_instead_of_counting_it(host):
    client, apartment_id = host

    page = client.get("/automation?lang=en")

    assert page.status_code == 200
    assert "Still missing:" in page.text
    assert "IDUB" in page.text
    assert "to fix" not in page.text, "the count pill is back"


def test_each_missing_item_links_to_its_field_on_the_property_form(host):
    client, apartment_id = host

    page = client.get("/automation?lang=en")

    # IDUB, the abbreviation, the facility name, the login and the password are
    # all empty in the fixture, so all five have to be offered as links.
    for field in ("uby_idub", "uby_mark", "uby_name", "uby_ws_user", "uby_ws_password"):
        assert f'href="/apartments/{apartment_id}#{field}"' in page.text, field
    # The address is already complete, so it must not be offered.
    assert f'href="/apartments/{apartment_id}#addr_zip"' not in page.text


def test_a_complete_property_shows_ready_and_no_missing_list(host):
    client, apartment_id = host
    db.update(
        "apartment",
        apartment_id,
        {
            "uby_idub": "100227887600",
            "uby_mark": "CZGFW",
            "uby_name": "Automation Flat",
            "uby_contact": "host@automation.test",
            "uby_ws_user": "UBY-WS12cdef",
            "uby_ws_password_enc": db.encrypt_secret("ws-secret"),
        },
    )

    page = client.get("/automation?lang=en")

    assert "Ready" in page.text
    assert "Still missing:" not in page.text


def test_the_missing_items_are_named_in_czech(host):
    client, _apartment_id = host

    page = client.get("/automation?lang=cs")

    assert "Ještě chybí:" in page.text
    assert "Číslo popisné" not in page.text  # the address is complete


def test_the_missing_list_names_the_address_when_it_is_what_is_missing(host):
    client, apartment_id = host
    db.update("apartment", apartment_id, {"addr_zip": ""})

    page = client.get("/automation?lang=en")

    assert "Postcode" in page.text
    assert f'href="/apartments/{apartment_id}#addr_zip"' in page.text


def test_the_test_button_saves_the_card_and_not_the_property_payload(host, mock_ubyport):
    """The card posts no name or address, so the property payload blanked them."""
    client, apartment_id = host

    response = client.post(
        f"/apartments/{apartment_id}/test-connection",
        data=_payload(uby_idub="100227887600", uby_mark="CZGFW", uby_name="Automation Flat",
                      uby_ws_user="UBY-WS12cdef", uby_ws_password="ws-secret"),
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    saved = _apartment()
    assert saved["internal_name"] == "Automation Flat", "the test blanked the property name"
    assert saved["addr_obec"] == "Praha", "the test blanked the address"
    assert saved["legal_entity_id"], "the test detached the property manager"
    assert saved["uby_idub"] == "100227887600", "the typed credentials were not saved"
    assert db.decrypt_secret(saved["uby_ws_password_enc"]) == "ws-secret"


def test_the_test_button_still_saves_the_property_form(host, mock_ubyport):
    """The property form keeps its own payload; only the card carries the marker."""
    client, apartment_id = host

    response = client.post(
        f"/apartments/{apartment_id}/test-connection",
        data={
            "internal_name": "Renamed Automation Flat",
            "addr_obec": "Brno",
            "uby_idub": "100227887600",
            "return_to": f"/apartments/{apartment_id}",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    saved = _apartment()
    assert saved["internal_name"] == "Renamed Automation Flat"
    assert saved["addr_obec"] == "Brno"


def test_the_button_says_it_saves_first(host):
    client, _apartment_id = host

    page = client.get("/automation?lang=en")

    assert "Save and test connection" in page.text
    assert "Test connection" not in page.text
    assert "Save first if you changed them" in page.text


def _raise_auth_pause(apartment_id: int) -> None:
    alerts.raise_alert(
        "critical",
        "ubyport_auth_failed",
        "UbyPort refused the web-service login.",
        "HTTP 401",
        dedupe_key=f"ubyport_auth_failed:{apartment_id}",
        apartment_id=apartment_id,
    )


def test_saving_the_automation_card_does_not_lift_the_auth_pause(host):
    """AR-18: switching mode or review hours is not new credentials."""
    client, apartment_id = host
    _raise_auth_pause(apartment_id)

    response = client.post(
        f"/automation/{apartment_id}",
        data=_payload(automation_mode="scheduled"),
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert alerts.open_alert(f"ubyport_auth_failed:{apartment_id}") is not None, (
        "an unrelated automation save must not resume the refused-login retries"
    )


def test_new_automation_credentials_lift_the_auth_pause(host):
    client, apartment_id = host
    _raise_auth_pause(apartment_id)

    response = client.post(
        f"/automation/{apartment_id}",
        data=_payload(uby_ws_password="fresh-police-secret"),
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert alerts.open_alert(f"ubyport_auth_failed:{apartment_id}") is None
