"""Police setup defaults: three visible fields, derived header filled on save."""
from __future__ import annotations

import secrets

import pytest
from fastapi.testclient import TestClient

from app import auth, db, property_setup, validation
from app.main import app
from app.routes import admin as admin_routes
from app.host_i18n import STRINGS
from tests.conftest import login_as

USERNAME = "police-defaults-host"


def _cleanup():
    db.execute(
        "DELETE FROM apartment WHERE owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?)",
        (USERNAME,),
    )
    db.execute(
        "DELETE FROM legal_entity WHERE owner_user_id = "
        "(SELECT id FROM user_account WHERE username = ?)",
        (USERNAME,),
    )


def _owner_id() -> int:
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    assert row
    return row["id"]


def _entity(**overrides):
    owner = _owner_id()
    data = {
        "name": "Police Defaults s.r.o.",
        "owner_user_id": owner,
        "contact_email": "operator@police-defaults.test",
        "created_at": db.utcnow(),
    }
    data.update(overrides)
    return db.insert("legal_entity", data)


def _finish_setup(apartment_id: int) -> None:
    property_setup.start(apartment_id)
    property_setup.finish(apartment_id)


def _valid_apartment_fields(entity_id: int, **overrides):
    data = {
        "internal_name": "Police Defaults Flat",
        "owner_user_id": _owner_id(),
        "legal_entity_id": entity_id,
        "permalink_token": f"pd{secrets.token_hex(5)}",
        "active": 1,
        "created_at": db.utcnow(),
        "uby_idub": "123456789012",
        "uby_mark": "AB12CD",
        "uby_name": "Police Defaults Flat",
        "uby_contact": "host@police-defaults.test",
        "uby_ws_user": "UBY-WSab12cd",
        "uby_ws_password_enc": db.encrypt_secret("secret"),
        "addr_house_no": "1",
        "addr_zip": "120 00",
        "addr_obec": "Praha",
    }
    data.update(overrides)
    return data


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(f"{USERNAME}@example.test", "Police Defaults", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


@pytest.fixture(autouse=True)
def _db():
    db.init_db()
    yield


def test_mark_from_ws_user_derives_production_login():
    assert validation.mark_from_ws_user("UBY-WSab12cd") == "AB12CD"
    assert validation.mark_from_ws_user("UBY-WS_MLJNO") == "MLJNO"
    assert validation.mark_from_ws_user("uby-ws_mljno") == "MLJNO"


def test_mark_from_ws_user_ignores_test_login():
    assert validation.mark_from_ws_user("uby-tws1ab45") == ""


def test_facility_name_is_never_filled_from_the_property_name():
    # 0097: the police name comes from the letter ("Ubytovací zařízení"), never
    # from the property or listing name.
    payload = {"internal_name": "A" * 40, "uby_name": ""}
    admin_routes._apply_police_defaults(payload, [])
    assert payload["uby_name"] == ""
    payload = {"internal_name": "Flat", "uby_name": None}
    admin_routes._apply_police_defaults(payload, [])
    assert payload["uby_name"] is None


def test_contact_default_uses_operator_email(host):
    entity_id = _entity(contact_email=("x" * 45) + "@example.test")
    entities = db.query("SELECT * FROM legal_entity WHERE id = ?", (entity_id,))
    payload = {"legal_entity_id": entity_id, "uby_contact": ""}
    admin_routes._apply_police_defaults(payload, entities)
    assert len(payload["uby_contact"]) == 50
    assert payload["uby_contact"].startswith("x" * 35)


def test_typed_police_fields_are_never_replaced(host):
    entity_id = _entity()
    entities = db.query("SELECT * FROM legal_entity WHERE id = ?", (entity_id,))
    payload = {
        "internal_name": "Other name",
        "legal_entity_id": entity_id,
        "uby_ws_user": "UBY-WSzzzzzz",
        "uby_mark": "KEPT01",
        "uby_name": "Kept facility",
        "uby_contact": "kept@example.test",
    }
    admin_routes._apply_police_defaults(payload, entities)
    assert payload["uby_mark"] == "KEPT01"
    assert payload["uby_name"] == "Kept facility"
    assert payload["uby_contact"] == "kept@example.test"


def test_create_applies_defaults_from_login_and_operator(host):
    entity_id = _entity()
    created = host.post(
        "/apartments",
        data={
            "internal_name": "Defaults On Create",
            "legal_entity_id": str(entity_id),
            "uby_idub": "123456789012",
            "uby_ws_user": "UBY-WSab12cd",
            "uby_ws_password": "secret",
            "addr_house_no": "1",
            "addr_zip": "120 00",
            "addr_obec": "Praha",
            "active": "on",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303, created.text
    row = db.query_one(
        "SELECT uby_mark, uby_name, uby_contact FROM apartment WHERE internal_name = ?",
        ("Defaults On Create",),
    )
    assert row["uby_mark"] == "AB12CD"
    assert not row["uby_name"]
    assert row["uby_contact"] == "operator@police-defaults.test"


def test_readiness_still_requires_the_facility_name(host):
    entity_id = _entity()
    apartment_id = db.insert("apartment", _valid_apartment_fields(entity_id, uby_name=""))
    _finish_setup(apartment_id)
    page = host.get(f"/apartments/{apartment_id}?lang=en")
    assert page.status_code == 200, page.text
    assert 'name="uby_name" value=""' in page.text
    issues = validation.errors_only(validation.validate_apartment(
        dict(db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,)))
    ))
    assert any(issue.field == "uby_name" for issue in issues)


def test_save_keeps_a_stored_facility_name_and_does_not_fill_a_blank_one(host):
    entity_id = _entity()
    kept = db.insert("apartment", _valid_apartment_fields(entity_id, uby_name="Penzion Z Dopisu"))
    blank = db.insert("apartment", _valid_apartment_fields(
        entity_id, internal_name="Blank Name Flat", uby_name="",
        permalink_token=f"pd{secrets.token_hex(5)}"))
    for apartment_id in (kept, blank):
        row = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
        page = host.get(f"/apartments/{apartment_id}?lang=en")
        token = page.text.split('name="_csrf" value="', 1)[1].split('"', 1)[0]
        form = {key: (row[key] or "") for key in (
            "internal_name", "uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user",
            "addr_house_no", "addr_zip", "addr_obec")}
        form.update({"_csrf": token, "legal_entity_id": str(entity_id)})
        response = host.post(f"/apartments/{apartment_id}", data=form, follow_redirects=False)
        assert response.status_code == 303, response.text
    assert db.query_one("SELECT uby_name FROM apartment WHERE id = ?", (kept,))["uby_name"] == "Penzion Z Dopisu"
    assert not db.query_one("SELECT uby_name FROM apartment WHERE id = ?", (blank,))["uby_name"]


def test_property_page_shows_police_header_fields_without_derived_wrapper(host):
    entity_id = _entity()
    apartment_id = db.insert("apartment", _valid_apartment_fields(entity_id))
    page = host.get(f"/apartments/{apartment_id}?lang=en")
    assert page.status_code == 200, page.text
    assert 'name="uby_mark"' in page.text
    assert 'name="uby_name"' in page.text
    assert 'name="uby_contact"' in page.text
    assert "police-derived" not in page.text
    assert STRINGS["en"]["apartment.form.ubyport.credentials_help_heading"] in page.text


def test_property_page_shows_mark_error_when_abbreviation_missing(host):
    entity_id = _entity()
    apartment_id = db.insert(
        "apartment",
        _valid_apartment_fields(entity_id, uby_mark="", uby_ws_user="uby-tws1ab45"),
    )
    _finish_setup(apartment_id)
    page = host.get(f"/apartments/{apartment_id}?lang=en")
    assert page.status_code == 200, page.text
    assert "The facility abbreviation (zkratka) is required." in page.text
    assert 'id="uby_mark"' in page.text
