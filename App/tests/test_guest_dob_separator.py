"""UX-122 (audit A-35, cross-cutting): the DOB field speaks dotted dates.

Every other date the app prints is "24.09.2026", so the date-of-birth field
auto-inserts dots too instead of forcing "01/01/1990".
"""
import re
from pathlib import Path

from app import i18n, validation, validation_i18n

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"

DATE_MESSAGE = "Enter the full date as DD.MM.YYYY."


def test_the_guest_form_placeholder_matches_the_displayed_dates():
    assert i18n.STRINGS["en"]["date_placeholder"] == "DD.MM.YYYY"
    assert i18n.STRINGS["cs"]["date_placeholder"] == "DD.MM.RRRR"


def test_the_birth_date_help_shows_a_dotted_example():
    assert i18n.STRINGS["en"]["birth_date_help"] == (
        "Day, month, year — e.g. 04.07.1990 for 4 July 1990. Dots are added for you."
    )
    assert i18n.STRINGS["cs"]["birth_date_help"] == (
        "Den, měsíc, rok — např. 04.07.1990 pro 4. července 1990. Tečky se doplní samy."
    )
    # The old wording told the guest to expect slashes.
    for lang in ("en", "cs"):
        assert "/" not in i18n.STRINGS[lang]["birth_date_help"]


def test_the_stored_date_is_displayed_with_dots():
    assert validation.display_birth_date("04071990") == "04.07.1990"
    # An unknown day is written as zero, which appendix 3 allows.
    assert validation.display_birth_date("00051950") == "00.05.1950"


def test_the_guest_dob_messages_ask_for_dotted_dates():
    assert validation_i18n.CS_MESSAGES[DATE_MESSAGE] == (
        "Zadejte celé datum ve formátu DD.MM.RRRR."
    )
    assert validation_i18n.GUEST_EN_MESSAGES[DATE_MESSAGE] == (
        "Date of birth: enter the full date as DD.MM.YYYY."
    )
    assert validation_i18n.GUEST_CS_MESSAGES[DATE_MESSAGE] == (
        "Datum narození: zadejte celé datum ve formátu DD.MM.RRRR."
    )


def test_the_validation_issue_uses_the_dotted_wording():
    issues = validation.validate_birth_date("1990", None)
    assert [issue.message for issue in issues] == [DATE_MESSAGE]


def _format_digits(source: str, func: str) -> str:
    match = re.search(r"function " + func + r"\(digits\) \{(.*?)\n    \}", source, re.S)
    assert match, f"{func} disappeared"
    return match.group(1)


def test_both_birth_date_inputs_insert_dots():
    for name in ("signature.js", "app.js"):
        body = _format_digits((STATIC / name).read_text(encoding="utf-8"), "formatDigits")
        assert 'out += "." + digits.slice(2, 4)' in body, name
        assert 'out += "." + digits.slice(4, 8)' in body, name
        assert '"/"' not in body, name


def test_the_readback_still_parses_the_dotted_value():
    source = (STATIC / "signature.js").read_text(encoding="utf-8")
    # Without this the read-back would silently stop matching its own output.
    assert r"/^(\d{2})\.(\d{2})\.(\d{4})$/" in source
    assert r"/^(\d{2})\/(\d{2})\/(\d{4})$/" not in source
