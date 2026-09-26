"""Czech account normalisation, SPAYD and QR helpers (stay-fee step 2).

Every expected value below is the table in docs/plans/PLAN_POPLATEK_Z_POBYTU.md §5.
"""
from __future__ import annotations

import pytest

from app import payments


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("19-2000781379/0800", ("19-2000781379/0800", "CZ3008000000192000781379")),
        ("123/0600", ("123/0600", "CZ9106000000000000000123")),
        ("30015-5157998/6000", ("30015-5157998/6000", "CZ1760000300150005157998")),
        (
            "CZ30 0800 0000 1920 0078 1379",
            ("CZ3008000000192000781379", "CZ3008000000192000781379"),
        ),
    ],
)
def test_normalise_account_accepts(raw, expected):
    assert payments.normalise_account(raw) == expected


@pytest.mark.parametrize(
    "raw, code",
    [
        ("19-2000781378/0800", "account_checksum"),
        ("abc", "account_format"),
        ("CZ3108000000192000781379", "iban_checksum"),
    ],
)
def test_normalise_account_rejects(raw, code):
    with pytest.raises(ValueError) as err:
        payments.normalise_account(raw)
    assert str(err.value) == code


def test_spayd_payload():
    payload = payments.spayd(
        "CZ9106000000000000000123", 400, "8000000042", "Poplatek z pobytu 42"
    )
    assert payload == (
        "SPD*1.0*ACC:CZ9106000000000000000123*AM:400.00*CC:CZK"
        "*X-VS:8000000042*MSG:POPLATEK Z POBYTU 42"
    )


def test_ascii_upper_strips_diacritics_and_symbols():
    assert (
        payments.ascii_upper("Příliš žluťoučký kůň * 100% ok", 60)
        == "PRILIS ZLUTOUCKY KUN 100 OK"
    )


def test_format_iban_groups_by_four():
    assert payments.format_iban("CZ3008000000192000781379") == "CZ30 0800 0000 1920 0078 1379"


def test_qr_data_uri_is_a_png_data_uri():
    assert payments.qr_data_uri("x").startswith("data:image/png;base64,")
