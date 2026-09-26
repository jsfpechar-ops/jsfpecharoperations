"""Stay-fee settings (steps 4-5): entity bank account and the property panel.

The acceptance list is docs/plans/PLAN_POPLATEK_Z_POBYTU.md §14
(``test_stay_fee_settings.py``).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "stay-fee-settings-host"


def _cleanup():
    owner = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    if not owner:
        return
    user_id = owner["id"]
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id IN "
        "(SELECT id FROM apartment WHERE owner_user_id = ?))",
        (user_id,),
    )
    db.execute(
        "DELETE FROM reservation WHERE apartment_id IN "
        "(SELECT id FROM apartment WHERE owner_user_id = ?)",
        (user_id,),
    )
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
    db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    if not db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        auth.create_account(USERNAME, PASSWORD, "Stay Fee Host", must_change_password=False)
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": USERNAME, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def test_entity_bank_account_stores_the_derived_iban(host):
    host.post(
        "/entities?lang=en",
        data={
            "name": "Fee Operator",
            "seat": "Praha 1",
            "ico": "12345678",
            "contact_email": "fee@settings.test",
            "bank_account": "19-2000781379/0800",
        },
    )
    row = db.query_one("SELECT * FROM legal_entity WHERE name = ?", ("Fee Operator",))
    assert row is not None
    assert row["bank_account"] == "19-2000781379/0800"
    assert row["iban"] == "CZ3008000000192000781379"


def test_entity_invalid_bank_account_shows_the_error_and_saves_nothing(host):
    response = host.post(
        "/entities?lang=en",
        data={
            "name": "Bad Operator",
            "seat": "Praha 1",
            "ico": "12345678",
            "contact_email": "bad@settings.test",
            "bank_account": "19-2000781378/0800",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "That account number is not valid" in response.text
    assert (
        db.query_one("SELECT * FROM legal_entity WHERE name = ?", ("Bad Operator",)) is None
    )
