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
            "ico": "04656679",
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
            "ico": "04656679",
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


def _owner_id() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


def _add_apartment(**over):
    values = {
        "internal_name": "Fee Flat",
        "owner_user_id": _owner_id(),
        "created_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("apartment", values)


def _apartment(apt_id):
    return db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,))


def test_new_apartment_defaults_to_policy_off_rate_zero_cash_on(host):
    apt_id = _add_apartment()
    row = _apartment(apt_id)
    assert row["stay_fee_policy"] == "off"
    assert row["stay_fee_rate_czk"] == 0
    assert row["stay_fee_cash"] == 1


def test_create_form_without_fee_fields_keeps_the_defaults(host):
    response = host.post(
        "/apartments?lang=en",
        data={"internal_name": "No Fee Flat", "active": "on"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    row = db.query_one(
        "SELECT * FROM apartment WHERE internal_name = ?", ("No Fee Flat",)
    )
    assert row["stay_fee_policy"] == "off"
    assert row["stay_fee_rate_czk"] == 0
    assert row["stay_fee_cash"] == 1
    assert row["stay_fee_payment_link"] is None


def test_edit_form_caps_the_rate_at_50(host):
    apt_id = _add_apartment()
    host.post(
        f"/apartments/{apt_id}?lang=en",
        data={"internal_name": "Fee Flat", "stay_fee_rate_czk": "75", "stay_fee_policy": "on"},
        follow_redirects=False,
    )
    row = _apartment(apt_id)
    assert row["stay_fee_rate_czk"] == 50
    # The cash checkbox was not posted, so it is off.
    assert row["stay_fee_cash"] == 0


def test_edit_form_non_numeric_rate_stores_zero(host):
    apt_id = _add_apartment(stay_fee_rate_czk=30)
    host.post(
        f"/apartments/{apt_id}?lang=en",
        data={"internal_name": "Fee Flat", "stay_fee_rate_czk": "abc", "stay_fee_policy": "on"},
        follow_redirects=False,
    )
    assert _apartment(apt_id)["stay_fee_rate_czk"] == 0


def test_edit_form_link_without_https_is_stored_as_none(host):
    apt_id = _add_apartment()
    host.post(
        f"/apartments/{apt_id}?lang=en",
        data={
            "internal_name": "Fee Flat",
            "stay_fee_rate_czk": "50",
            "stay_fee_policy": "on",
            "stay_fee_payment_link": "http://paypal.me/x",
            "stay_fee_cash": "1",
        },
        follow_redirects=False,
    )
    row = _apartment(apt_id)
    assert row["stay_fee_payment_link"] is None
    assert row["stay_fee_cash"] == 1


def test_edit_form_accepts_an_https_link(host):
    apt_id = _add_apartment()
    host.post(
        f"/apartments/{apt_id}?lang=en",
        data={
            "internal_name": "Fee Flat",
            "stay_fee_rate_czk": "50",
            "stay_fee_policy": "on",
            "stay_fee_payment_link": "https://paypal.me/fee",
        },
        follow_redirects=False,
    )
    assert _apartment(apt_id)["stay_fee_payment_link"] == "https://paypal.me/fee"

