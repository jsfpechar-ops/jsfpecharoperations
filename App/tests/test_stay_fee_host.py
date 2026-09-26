"""Stay-fee host panel and routes (step 9).

The host rows of docs/plans/PLAN_POPLATEK_Z_POBYTU.md §14.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, db, stay_fee
from app.main import app

PASSWORD = "Secure-Password-123"
USERNAME = "stay-fee-host"
TOKEN = "hostfeestay"
IBAN = "CZ9106000000000000000123"


def _owner() -> int:
    return db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]


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


def _make_stay(expected=3):
    now = db.utcnow()
    owner = _owner()
    entity_id = db.insert(
        "legal_entity",
        {"name": "Host Fee Entity", "iban": IBAN, "bank_account": "123/0600",
         "owner_user_id": owner, "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Host Fee Flat",
            "owner_user_id": owner,
            "legal_entity_id": entity_id,
            "stay_fee_rate_czk": 50,
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "uid": "host-fee-1",
            "source": "booking",
            "date_from": "2026-09-10",
            "date_to": "2026-09-14",
            "expected_guests_override": expected,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return apartment_id, reservation_id


def _add_guest(res_id, *, signed=True, claim=None, decision=None):
    return db.insert(
        "guest",
        {
            "reservation_id": res_id,
            "first_name": "A",
            "surname": "B",
            "birth_date": "01011990",
            "signature_png": "data:image/png;base64,AAAA" if signed else "",
            "fee_claim": claim,
            "fee_host_decision": decision,
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )


def _summary(res_id, apt_id):
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (res_id,))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,))
    return stay_fee.stay_summary(reservation, apartment)


def test_exempt_without_a_reason_is_refused(host):
    apt_id, res_id = _make_stay()
    gid = _add_guest(res_id)
    response = host.post(
        f"/guests/{gid}/stay-fee",
        data={"decision": "exempt", "reason": ""},
        follow_redirects=True,
    )
    assert "Give a reason when you exempt someone." in response.text
    assert (
        db.query_one("SELECT fee_host_decision FROM guest WHERE id = ?", (gid,))[
            "fee_host_decision"
        ]
        is None
    )


def test_exempt_with_a_reason_zeroes_the_amount_and_audits(host):
    apt_id, res_id = _make_stay()
    gid = _add_guest(res_id)
    host.post(
        f"/guests/{gid}/stay-fee",
        data={"decision": "exempt", "reason": "Local resident"},
        follow_redirects=False,
    )
    row = db.query_one("SELECT * FROM guest WHERE id = ?", (gid,))
    assert row["fee_host_decision"] == "exempt"
    assert row["fee_host_reason"] == "Local resident"
    assert _summary(res_id, apt_id)["people"][0]["amount_czk"] == 0
    assert db.query_one("SELECT 1 AS x FROM audit WHERE action = 'stay_fee_decision'")


def test_charge_decision_is_stored(host):
    apt_id, res_id = _make_stay()
    gid = _add_guest(res_id, claim="disability_card")
    host.post(
        f"/guests/{gid}/stay-fee",
        data={"decision": "charge", "reason": ""},
        follow_redirects=False,
    )
    assert (
        db.query_one("SELECT fee_host_decision FROM guest WHERE id = ?", (gid,))[
            "fee_host_decision"
        ]
        == "charge"
    )


def test_auto_clears_a_stored_decision(host):
    apt_id, res_id = _make_stay()
    gid = _add_guest(res_id, decision="exempt")
    host.post(
        f"/guests/{gid}/stay-fee",
        data={"decision": "", "reason": ""},
        follow_redirects=False,
    )
    assert (
        db.query_one("SELECT fee_host_decision FROM guest WHERE id = ?", (gid,))[
            "fee_host_decision"
        ]
        is None
    )


def test_a_claim_without_a_decision_is_highlighted_and_open(host):
    apt_id, res_id = _make_stay()
    _add_guest(res_id, claim="other")
    page = host.get(f"/reservations/{res_id}")
    assert "needs-review" in page.text
    assert "<details open>" in page.text


def test_mark_paid_stores_the_total_and_undo_clears_it(host):
    apt_id, res_id = _make_stay(expected=1)
    _add_guest(res_id)
    host.post(
        f"/reservations/{res_id}/stay-fee/paid",
        data={"action": "paid"},
        follow_redirects=False,
    )
    row = db.query_one("SELECT * FROM reservation WHERE id = ?", (res_id,))
    assert row["stay_fee_paid_at"]
    assert row["stay_fee_paid_amount_czk"] == 200
    host.post(
        f"/reservations/{res_id}/stay-fee/paid",
        data={"action": "unpaid"},
        follow_redirects=False,
    )
    row = db.query_one("SELECT * FROM reservation WHERE id = ?", (res_id,))
    assert row["stay_fee_paid_at"] is None
    assert row["stay_fee_paid_amount_czk"] is None


def test_headcount_warning_when_fewer_signed_than_expected(host):
    apt_id, res_id = _make_stay(expected=3)
    _add_guest(res_id)
    page = host.get(f"/reservations/{res_id}")
    assert "Only 1 of 3" in page.text
