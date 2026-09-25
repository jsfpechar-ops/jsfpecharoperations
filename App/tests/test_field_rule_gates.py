"""Two rules that validation used to wave through.

Purpose of stay is a required UbyPort field, but an empty one passed because
the check only fired on a value it did not recognise. And the forbidden
characters were only ever removed by the normalisers, so a value that reached
the database by some other route validated clean and went on the wire.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import validation, validation_i18n


def _record(**overrides):
    base = {
        "surname": "SMITH",
        "first_name": "JOHN",
        "birth_date": "01011990",
        "nationality": "GBR",
        "doc_number": "P1234567",
        "res_street": "Baker Street 1",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "note": "",
    }
    base.update(overrides)
    return base


def _messages(record):
    stay_from = date.today()
    return [
        issue.message
        for issue in validation.errors_only(
            validation.validate_guest(record, stay_from, stay_from + timedelta(days=2))
        )
    ]


def test_a_clean_record_still_passes():
    assert _messages(_record()) == []


def test_an_empty_purpose_of_stay_is_refused():
    """UbyPort requires it; an empty one used to submit as no value at all."""
    fields = [
        issue.field
        for issue in validation.errors_only(
            validation.validate_guest(_record(purpose=""))
        )
    ]
    assert "purpose" in fields


def test_an_unknown_purpose_is_still_named_separately():
    assert "Unknown purpose-of-stay code." in _messages(_record(purpose="ZZ"))


@pytest.mark.parametrize(
    "field", ["surname", "first_name", "doc_number", "res_street", "res_city", "note"]
)
@pytest.mark.parametrize("bad", ["|", "\r", "\n"])
def test_the_batch_separator_is_refused_wherever_it_appears(field, bad):
    """One pipe anywhere breaks the field framing for the whole submission."""
    problems = [
        issue.field
        for issue in validation.errors_only(
            validation.validate_guest(_record(**{field: f"VAL{bad}UE"}))
        )
    ]
    assert field in problems, f"a {bad!r} in {field} validated clean"


def test_every_new_message_has_czech():
    """A Czech guest must not be handed an English field rule."""
    for record in (_record(purpose=""), _record(surname="A|B")):
        for message in _messages(record):
            assert message in validation_i18n.CS_MESSAGES, message


def test_normalising_still_removes_them_so_the_forms_are_not_dead_ends():
    """Validation is the gate; the normaliser is still what fixes typed input."""
    cleaned = validation.normalise_guest(_record(surname="SMI|TH", note="a\nb"))
    assert "|" not in cleaned["surname"]
    assert "\n" not in cleaned["note"]
    assert _messages(cleaned) == []
