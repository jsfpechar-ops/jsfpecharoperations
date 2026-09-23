import xml.etree.ElementTree as ET

import pytest

from app.ubyport import errors as uby_errors
from app.ubyport import soap
from app.ubyport.client import UbyportClient, UbyportTransportError

HEADER = {
    "uIdub": "100227887600",
    "uMark": "CZGFW",
    "uName": "Apartment Vinohrady",
    "uCont": "host@example.com",
    "uOkr": "Praha 2",
    "uOb": "Praha",
    "uObCa": "Vinohrady",
    "uStr": "Korunní",
    "uHomN": "1234",
    "uOriN": "12a",
    "uPsc": "12000",
}

GUEST = {
    "cFrom": "2026-09-10T00:00:00",
    "cUntil": "2026-09-15T00:00:00",
    "cSurN": "SMITH",
    "cFirstN": "JOHN",
    "cDate": "01011990",
    "cPlac": None,
    "cNati": "GBR",
    "cDocN": "P1234567",
    "cVisN": None,
    "cResi": "Baker Street 221B, London, GBR-United Kingdom",
    "cPurp": 10,
    "cSpz": None,
    "cNote": None,
}


def local_names(parent):
    return [child.tag.rsplit("}", 1)[-1] for child in parent]


def test_envelope_is_well_formed():
    envelope = soap.build_zapis_ubytovane(HEADER, [GUEST])
    root = ET.fromstring(envelope)
    assert root.tag.endswith("Envelope")


def test_guest_fields_are_in_datacontract_alphabetical_order():
    """WCF serialises members alphabetically and the spec warns against reordering."""
    envelope = soap.build_zapis_ubytovane(HEADER, [GUEST])
    root = ET.fromstring(envelope)
    guest = None
    for element in root.iter():
        if element.tag.endswith("Ubytovany"):
            guest = element
            break
    assert guest is not None
    assert local_names(guest) == list(soap.GUEST_FIELDS)
    assert local_names(guest) == sorted(local_names(guest), key=str.lower)


def test_header_fields_are_in_expected_order_with_vracetpdf_last():
    envelope = soap.build_zapis_ubytovane(HEADER, [GUEST])
    root = ET.fromstring(envelope)
    seznam = next(el for el in root.iter() if el.tag.endswith("Seznam"))
    names = local_names(seznam)
    assert names[0] == "Ubytovani"
    assert names[1:-1] == list(soap.HEADER_FIELDS)
    assert names[-1] == "VracetPDF"


def test_none_values_become_nil_elements():
    envelope = soap.build_zapis_ubytovane(HEADER, [GUEST])
    assert 'i:nil="true"' in envelope
    root = ET.fromstring(envelope)
    plac = next(el for el in root.iter() if el.tag.endswith("cPlac"))
    assert plac.get("{http://www.w3.org/2001/XMLSchema-instance}nil") == "true"


def test_authentication_code_is_always_present():
    # The spec says the field is unused but must not be empty.
    envelope = soap.build_zapis_ubytovane(HEADER, [GUEST])
    root = ET.fromstring(envelope)
    code = next(el for el in root.iter() if el.tag.endswith("AutentificationCode"))
    assert code.text == "X"


def test_special_characters_are_escaped():
    envelope = soap.build_zapis_ubytovane(
        HEADER, [dict(GUEST, cNote="Ampersand & angle < bracket")]
    )
    assert "&amp;" in envelope and "&lt;" in envelope
    root = ET.fromstring(envelope)
    note = next(el for el in root.iter() if el.tag.endswith("cNote"))
    assert note.text == "Ampersand & angle < bracket"


def test_diacritics_survive_the_round_trip():
    envelope = soap.build_zapis_ubytovane(HEADER, [dict(GUEST, cSurN="DVOŘÁK")])
    root = ET.fromstring(envelope)
    surname = next(el for el in root.iter() if el.tag.endswith("cSurN"))
    assert surname.text == "DVOŘÁK"


RESPONSE_WITH_ERRORS = """<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
<s:Header /><s:Body>
<ZapisUbytovaneResponse xmlns="http://UBY.pcr.cz/WS_UBY">
<ZapisUbytovaneResult xmlns:a="http://schemas.datacontract.org/2004/07/WS_UBY"
 xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
<a:ChybyHlavicky>5;6;7;</a:ChybyHlavicky>
<a:ChybyZaznamu xmlns:b="http://schemas.microsoft.com/2003/10/Serialization/Arrays">
<b:string>;112;106;</b:string>
<b:string>;</b:string>
</a:ChybyZaznamu>
<a:PseudoRazitko>F8EA613D-C8C5-4671-924D-EE4F8588E08D</a:PseudoRazitko>
</ZapisUbytovaneResult></ZapisUbytovaneResponse></s:Body></s:Envelope>"""


def test_response_parsing():
    parsed = soap.parse_zapis_response(RESPONSE_WITH_ERRORS)
    assert parsed["header_errors"] == "5;6;7;"
    assert parsed["record_errors"] == [";112;106;", ";"]
    assert parsed["pseudo_stamp"] == "F8EA613D-C8C5-4671-924D-EE4F8588E08D"


