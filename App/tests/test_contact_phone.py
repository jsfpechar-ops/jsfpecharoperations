"""Operator phone formatting does not alter guest-registration validation."""
import pytest

from app import contact_phone


@pytest.mark.parametrize(
    "value,code,number",
    [("", "", ""), ("777 000 111", "+420", "777000111"),
     ("+420777000111", "+420", "777000111"),
     ("00421 901 234 567", "+421", "901234567"),
     ("+1 (202) 555-0101", "+1", "2025550101"),
     ("+7 999 1234567", "+7", "9991234567"),
     ("+49 15123456789", "+49", "15123456789"),
     ("+971 501234567", "+971", "501234567"),
     ("office extension 12", "", "office extension 12")],
)
def test_phone_form_parts(value, code, number):
    assert contact_phone.form_parts(value) == {"code": code, "number": number}


def test_pasted_international_prefix_is_not_doubled():
    assert contact_phone.with_country_code("+420", "+49 15123456789") == "+4915123456789"
    assert contact_phone.with_country_code("49", "15123456789") == "+4915123456789"
    assert contact_phone.with_country_code("+420", "") == ""
    assert contact_phone.with_country_code("", "office extension 12") == "office extension 12"
