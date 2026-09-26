"""Stay-fee core: the worked examples E1-E11 and the freeze/None rules.

Every ``E`` case is the table in docs/plans/PLAN_POPLATEK_Z_POBYTU.md §6 (rate 50).
"""
from __future__ import annotations

import pytest

from app import db, stay_fee

RATE = 50


def _guest(**over):
    row = {
        "id": 1,
        "stay_from": None,
        "stay_to": None,
        "birth_date": None,
        "fee_claim": None,
        "fee_host_decision": None,
        "fee_host_reason": None,
        "signature_png": "data:image/png;base64,AAAA",
    }
    row.update(over)
    return row


def _reservation(**over):
    row = {
        "id": 7,
        "date_from": "2026-09-10",
        "date_to": "2026-09-14",
        "stay_fee_rate_czk": None,
        "stay_fee_paid_at": None,
        "stay_fee_paid_amount_czk": None,
    }
    row.update(over)
    return row


def test_e1_adult_four_nights():
    fee = stay_fee.person_fee(_guest(birth_date="01.01.1990"), _reservation(), RATE)
    assert fee["nights"] == 4
    assert fee["charged_nights"] == 4
    assert fee["amount_czk"] == 200
    assert fee["reason"] is None


def test_e2_under_18_on_arrival_is_free():
    fee = stay_fee.person_fee(_guest(birth_date="12.09.2008"), _reservation(), RATE)
    assert fee["amount_czk"] == 0
    assert fee["reason"] == "under_18"


def test_e3_18_on_arrival_is_charged():
    fee = stay_fee.person_fee(_guest(birth_date="10.09.2008"), _reservation(), RATE)
    assert fee["amount_czk"] == 200


def test_e4_partial_birth_date_is_read_conservatively():
    # 00002015 -> 01.01.2015, an 11-year-old on arrival: never a false adult.
    fee = stay_fee.person_fee(_guest(birth_date="00002015"), _reservation(), RATE)
    assert fee["amount_czk"] == 0
    assert fee["reason"] == "under_18"


def test_e5_unknown_birth_date_is_an_adult():
    fee = stay_fee.person_fee(_guest(birth_date="00000000"), _reservation(), RATE)
    assert fee["amount_czk"] == 200


def test_e6_fifty_nine_nights_is_charged():
    fee = stay_fee.person_fee(
        _guest(birth_date="01.01.1990"),
        _reservation(date_from="2026-06-01", date_to="2026-07-30"),
        RATE,
    )
    assert fee["nights"] == 59
    assert fee["amount_czk"] == 2950


def test_e7_sixty_nights_is_over_the_cut_off():
    fee = stay_fee.person_fee(
        _guest(birth_date="01.01.1990"),
        _reservation(date_from="2026-06-01", date_to="2026-07-31"),
        RATE,
    )
    assert fee["nights"] == 60
    assert fee["amount_czk"] == 0
    assert fee["reason"] == "over_60_days"


def test_e8_a_claim_alone_changes_nothing():
    fee = stay_fee.person_fee(
        _guest(birth_date="01.01.1990", fee_claim="disability_card"), _reservation(), RATE
    )
    assert fee["amount_czk"] == 200


def test_e9_host_exemption_wins():
    fee = stay_fee.person_fee(
        _guest(
            birth_date="01.01.1990",
            fee_claim="disability_card",
            fee_host_decision="exempt",
        ),
        _reservation(),
        RATE,
    )
    assert fee["amount_czk"] == 0
    assert fee["reason"] == "host_exempt"


def test_e10_host_charge_wins_over_minor():
    fee = stay_fee.person_fee(
        _guest(birth_date="12.09.2008", fee_host_decision="charge"), _reservation(), RATE
    )
    assert fee["amount_czk"] == 200
    assert fee["reason"] is None


@pytest.fixture
def stay():
    db.init_db()
    apt_id = db.insert(
        "apartment",
        {
            "internal_name": "Fee Flat",
            "stay_fee_rate_czk": RATE,
            "created_at": db.utcnow(),
        },
    )
    res_id = db.insert(
        "reservation",
        {
            "apartment_id": apt_id,
            "uid": f"fee-{apt_id}",
            "date_from": "2026-09-10",
            "date_to": "2026-09-14",
            "status": "active",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )
    yield apt_id, res_id
    db.execute("DELETE FROM guest WHERE reservation_id = ?", (res_id,))
    db.execute("DELETE FROM reservation WHERE id = ?", (res_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (apt_id,))


def _add_guest(res_id: int, **over):
    values = {
        "reservation_id": res_id,
        "first_name": "A",
        "surname": "B",
        "signature_png": "data:image/png;base64,AAAA",
        "created_at": db.utcnow(),
        "updated_at": db.utcnow(),
    }
    values.update(over)
    return db.insert("guest", values)


def test_e11_only_signed_guests_count(stay):
    apt_id, res_id = stay
    for _ in range(3):
        _add_guest(res_id)
    _add_guest(res_id, signature_png="")  # not signed: excluded
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apt_id,))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (res_id,))
    summary = stay_fee.stay_summary(reservation, apartment)
    assert len(summary["people"]) == 3
    assert summary["total_czk"] == 600
    assert summary["vs"] == "8" + str(res_id).zfill(9)


def test_stay_summary_is_none_when_inactive_and_no_snapshot():
    assert stay_fee.stay_summary(_reservation(), {"stay_fee_rate_czk": 0}) is None


def test_snapshot_rate_freezes_once(stay):
    apt_id, res_id = stay
    stay_fee.snapshot_rate(res_id)
    frozen = db.query_one(
        "SELECT stay_fee_rate_czk FROM reservation WHERE id = ?", (res_id,)
    )["stay_fee_rate_czk"]
    assert frozen == RATE
    db.execute("UPDATE apartment SET stay_fee_rate_czk = 30 WHERE id = ?", (apt_id,))
    stay_fee.snapshot_rate(res_id)
    assert (
        db.query_one("SELECT stay_fee_rate_czk FROM reservation WHERE id = ?", (res_id,))[
            "stay_fee_rate_czk"
        ]
        == RATE
    )


def test_is_active_and_policy_gate():
    assert not stay_fee.is_active({"stay_fee_rate_czk": 0})
    assert stay_fee.is_active({"stay_fee_rate_czk": RATE})
    assert stay_fee.shows_to_guest({"stay_fee_rate_czk": RATE, "stay_fee_policy": "on"})
    assert not stay_fee.shows_to_guest({"stay_fee_rate_czk": RATE, "stay_fee_policy": "off"})


def test_format_czk_groups_thousands_with_a_no_break_space():
    assert stay_fee.format_czk(1200) == "1\u00a0200"
