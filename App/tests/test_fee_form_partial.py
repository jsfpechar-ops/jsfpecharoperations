"""0205: a shorter stay-fee form (the setup wizard) never wipes stored office details."""
from __future__ import annotations

from starlette.datastructures import FormData

from app.routes import stay_fees

KEPT = (
    "stay_fee_authority_name", "stay_fee_authority_address", "stay_fee_authority_contact",
    "stay_fee_authority_databox", "stay_fee_payee", "stay_fee_instruction",
)


def test_a_form_without_the_office_fields_leaves_them_out():
    values = stay_fees.fee_form_values(FormData([
        ("stay_fee_rate_czk", "30"), ("stay_fee_vs", "123"),
        ("account_number", "2000145399"), ("account_bank", "0800"),
    ]))
    assert values["stay_fee_rate_czk"] == 30 and values["stay_fee_vs"] == "123"
    assert "stay_fee_cadence" not in values  # 0239: the wizard does not ask the period
    for key in KEPT:
        assert key not in values, key


def test_a_full_form_still_writes_the_office_fields():
    values = stay_fees.fee_form_values(FormData([(key, "") for key in KEPT]))
    for key in KEPT:
        assert key in values and values[key] is None, key
