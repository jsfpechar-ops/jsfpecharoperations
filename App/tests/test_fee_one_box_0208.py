"""0208: the stay-fee account is one box; the server splits and checks it."""
from __future__ import annotations

from starlette.datastructures import FormData

from app.routes import stay_fees


def _saved(pairs):
    values = stay_fees.fee_form_values(FormData(pairs))
    stay_fees.apply_fee_account(values)
    return values


def test_one_box_with_spaces_and_dashes_is_split_and_becomes_an_iban():
    values = _saved([("stay_fee_rate_czk", "30"), ("stay_fee_council_account", "19 - 2000145399 / 0800")])
    assert values["stay_fee_council_account"] == "19-2000145399/0800"
    assert values["stay_fee_council_iban"].startswith("CZ")


def test_one_box_with_an_iban_is_saved_as_that_iban():
    values = _saved([("stay_fee_rate_czk", "30"), ("stay_fee_council_account", "CZ6508000000192000145399")])
    assert values["stay_fee_council_iban"] == "CZ6508000000192000145399"


def test_a_form_without_the_account_box_keeps_the_stored_account():
    values = stay_fees.fee_form_values(FormData([("stay_fee_rate_czk", "30"), ("stay_fee_vs", "123")]))
    assert stay_fees.FEE_ACCOUNT_RAW not in values
    stay_fees.apply_fee_account(values)
    assert "stay_fee_council_account" not in values
    assert "stay_fee_council_iban" not in values
