"""Czech property address: one line in, police parts out."""
from __future__ import annotations

import pytest

from app import validation


@pytest.mark.parametrize(
    "line,expected",
    [
        (
            "Vinohradská 1234/12, 120 00 Praha 2",
            {
                "addr_street": "Vinohradská",
                "addr_house_no": "1234",
                "addr_orient_no": "12",
                "addr_zip": "12000",
                "addr_obec": "Praha 2",
            },
        ),
        (
            "Street 1234/12a, 120 00 Praha",
            {
                "addr_street": "Street",
                "addr_house_no": "1234",
                "addr_orient_no": "12a",
                "addr_zip": "12000",
                "addr_obec": "Praha",
            },
        ),
        (
            "Street 1234, 120 00 Praha",
            {
                "addr_street": "Street",
                "addr_house_no": "1234",
                "addr_zip": "12000",
                "addr_obec": "Praha",
            },
        ),
        (
            "Obec 123, 54321 Obec",
            {
                "addr_house_no": "123",
                "addr_zip": "54321",
                "addr_obec": "Obec",
            },
        ),
        (
            "č.p. 123, 12000 Praha",
            {"addr_house_no": "123", "addr_zip": "12000", "addr_obec": "Praha"},
        ),
        (
            "cp. E123, 12000 Praha",
            {"addr_house_no": "E123", "addr_zip": "12000", "addr_obec": "Praha"},
        ),
        (
            "Main 12E, 12000 Praha",
            {"addr_street": "Main", "addr_house_no": "12E", "addr_zip": "12000", "addr_obec": "Praha"},
        ),
        (
            "Hlavní 1, 12000 Praha 2 - Vinohrady",
            {
                "addr_street": "Hlavní",
                "addr_house_no": "1",
                "addr_zip": "12000",
                "addr_obec": "Praha 2",
                "addr_obec_cast": "Vinohrady",
            },
        ),
        ("", {}),
        ("not an address at all", {}),
        (
            "Street 99999, 12000 Praha",
            {"addr_zip": "12000", "addr_obec": "Praha"},
        ),
        (
            "Street  1234/12,12000  Praha",
            {
                "addr_street": "Street",
                "addr_house_no": "1234",
                "addr_orient_no": "12",
                "addr_zip": "12000",
                "addr_obec": "Praha",
            },
        ),
    ],
)
def test_split_czech_address(line: str, expected: dict):
    assert validation.split_czech_address(line) == expected


def test_merge_fills_only_empty_fields():
    payload = {
        "addr_street": "Host street",
        "addr_house_no": "",
        "addr_orient_no": "",
        "addr_zip": "",
        "addr_obec": "",
        "addr_obec_cast": "",
    }
    split = validation.split_czech_address("Other 99/1, 11000 Praha 1")
    mismatch = validation.merge_split_address_fields(payload, split)
    assert mismatch is True
    assert payload["addr_street"] == "Host street"
    assert payload["addr_house_no"] == "99"
    assert payload["addr_orient_no"] == "1"
    assert payload["addr_zip"] == "11000"
    assert payload["addr_obec"] == "Praha 1"


def test_merge_no_conflict_when_empty_details():
    payload = {field: "" for field in validation._ADDR_SPLIT_FIELDS}
    split = validation.split_czech_address("Vinohradská 1234/12, 120 00 Praha 2")
    mismatch = validation.merge_split_address_fields(payload, split)
    assert mismatch is False
    assert payload["addr_street"] == "Vinohradská"
    assert payload["addr_house_no"] == "1234"


def test_compose_round_trip():
    parts = {
        "addr_street": "Vinohradská",
        "addr_house_no": "1234",
        "addr_orient_no": "12",
        "addr_zip": "12000",
        "addr_obec": "Praha 2",
    }
    line = validation.compose_czech_address_line(parts)
    assert validation.split_czech_address(line) == parts


def test_property_save_ignores_address_line_field(host_client):
    """Route-level: submitted address_line cannot override structured addr_* values."""
    from app import db

    client, owner_id, entity_id = host_client
    payload = {
        "internal_name": "Split Route Flat",
        "legal_entity_id": str(entity_id),
        "addr_obec": "Praha",
        "addr_house_no": "7",
        "addr_zip": "11000",
        "addr_street": "Saved Street",
        "address_line": "Other 999/1, 99999 Elsewhere",
        "active": "on",
        "automation_mode": "manual",
        "submit_after_hours": "24",
        "default_purpose": "10",
    }
    response = client.post("/apartments", data=payload, follow_redirects=False)
    assert response.status_code == 303
    row = db.query_one(
        "SELECT addr_street, addr_obec FROM apartment WHERE internal_name = ?",
        ("Split Route Flat",),
    )
    assert row["addr_street"] == "Saved Street"
    assert row["addr_obec"] == "Praha"


@pytest.fixture
def host_client():
    from fastapi.testclient import TestClient

    from app import auth, db
    from app.main import app
    from tests.conftest import login_as

    db.init_db()
    username = "addr-split-route"
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (username,)):
        owner_id = row["id"]
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))
    owner_id = auth.create_account(f"{username}@example.test", "", role="host", username=username)
    entity_id = db.insert(
        "legal_entity",
        {"name": "Split Route s.r.o.", "owner_user_id": owner_id, "created_at": db.utcnow()},
    )
    client = TestClient(app)
    login_as(client, username, url="/login?lang=en", follow_redirects=False)
    try:
        yield client, owner_id, entity_id
    finally:
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (owner_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (owner_id,))