def test_submit_rejects_fewer_outcomes_than_guest_records(monkeypatch):
    client = UbyportClient("https://ubyport.invalid", "user", "password")
    monkeypatch.setattr(client, "_post", lambda *_args: RESPONSE_WITH_ERRORS)

    with pytest.raises(UbyportTransportError, match="2 outcomes for 3 guest"):
        client.submit(HEADER, [GUEST, GUEST, GUEST])


def test_submit_wraps_malformed_xml_as_transport_failure(monkeypatch):
    client = UbyportClient("https://ubyport.invalid", "user", "password")
    monkeypatch.setattr(client, "_post", lambda *_args: "<html>upstream failure")

    with pytest.raises(UbyportTransportError, match="unreadable XML"):
        client.submit(HEADER, [GUEST])


def test_ubyport_redirects_are_not_followed(monkeypatch):
    class RedirectResponse:
        status_code = 302
        text = ""

    observed = {}

    def fake_post(*args, **kwargs):
        observed.update(kwargs)
        return RedirectResponse()

    monkeypatch.setattr("app.ubyport.client.requests.post", fake_post)
    client = UbyportClient(
        "https://ubyport.invalid",
        use_ntlm=False,
    )

    with pytest.raises(UbyportTransportError, match="unexpected redirect"):
        client._post("TestDostupnosti", "<Envelope />")

    assert observed["allow_redirects"] is False


def test_pseudo_stamp_accepts_the_misspelling_in_the_spec():
    xml = RESPONSE_WITH_ERRORS.replace("PseudoRazitko", "PseudoRazirko")
    assert soap.parse_zapis_response(xml)["pseudo_stamp"].startswith("F8EA613D")


def test_fault_detection():
    fault = """<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Header /><s:Body>
    <s:Fault><faultcode>s:Chyba</faultcode>
    <faultstring xml:lang="cs-CZ">Length cannot be less than zero.</faultstring>
    </s:Fault></s:Body></s:Envelope>"""
    assert "Length cannot be less than zero." in soap.parse_fault(fault)
    assert soap.parse_fault(RESPONSE_WITH_ERRORS) is None


def test_scalar_and_codelist_parsing():
    availability = """<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>
    <TestDostupnostiResponse xmlns="http://UBY.pcr.cz/WS_UBY">
    <TestDostupnostiResult>true</TestDostupnostiResult>
    </TestDostupnostiResponse></s:Body></s:Envelope>"""
    assert soap.parse_scalar_response(availability, "TestDostupnosti") == "true"

    codelist = """<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>
    <DejMiCiselnikResponse xmlns="http://UBY.pcr.cz/WS_UBY">
    <DejMiCiselnikResult xmlns:a="http://schemas.datacontract.org/2004/07/WS_UBY">
    <a:CiselnikType><a:Kod2>GB</a:Kod2><a:Kod3>GBR</a:Kod3>
    <a:TextCZ>Spojené království</a:TextCZ><a:TextENG>United Kingdom</a:TextENG></a:CiselnikType>
    </DejMiCiselnikResult></DejMiCiselnikResponse></s:Body></s:Envelope>"""
    entries = soap.parse_ciselnik_response(codelist)
    assert entries[0]["Kod3"] == "GBR"
    assert entries[0]["TextENG"] == "United Kingdom"


# --- error classification -------------------------------------------------

def test_no_errors_means_accepted():
    state, messages = uby_errors.classify("", ";")
    assert state == "accepted"
    assert messages == []


def test_a_critical_transmission_error_can_be_corrected():
    """112 means the batch never reached the register, so resending is the fix.

    The Foreign Police answered this in writing: 112 is a critical transmission
    error (1xx series) - the batch of accommodated foreigners was not received
    at all. The guest must stay retryable, not land in `blocked`.
    """
    state, messages = uby_errors.classify("", ";112;")
    assert state == "error"
    assert any("112" in m for m in messages)


def test_the_112_wording_carries_no_non_correctable_marker():
    """The fallback wording is substring-matched, so it must not trip the filter.

    classify() matches NON_CORRECTABLE_MARKERS against describe()'s output, and
    describe() falls back to KNOWN_CODES when the live code book is silent. A
    wording that happened to contain one of those markers would reclassify 112
    on its own.
    """
    assert not uby_errors.is_non_correctable(uby_errors.KNOWN_CODES["112"])


def test_a_reworded_112_from_the_code_book_is_still_correctable():
    """The police's own prose for 112 must not override the written answer.

    The cached code book is authoritative for what a code means to them, but it
    is free text: a wording change must not silently abandon a record the
    register never received.
    """
    book = {"112": "Pozdě podané hlášení - záznam nebyl přijat"}
    state, _messages = uby_errors.classify("", ";112;", book)
    assert state == "error"


def test_duplicate_is_not_correctable_by_wording():
    book = {"150": "Duplicitní záznam - data nebyla převzata"}
    state, _ = uby_errors.classify("", ";150;", book)
    assert state == "not_correctable"


def test_ordinary_field_error_is_correctable():
    state, messages = uby_errors.classify("", ";106;")
    assert state == "error"
    assert "106" in messages[0]


def test_header_error_marks_the_record_too():
    state, _ = uby_errors.classify("13;", ";")
    assert state == "error"


def test_split_codes():
    assert uby_errors.split_codes("5;6;7;") == ["5", "6", "7"]
    assert uby_errors.split_codes(";") == []
    assert uby_errors.split_codes(None) == []
