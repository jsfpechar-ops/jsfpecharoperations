"""0209: the stay-fee report signature is set with the stay fee and saved to the operator."""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from tests.conftest import login_as
from tests.test_stay_fee_property_panel import USERNAME, _cleanup, _form_data, _operator_id, _stay_fee_data

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/h48AAAAASUVORK5CYII=")
PNG_URL = "data:image/png;base64," + base64.b64encode(PNG).decode()


@pytest.fixture
def host():
    from app import auth

    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Fee signature host", username=USERNAME)
    client = TestClient(app)
    login = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert login.status_code == 303, login.text
    created = client.post("/apartments", data=_form_data(), follow_redirects=False)
    assert created.status_code == 303, created.text
    owner_id = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]
    apartment_id = db.query_one("SELECT id FROM apartment WHERE owner_user_id = ?", (owner_id,))["id"]
    try:
        yield client, apartment_id
    finally:
        _cleanup()


def _operator_row():
    return db.query_one("SELECT * FROM legal_entity WHERE id = ?", (int(_operator_id()),))


def test_settings_reporting_has_the_signature_in_a_multipart_form(host):
    client, apartment_id = host
    page = client.get(f"/apartments/{apartment_id}?view=settings&section=reporting&lang=en")
    assert page.status_code == 200
    assert 'name="fee_signature_section"' in page.text
    assert 'id="fee_sig-canvas"' in page.text
    form_tag = page.text[page.text.index('id="property-settings-form"') - 400:page.text.index('id="property-settings-form"') + 200]
    assert 'enctype="multipart/form-data"' in form_tag


def test_business_details_no_longer_hold_the_signature(host):
    client, _apartment_id = host
    page = client.get(f"/entities?edit={_operator_id()}&lang=en")
    assert page.status_code == 200
    assert "sig-canvas" not in page.text
    assert "The signature for stay-fee reports is now set with the stay fee" in page.text


def test_settings_reporting_remove_checkbox_follows_the_stored_signature(host):
    client, apartment_id = host
    url = f"/apartments/{apartment_id}?view=settings&section=reporting&lang=en"
    assert 'name="signature_remove"' not in client.get(url).text
    db.update("legal_entity", int(_operator_id()), {"signature_png_enc": db.encrypt_field(PNG_URL)})
    page = client.get(url).text
    assert page.count('name="signature_remove"') == 1
    assert 'accept="image/png,image/jpeg"' in page
    assert 'maxlength="80"' in page


def test_fee_form_with_a_signature_saves_it_to_the_operator(host):
    client, apartment_id = host
    data = _form_data(**_stay_fee_data(stay_fee_rate_czk="25"))
    data.update({"fee_signature_section": "1", "signature_drawn": PNG_URL, "signature_name": "Jana Pole"})
    response = client.post(f"/apartments/{apartment_id}", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text
    row = _operator_row()
    assert row["signature_name"] == "Jana Pole"
    assert row["signature_png_enc"]


def test_invalid_signature_is_refused_and_the_stored_one_stays(host):
    client, apartment_id = host
    client.post(
        f"/apartments/{apartment_id}",
        data={**_form_data(**_stay_fee_data(stay_fee_rate_czk="25")), "fee_signature_section": "1",
              "signature_drawn": PNG_URL, "signature_name": "Jana Pole"},
        follow_redirects=False,
    )
    before = _operator_row()
    response = client.post(
        f"/apartments/{apartment_id}",
        data={**_form_data(**_stay_fee_data(stay_fee_rate_czk="25")), "fee_signature_section": "1",
              "signature_drawn": "data:image/png;base64,AAAA", "signature_name": "Someone Else"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "stay-fee-settings" in response.headers["location"]
    assert "err=" in response.headers["location"]
    after = _operator_row()
    assert after["signature_name"] == before["signature_name"] == "Jana Pole"
    assert after["signature_png_enc"] == before["signature_png_enc"]
