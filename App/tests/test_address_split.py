"""Czech property address: one line in, police parts out."""
from __future__ import annotations

import pytest

from app import validation


@pytest.mark.parametrize(
    "line,expected",
    [
        (
            "Vinohradská 1234/12, 120 00 Praha 2",
            {
                "addr_street": "Vinohradská",
                "addr_house_no": "1234",
                "addr_orient_no": "12",
                "addr_zip": "12000",
                "addr_obec": "Praha 2",
            },
        ),
        (
            "Street 1234/12a, 120 00 Praha",
            {
                "addr_street": "Street",
                "addr_house_no": "1234",
                "addr_orient_no": "12a",
                "addr_zip": "12000",
                "addr_obec": "Praha",
            },
        ),
        (
            "Street 1234, 120 00 Praha",
            {
                "addr_street": "Street",
                "addr_house_no": "1234",
                "addr_zip": "12000",
                "addr_obec": "Praha",
            },
        ),
        (
            "Obec 123, 54321 Obec",
            {
                "addr_house_no": "123",
                "addr_zip": "54321",
                "addr_obec": "Obec",
            },
        ),
        (
            "č.p. 123, 12000 Praha",
            {"addr_house_no": "123", "addr_zip": "12000", "addr_obec": "Praha"},
        ),
        (
            "cp. E123, 12000 Praha",
            {"addr_house_no": "E123", "addr_zip": "12000", "addr_obec": "Praha"},
        ),
        (
            "Main 12E, 12000 Praha",
            {"addr_street": "Main", "addr_house_no": "12E", "addr_zip": "12000", "addr_obec": "Praha"},
        ),
        (
            "Hlavní 1, 12000 Praha 2 - Vinohrady",
            {
                "addr_street": "Hlavní",
                "addr_house_no": "1",
                "addr_zip": "12000",
                "addr_obec": "Praha 2",
                "addr_obec_cast": "Vinohrady",
            },
        ),
        ("", {}),
        ("not an address at all", {}),
        (
            "Street 99999, 12000 Praha",
            {"addr_zip": "12000", "addr_obec": "Praha"},
        ),
        (
            "Street  1234/12,12000  Praha",
            {
                "addr_street": "Street",
                "addr_house_no": "1234",
                "addr_orient_no": "12",
                "addr_zip": "12000",
                "addr_obec": "Praha",
            },
        ),
    ],
)
def test_split_czech_address(line: str, expected: dict):
    assert validation.split_czech_address(line) == expected


def test_merge_fills_only_empty_fields():
    payload = {
        "addr_street": "Host street",
        "addr_house_no": "",
        "addr_orient_no": "",
        "addr_zip": "",
        "addr_obec": "",
        "addr_obec_cast": "",
    }
    split = validation.split_czech_address("Other 99/1, 11000 Praha 1")
    mismatch = validation.merge_split_address_fields(payload, split)
    assert mismatch is True
    assert payload["addr_street"] == "Host street"
    assert payload["addr_house_no"] == "99"
    assert payload["addr_orient_no"] == "1"
    assert payload["addr_zip"] == "11000"
    assert payload["addr_obec"] == "Praha 1"


def test_merge_no_conflict_when_empty_details():
    payload = {field: "" for field in validation._ADDR_SPLIT_FIELDS}
    split = validation.split_czech_address("Vinohradská 1234/12, 120 00 Praha 2")
    mismatch = validation.merge_split_address_fields(payload, split)
    assert mismatch is False
    assert payload["addr_street"] == "Vinohradská"
    assert payload["addr_house_no"] == "1234"


def test_compose_round_trip():
    parts = {
        "addr_street": "Vinohradská",
        "addr_house_no": "1234",
        "addr_orient_no": "12",
        "addr_zip": "12000",
        "addr_obec": "Praha 2",
    }
    line = validation.compose_czech_address_line(parts)
    assert validation.split_czech_address(line) == parts
