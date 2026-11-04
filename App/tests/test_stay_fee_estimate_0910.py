"""Brief 0910: the form-end fee estimate never raises and renders nothing when it cannot compute."""
import pytest

from app import config, routes  # noqa: F401  (import check)
from app.routes import guest as guest_routes


APARTMENT = {
    "stay_fee_collect": 1,
    "stay_fee_rate_czk": 50,
    "addr_obec": "Praha",
    "legal_entity_id": None,
}
RESERVATION = {"id": 7, "date_from": "2026-07-01", "date_to": "2026-07-04"}


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    monkeypatch.setattr(config, "STAY_FEE_GUEST_PAY", True)


def _values(**overrides):
    data = {"birth_date": "01.01.1980", "res_country": "DE", "res_city": "Berlin"}
    data.update(overrides)
    return data


def test_adult_with_stay_dates_gets_a_positive_estimate():
    result = guest_routes._fee_estimate(APARTMENT, RESERVATION, _values())
    assert result is not None
    assert result["days"] > 0
    assert result["amount"] == result["days"] * 50


@pytest.mark.parametrize("birth", ["", "   ", "xx.yy.zzzz", "31.02.1999", "--", "0"])
def test_blank_or_unparseable_birth_date_never_raises(birth):
    result = guest_routes._fee_estimate(APARTMENT, RESERVATION, _values(birth_date=birth))
    assert result is None or (result["amount"] > 0 and result["amount"] == result["days"] * 50)


def test_missing_stay_dates_render_nothing():
    no_dates = {"id": 7, "date_from": None, "date_to": None}
    assert guest_routes._fee_estimate(APARTMENT, no_dates, _values()) is None


def test_reservation_with_only_bad_dates_renders_nothing():
    bad = {"id": 7, "date_from": "not-a-date", "date_to": ""}
    assert guest_routes._fee_estimate(APARTMENT, bad, _values()) is None


def test_zero_rate_renders_nothing(monkeypatch):
    zero = dict(APARTMENT, stay_fee_rate_czk=0)
    assert guest_routes._fee_estimate(zero, RESERVATION, _values()) is None


def test_property_not_collecting_renders_nothing():
    off = dict(APARTMENT, stay_fee_collect=0)
    assert guest_routes._fee_estimate(off, RESERVATION, _values()) is None


def test_fee_qr_payload_carries_plain_vs_and_short_message():
    from app import payments
    payload = payments.spayd("CZ6508000000192000145399", 150, "2", "Stay fee 2")
    assert "*X-VS:2*" in payload
    assert payload.endswith("MSG:STAY FEE 2")
    assert "0000000002" not in payload
