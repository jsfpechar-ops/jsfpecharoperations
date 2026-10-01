"""Czech account editor helpers."""
from app import payments


def test_iban_only_account_is_preserved_when_domestic_fields_are_empty():
    iban = "CZ9106000000000000000123"
    assert payments.preserve_iban_only_account(iban, "", "", "") is True


def test_domestic_fields_can_clear_a_domestic_account():
    assert payments.preserve_iban_only_account("123/0600", "", "", "") is False


def test_entered_domestic_fields_always_update():
    assert payments.preserve_iban_only_account("CZ9106000000000000000123", "", "123", "0600") is False
