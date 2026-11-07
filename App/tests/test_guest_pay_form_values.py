"""Guest-pay form parsing: the operator account must reach the internal raw key."""
from __future__ import annotations

from starlette.datastructures import FormData

from app.routes import stay_fees
from app.routes.stay_fees import GUEST_OPERATOR_ACCOUNT_RAW


def test_operator_account_in_the_form_maps_to_the_internal_raw_key():
    values = stay_fees.guest_pay_values(FormData([
        ("stay_fee_collect", "1"),
        ("stay_fee_guest_rails", "qr"),
        ("stay_fee_guest_operator_account", "19-2000145399/0800"),
    ]))
    assert values[GUEST_OPERATOR_ACCOUNT_RAW] == "19-2000145399/0800"
    assert values["stay_fee_collect"] == 1
    assert values["stay_fee_guest_rails"] == "iban"


def test_operator_account_left_out_means_leave_the_stored_account():
    values = stay_fees.guest_pay_values(FormData([
        ("stay_fee_collect", "0"),
        ("stay_fee_guest_rails", "cash"),
    ]))
    assert GUEST_OPERATOR_ACCOUNT_RAW not in values
