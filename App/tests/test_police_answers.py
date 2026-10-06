"""Pins the Foreign Police's written answers (ŘSCP, 24 September 2026).

CPR-34587-2/ČJ-2026-930023 answered the open web-service questions. Each test
names the answer it holds the code and the mock to.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, timedelta

from app import config, validation
from app.ubyport import errors as uby_errors
from mock_ubyport import server as mock


def _guest(**fields) -> ET.Element:
    values = {
        "cSurN": "NOVAK",
        "cFirstN": "JAN",
        "cDate": "01011990",
        "cNati": "DEU",
        "cDocN": "C01X00T47",
        "cPurp": "10",
        "cVisN": "",
        "cResi": "BERLIN 1",
        "cFrom": date.today().isoformat(),
        "cUntil": (date.today() + timedelta(days=2)).isoformat(),
    }
    values.update(fields)
    guest = ET.Element("UbytovanyType")
    for name, value in values.items():
        child = ET.SubElement(guest, name)
        child.text = value
    return guest


def test_a1_a2_severity_decides_accepted():
    """0-2 accepted, 4-6 not accepted."""
    for severity in (0, 1, 2):
        assert uby_errors.classify("", ";900;", severities={"900": severity})[0] == "accepted"
    for severity in (4, 5, 6):
        assert uby_errors.classify("", ";900;", severities={"900": severity})[0] != "accepted"


def test_a4_112_is_reported_late_and_accepted_in_the_mock():
    late = _guest(cFrom=(date.today() - timedelta(days=14)).isoformat())
    codes, fingerprint = mock._validate_guest(late, "123456789012", [])
    assert codes == ["112"]
    assert fingerprint
    assert not mock._refused(codes)
    assert uby_errors.classify("", ";112;")[0] == "accepted"


def test_a3_duplicate_key_ignores_visa_and_address():
    _codes, fingerprint = mock._validate_guest(_guest(), "123456789012", [])
    again = _guest(cVisN="CZE123456", cResi="MUNICH 2")
    codes, _ = mock._validate_guest(again, "123456789012", [fingerprint])
    assert "150" in codes


def test_a3_duplicate_key_includes_purpose():
    _codes, fingerprint = mock._validate_guest(_guest(), "123456789012", [])
    codes, _ = mock._validate_guest(_guest(cPurp="01"), "123456789012", [fingerprint])
    assert "150" not in codes


def test_mock_code_book_uses_the_real_layout():
    xml = mock._ciselnik("Chyby")
    assert "<a:Kod2>ERR_CZE_112</a:Kod2><a:Kod3>Oznámeno pozdě</a:Kod3>" in xml
    assert "<a:TextKratkyCZ>0</a:TextKratkyCZ>" in xml


def test_d1_batch_limit_is_32():
    assert mock.MAX_BATCH == 32
    assert config.UBYPORT_MAX_BATCH == 32


def test_b4_endpoints_match_appendix_5():
    assert config.UBYPORT_ENDPOINTS["test"] == "https://ubyport.pcr.cz/ws_uby_test/ws_uby.svc"
    assert config.UBYPORT_ENDPOINTS["prod"] == "https://ubyport.pcr.cz/ws_uby/ws_uby.svc"


def test_the_issued_test_account_abbreviation_validates():
    """The police issued a six-character abbreviation for the WS test account."""
    assert validation._MARK_RE.match("AAKLI")
    assert validation._MARK_RE.match("ABC123")
    assert not validation._MARK_RE.match("AB1")
    assert not validation._MARK_RE.match("TOOLONG1")
