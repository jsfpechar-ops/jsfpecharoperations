"""1026: stay-fee rules for long stays and locked guest stay dates.

Rules (zákon 565/1990 Sb. §3a, Ministry of Finance MP/08/2019, owner decision):
a stay of up to and including 60 consecutive nights pays the fee; a stay of MORE
than 60 nights owes nothing at all (0 Kč, no pay step, no estimate), not even for
its first 60 nights. A host decision cannot make a >60-night stay chargeable.
"""
from __future__ import annotations

import pathlib
from datetime import date, timedelta

import pytest

from app import config, stay_fee
from app.routes import guest as guest_routes

START = date(2026, 3, 1)
RATE = 30


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)


def _res(nights: int) -> dict:
    return {"id": 1, "source": None, "date_from": START.isoformat(),
            "date_to": (START + timedelta(days=nights)).isoformat()}


def _guest(**kw) -> dict:
    base = {"id": 1, "stay_from": None, "stay_to": None, "birth_date": "01011990",
            "fee_host_decision": None, "fee_host_reason": None, "fee_host_reason_enc": None,
            "res_country": "DEU", "res_city": "Berlin"}
    base.update(kw)
    return base


def _apartment(**kw) -> dict:
    base = {"stay_fee_collect": 1, "stay_fee_rate_czk": RATE, "stay_fee_scope_rule": "",
            "addr_obec": None, "legal_entity_id": None}
    base.update(kw)
    return base


def _share(nights: int, guest=None, apartment=None):
    return stay_fee.guest_period(guest or _guest(), _res(nights), date.min, date.max,
                                 apartment=apartment)


# --- engine: 59, 60, 61 nights ----------------------------------------------

def test_59_nights_pays_every_night():
    share = _share(59)
    assert share["status"] == "liable"
    assert share["liable_nights"] == 59


def test_60_nights_pays_every_night_by_default():
    share = _share(60)
    assert share["status"] == "liable"
    assert share["liable_nights"] == 60
    assert share["threshold_nights"] is True


def test_61_nights_owes_nothing():
    share = _share(61)
    assert share["status"] == "not_subject"
    assert share["liable_nights"] == 0
    assert share["exempt_nights"] == 0


def test_61_nights_owes_nothing_even_with_host_charge_decision():
    share = _share(61, guest=_guest(fee_host_decision="charge"))
    assert share["status"] == "not_subject"
    assert share["liable_nights"] == 0


def test_long_stay_owes_nothing_for_any_length_over_threshold():
    for nights in (62, 90, 365):
        share = _share(nights)
        assert share["status"] == "not_subject"
        assert share["liable_nights"] == 0


def test_recorded_calendar_days_ruling_takes_exactly_60_out_but_not_61_in():
    # An explicit host-recorded council ruling may move exactly-60 out of scope;
    # it never makes a >60-night stay chargeable.
    apartment = _apartment(stay_fee_scope_rule="calendar_days")
    sixty = guest_routes._fee_liable_days(apartment, _res(60), _guest())
    sixty_one = guest_routes._fee_liable_days(apartment, _res(61), _guest())
    assert sixty == 0
    assert sixty_one == 0


# --- estimate on the guest's Check step -------------------------------------

def _estimate(nights: int, apartment=None):
    return guest_routes._fee_estimate(apartment or _apartment(), _res(nights), {}, None)


def test_estimate_59_nights():
    assert _estimate(59) == {"amount": 59 * RATE, "days": 59, "rate": RATE,
                             "live": {"from": START.isoformat(),
                                      "to": (START + timedelta(days=59)).isoformat(),
                                      "rate": RATE},
                             "hidden": False}


def test_estimate_60_nights_is_shown_in_full():
    estimate = _estimate(60)
    assert estimate["days"] == 60
    assert estimate["amount"] == 60 * RATE


def test_estimate_61_nights_is_none_so_no_box_and_no_pay_step():
    assert _estimate(61) is None


def test_fee_box_61_nights_is_none():
    assert guest_routes._fee_box(_apartment(), _res(61), {}, None) is None


def test_estimate_61_nights_with_host_charge_is_none():
    guest = _guest(fee_host_decision="charge")
    assert guest_routes._fee_estimate(_apartment(), _res(61), {}, guest) is None


# --- 1026: guest-submitted stay dates are locked -----------------------------

def test_locked_dates_use_booking_when_no_stored_guest_record():
    res = _res(5)
    assert guest_routes._locked_stay_dates(res, None) == (res["date_from"], res["date_to"])


def test_locked_dates_use_stored_stay_not_posted_value():
    res = _res(5)
    stored = {"stay_from": "2026-03-02", "stay_to": "2026-03-04"}
    assert guest_routes._locked_stay_dates(res, stored) == ("2026-03-02", "2026-03-04")


def test_locked_dates_fall_back_to_booking_when_stored_stay_is_empty():
    res = _res(5)
    stored = {"stay_from": None, "stay_to": None}
    assert guest_routes._locked_stay_dates(res, stored) == (res["date_from"], res["date_to"])


def test_guest_routes_no_longer_read_posted_stay_fields():
    source = pathlib.Path(guest_routes.__file__).read_text(encoding="utf-8")
    assert "_stay_dates_from_form(" not in source
    assert source.count("= _locked_stay_dates(reservation, existing)") == 2
