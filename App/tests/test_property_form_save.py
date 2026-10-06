"""Enter must save the property form, and the credentials test must not eat it.

Two data-loss paths sat on the primary setup task: the first submit button in
the form was "Test the connection", so pressing Enter in any field posted there
and dropped every edit, and clicking that button tested the *saved* credentials
while the values the host had just pasted from the police letter sat unused in
the form.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app import alerts, auth, db
from app.main import app
from tests.conftest import login_as

USERNAME = "property-form-host"


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


def _apartment():
    return db.query_one(
        "SELECT * FROM apartment WHERE owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?)",
        (USERNAME,),
    )


def _payload(**overrides):
    """The property form as a browser posts it."""
    data = {
        "internal_name": "Form Flat",
        "addr_city": "Praha",
        "addr_zip": "120 00",
        "uby_idub": "123456789012",
        "uby_mark": "abc",
        "uby_name": "Penzion Form",
        "uby_contact": "host@form.test",
        "uby_ws_user": "UBY-WSform",
        "permalink_window_days": "2",
        "permalink_reachback_days": "30",
        "active": "on",
    }
    data.update(overrides)
    return data


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Form Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    created = client.post(
        "/apartments", data=_payload(internal_name="Form Flat"), follow_redirects=False
    )
    assert created.status_code == 303, created.text
    try:
        yield client
    finally:
        _cleanup()


def _property_form(page_text: str, apartment_id: int) -> str:
    """The main property form only -- the page carries a language form too."""
    marker = f'action="/apartments/{apartment_id}"'
    assert marker in page_text, page_text[:400]
    start = page_text.rindex("<form", 0, page_text.index(marker))
    return page_text[start : page_text.index("</form>", start)]


def test_the_first_submit_button_saves_the_form(host):
    """Enter activates the first submit button, so it has to be Save.

    ``test_the_credentials_test_saves_what_the_host_typed`` cannot catch this:
    it posts to the test route by hand. Only the order of the buttons decides
    what a browser does when the host presses Enter in a text field.
    """
    apartment = _apartment()
    page = host.get(f"/apartments/{apartment['id']}")
    assert page.status_code == 200
    form = _property_form(page.text, apartment["id"])
    buttons = re.findall(r"<button[^>]*type=\"submit\"[^>]*>", form)
    assert buttons, "the form has no submit button"
    first = buttons[0]
    assert "formaction" not in first, f"Enter would leave the form: {first}"
    assert "hidden" in first
    assert 'tabindex="-1"' in first


def test_the_credentials_test_saves_what_the_host_typed(host, mock_ubyport):
    apartment = _apartment()
    assert db.decrypt_secret(apartment["uby_ws_password_enc"]) == ""

    response = host.post(
        f"/apartments/{apartment['id']}/test-connection",
        data=_payload(uby_ws_password="police-secret", internal_name="Renamed Flat"),
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "err=" not in response.headers["location"]

    saved = _apartment()
    assert saved["internal_name"] == "Renamed Flat", "the typed edits were dropped"
    assert db.decrypt_secret(saved["uby_ws_password_enc"]) == "police-secret"


def test_the_credentials_test_still_tests_the_saved_values(host, mock_ubyport):
    """The bare button posts nothing, so it must keep working as it did."""
    apartment = _apartment()
    response = host.post(
        f"/apartments/{apartment['id']}/test-connection", follow_redirects=False
    )
    assert response.status_code == 303
    assert "msg=" in response.headers["location"]
    assert "err=" not in response.headers["location"]


def test_the_button_says_it_saves_first(host):
    page = host.get(f"/apartments/{_apartment()['id']}")
    assert "Save and test connection" in page.text
    assert "Test the connection" not in page.text
    # The old hint told the host to save first, which is now what the button does.
    assert "save first" not in page.text


def test_the_edit_form_prefills_the_optional_texts(host):
    """The ternaries that prefill the textareas read value-or-empty only while
    editing; make the parenthesised intent stick."""
    apartment_id = _apartment()["id"]
    db.update(
        "apartment",
        apartment_id,
        {"guest_message": "Welcome to Form Flat.", "notes": "Two sets of keys."},
    )
    page = host.get(f"/apartments/{apartment_id}").text
    assert ">Welcome to Form Flat.</textarea>" in page
    assert ">Two sets of keys.</textarea>" in page


def _raise_auth_pause(apartment) -> None:
    alerts.raise_alert(
        "critical",
        "ubyport_auth_failed",
        "UbyPort refused the web-service login.",
        "HTTP 401",
        dedupe_key=f"ubyport_auth_failed:{apartment['id']}",
        apartment_id=apartment["id"],
    )


def test_an_unrelated_property_save_does_not_lift_the_auth_pause(host):
    """AR-18: the pause must not be lifted by a rename or an address edit.

    The pause exists so a refused police login is not retried every ten
    minutes; an unrelated save used to resume that retry storm.
    """
    apartment = _apartment()
    _raise_auth_pause(apartment)

    response = host.post(
        f"/apartments/{apartment['id']}",
        data=_payload(internal_name="Renamed Flat"),
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert alerts.open_alert(f"ubyport_auth_failed:{apartment['id']}") is not None, (
        "a property-details save is not new credentials"
    )


def test_a_new_password_lifts_the_auth_pause(host):
    apartment = _apartment()
    _raise_auth_pause(apartment)

    response = host.post(
        f"/apartments/{apartment['id']}",
        data=_payload(uby_ws_password="fresh-police-secret"),
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert alerts.open_alert(f"ubyport_auth_failed:{apartment['id']}") is None, (
        "replacing the password is the fix the pause waits for"
    )


def test_a_new_login_lifts_the_auth_pause(host):
    apartment = _apartment()
    _raise_auth_pause(apartment)

    response = host.post(
        f"/apartments/{apartment['id']}",
        data=_payload(uby_ws_user="UBY-WSreplacement"),
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    assert alerts.open_alert(f"ubyport_auth_failed:{apartment['id']}") is None
