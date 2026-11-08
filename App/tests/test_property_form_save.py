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


def _operator_id() -> str:
    """0088: the host's operator, created on first use."""
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not owner:
        return ""
    row = db.query_one("SELECT id FROM legal_entity WHERE owner_user_id = ? ORDER BY id LIMIT 1", (owner["id"],))
    if row:
        return str(row["id"])
    return str(db.insert("legal_entity", {"name": "Form Operator", "owner_user_id": owner["id"], "created_at": db.utcnow()}))


def _payload(**overrides):
    """The property form as a browser posts it."""
    data = {
        "internal_name": "Form Flat",
        "addr_city": "Praha",
        "addr_obec": "Praha",
        "addr_street": "Synthetic",
        "addr_house_no": "12",
        "addr_zip": "120 00",
        "uby_idub": "123456789012",
        "uby_mark": "abc",
        "uby_name": "Penzion Form",
        "uby_contact": "host@form.test",
        "uby_ws_user": "UBY-WSform",
        "permalink_window_days": "2",
        "permalink_reachback_days": "30",
        "legal_entity_id": _operator_id(),
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


def test_the_scan_switch_is_saved_off_without_the_upload(host):
    """0834: with passport upload off, saving forces the scan switch off."""
    apartment = _apartment()
    saved = host.post(
        f"/apartments/{apartment['id']}",
        data=_payload(passport_photo_policy="off", ocr_scan="1"),
        follow_redirects=False,
    )
    assert saved.status_code == 303, saved.text
    assert _apartment()["ocr_scan"] == 1


def test_the_scan_switch_is_saved_on_with_the_upload(host):
    """0834: the switch is stored on when the upload is on too."""
    apartment = _apartment()
    saved = host.post(
        f"/apartments/{apartment['id']}",
        data=_payload(passport_photo_policy="required_foreign", ocr_scan="1"),
        follow_redirects=False,
    )
    assert saved.status_code == 303, saved.text
    assert _apartment()["ocr_scan"] == 1


# ---- 1024: stay-fee stars, failed-save summary, Saved confirmation ----------

GOOD_FEE = dict(
    stay_fee_rate_czk="50",
    stay_fee_vs="1342900493",
    stay_fee_council_account="19-2000145399/0800",
    stay_fee_authority_name="Mesto Test",
)


def _fee_section(page: str) -> str:
    start = page.index('id="sec-fee"')
    return page[start : page.index("</details>", start)]


def _save_good_fee(host):
    apartment = _apartment()
    response = host.post(
        f"/apartments/{apartment['id']}", data=_payload(**GOOD_FEE), follow_redirects=False
    )
    assert response.status_code == 303, response.text
    return apartment["id"], response


def test_editor_stars_the_fee_fields_only_with_a_rate(host):
    apartment_id, _ = _save_good_fee(host)
    url = f"/apartments/{apartment_id}?lang=en&view=settings&section=reporting"
    stars = _fee_section(host.get(url).text).count('class="req-star"')
    assert stars == 3
    for fid in ("stay_fee_vs", "stay_fee_council_account", "stay_fee_authority_name"):
        tag = re.search(rf'<input[^>]*id="{fid}"[^>]*>', _fee_section(host.get(url).text)).group(0)
        assert 'aria-required="true"' in tag, fid
    db.execute("UPDATE apartment SET stay_fee_rate_czk = 0 WHERE id = ?", (apartment_id,))
    off = _fee_section(host.get(url).text)
    assert 'class="req-star"' not in off
    assert 'aria-required="true"' not in off


def test_a_valid_stay_fee_save_is_stored_and_confirmed(host):
    apartment_id, response = _save_good_fee(host)
    assert "msg=" in response.headers["location"]
    row = _apartment()
    assert row["stay_fee_vs"] == "1342900493"
    assert row["stay_fee_council_account"]
    page = host.get(response.headers["location"] + "&lang=en").text
    assert 'class="banner ok save-summary"' in page and "data-save-summary" in page
    assert 'class="banner err save-summary"' not in page
    assert page.count("Saved") >= 1


def _refused_account_post(host, apartment_id):
    return host.post(
        f"/apartments/{apartment_id}?lang=en",
        data=_payload(
            **{**GOOD_FEE, "stay_fee_council_account": "123", "stay_fee_vs": "9999999999",
               "internal_name": "Changed Flat"}
        ),
        follow_redirects=False,
    )


def test_an_invalid_account_is_refused_and_nothing_is_stored(host):
    apartment_id, _ = _save_good_fee(host)
    before = _apartment()
    response = _refused_account_post(host, apartment_id)
    assert response.status_code == 400
    after = _apartment()
    for column in ("internal_name", "stay_fee_vs", "stay_fee_council_account"):
        assert after[column] == before[column], column
    body = response.text
    assert "data-save-summary" in body
    assert 'data-first-error="stay_fee_council_account"' in body
    assert "This account number does not add up" in body
    assert "Not saved: fix 1 field." in body
    assert re.search(r'<details[^>]*id="sec-fee"[^>]*\bopen\b', body)
    assert "banner ok" not in body
    input_at = body.index('id="stay_fee_council_account"')
    error_at = body.index('<p class="err-text small" id="stay-fee-account-error"')
    assert body.index('for="stay_fee_council_account"') < input_at < error_at
    assert error_at < body.index('id="stay_fee_authority_name"')


def test_the_same_refusal_never_redirects_with_a_success_message(host):
    apartment_id, _ = _save_good_fee(host)
    response = _refused_account_post(host, apartment_id)
    assert response.status_code == 400
    assert "location" not in response.headers


def test_an_address_error_opens_basics_and_counts_fields(host):
    apartment = _apartment()
    response = host.post(
        f"/apartments/{apartment['id']}?lang=en",
        data=_payload(addr_zip="12", internal_name="Changed Flat"),
        follow_redirects=False,
    )
    assert response.status_code == 400
    body = response.text
    assert "Not saved: fix 1 field." in body
    assert 'data-first-error="addr_zip"' in body
    assert re.search(r'<details[^>]*id="sec-basics"[^>]*\bopen\b', body)
    assert _apartment()["internal_name"] == "Form Flat"
