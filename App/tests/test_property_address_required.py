"""Owner decision 2026-10-13: the police address is mandatory at create and on Settings save."""
from __future__ import annotations

import re
import secrets

from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

FIELDS = ("addr_obec", "addr_house_no", "addr_zip")
OPTIONAL_FIELDS = ("addr_okres", "addr_obec_cast", "addr_street", "addr_orient_no")


def setup_module():
    db.init_db()


def _host():
    username = f"addrreq-{secrets.token_hex(4)}"
    owner_id = auth.create_account(f"{username}@example.test", "Address Host", role="host", username=username)
    entity_id = db.insert("legal_entity", {"name": "Synthetic Operator", "owner_user_id": owner_id, "created_at": db.utcnow()})
    client = TestClient(app)
    assert login_as(client, username, url="/login?lang=en", follow_redirects=False).status_code == 303
    return {"client": client, "owner": owner_id, "entity": entity_id}


def _count(host) -> int:
    return len(db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (host["owner"],)))


def _form(host, **overrides):
    data = {
        "internal_name": "Address Flat",
        "legal_entity_id": str(host["entity"]),
        "addr_obec": "Praha",
        "addr_house_no": "12",
        "addr_zip": "11000",
    }
    data.update(overrides)
    return data


def _stored(host, **extra) -> int:
    row = {
        "internal_name": "Stored Flat",
        "owner_user_id": host["owner"],
        "legal_entity_id": host["entity"],
        "permalink_token": f"addrreq{secrets.token_hex(5)}",
        "permalink_pin": "123456",
        "addr_obec": "Brno",
        "addr_house_no": "7",
        "addr_zip": "60200",
        "active": 1,
        "created_at": db.utcnow(),
    }
    row.update(extra)
    return db.insert("apartment", row)


def _address(apartment_id):
    return db.query_one(
        "SELECT addr_obec, addr_house_no, addr_zip, internal_name FROM apartment WHERE id = ?", (apartment_id,)
    )


def test_create_without_address_is_refused_with_field_errors_and_inserts_nothing():
    host = _host()
    response = host["client"].post(
        "/apartments",
        data={"internal_name": "No Address Flat", "legal_entity_id": str(host["entity"]), "addr_street": "Typed Street"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    for field in FIELDS:
        assert f'id="{field}-error"' in response.text, field
        assert re.search(rf'id="{field}"[^>]*aria-invalid="true"', response.text), field
    assert 'value="No Address Flat"' in response.text and 'value="Typed Street"' in response.text
    assert _count(host) == 0


def test_each_missing_part_is_refused_on_its_own():
    host = _host()
    for field in FIELDS:
        response = host["client"].post("/apartments", data=_form(host, **{field: ""}), follow_redirects=False)
        assert response.status_code == 400, field
        assert f'id="{field}-error"' in response.text, field
        for other in FIELDS:
            if other != field:
                assert f'id="{other}-error"' not in response.text, (field, other)
    assert _count(host) == 0


def test_forged_post_without_address_fields_is_refused():
    host = _host()
    response = host["client"].post(
        "/apartments",
        data={"internal_name": "Forged", "legal_entity_id": str(host["entity"]), "active": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert _count(host) == 0
    blanks = host["client"].post("/apartments", data=_form(host, addr_obec="   "), follow_redirects=False)
    assert blanks.status_code == 400
    assert _count(host) == 0


def test_broken_typed_part_is_refused_even_when_all_three_are_present():
    host = _host()
    response = host["client"].post("/apartments", data=_form(host, addr_zip="12"), follow_redirects=False)
    assert response.status_code == 400
    assert 'id="addr_zip-error"' in response.text and 'value="12"' in response.text
    assert _count(host) == 0


def test_complete_address_creates_the_property_as_typed():
    host = _host()
    response = host["client"].post("/apartments", data=_form(host, addr_zip="602 00"), follow_redirects=False)
    assert response.status_code == 303
    row = db.query_one("SELECT * FROM apartment WHERE owner_user_id = ?", (host["owner"],))
    assert (row["addr_obec"], row["addr_house_no"], row["addr_zip"]) == ("Praha", "12", "60200")


def test_settings_save_clearing_the_municipality_is_refused_and_nothing_changes():
    host = _host()
    apartment_id = _stored(host)
    before = _address(apartment_id)
    response = host["client"].post(
        f"/apartments/{apartment_id}",
        data=_form(host, internal_name="Renamed Typed", addr_obec="", addr_house_no="99", addr_zip="11000"),
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert 'id="addr_obec-error"' in response.text
    assert 'value="Renamed Typed"' in response.text and 'value="99"' in response.text
    assert _address(apartment_id) == before


def test_settings_save_clearing_the_house_number_is_refused_and_typed_values_echoed():
    host = _host()
    apartment_id = _stored(host)
    before = _address(apartment_id)
    response = host["client"].post(
        f"/apartments/{apartment_id}",
        data=_form(host, internal_name="Echo Name", addr_obec="Ostrava", addr_house_no="", addr_zip="70200"),
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert 'id="addr_house_no-error"' in response.text
    assert 'value="Echo Name"' in response.text and 'value="Ostrava"' in response.text
    assert 'value="70200"' in response.text
    assert _address(apartment_id) == before


def test_settings_save_with_a_changed_complete_address_is_stored():
    host = _host()
    apartment_id = _stored(host)
    response = host["client"].post(
        f"/apartments/{apartment_id}", data=_form(host, addr_obec="Plzeň", addr_house_no="3"), follow_redirects=False
    )
    assert response.status_code == 303
    after = _address(apartment_id)
    assert (after["addr_obec"], after["addr_house_no"]) == ("Plzeň", "3")


def test_a_save_without_address_fields_still_works_and_keeps_the_address():
    host = _host()
    apartment_id = _stored(host)
    response = host["client"].post(
        f"/apartments/{apartment_id}",
        data={"internal_name": "Section Rename", "legal_entity_id": str(host["entity"])},
        follow_redirects=False,
    )
    assert response.status_code == 303
    after = _address(apartment_id)
    assert after["internal_name"] == "Section Rename"
    assert (after["addr_obec"], after["addr_house_no"], after["addr_zip"]) == ("Brno", "7", "60200")


def test_create_page_marks_the_three_parts_required_and_the_rest_optional():
    host = _host()
    for lang in ("en", "cs"):
        page = host["client"].get(f"/apartments/new?lang={lang}").text
        optional = host_i18n.translate(lang, "common.optional")
        for field in FIELDS:
            tag = re.search(rf'<input[^>]*id="{field}"[^>]*>', page).group(0)
            assert " required" in tag and 'aria-required="true"' in tag, (lang, field)
            label = re.search(rf'<label for="{field}">(.*?)</label>', page, re.S).group(1)
            assert optional not in label, (lang, field)
        for field in OPTIONAL_FIELDS:
            tag = re.search(rf'<input[^>]*id="{field}"[^>]*>', page).group(0)
            assert " required" not in tag, (lang, field)
            label = re.search(rf'<label for="{field}">(.*?)</label>', page, re.S).group(1)
            assert optional in label, (lang, field)
