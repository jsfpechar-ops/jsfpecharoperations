"""WP30: the Dorucenka PDF is requested, parsed and stored as the contract says.

Source of truth: "Technicky popis webove sluzby Ubyport", appendix 5 to the
Ubyport operating rules (policie.gov.cz, update of 19 June 2019). Section 4.2
defines class Chyby with DokumentPotvrzeni ("PDF dokument ve tvaru basecode64
obsahujici potvrzeni o zpracovani dat"); section 5.1.1 shows the wire format.
"""
from __future__ import annotations

import base64
import logging
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app import auth, db, reporting
from app.main import app
from app.ubyport import soap
from app.ubyport.client import UbyportClient
from mock_ubyport import server as mock_server

PASSWORD = "Secure-Password-123"

HEADER = {
    "uIdub": "100227887600",
    "uMark": "ABCDE",
    "uName": "Apartment Example",
    "uCont": "host@example.com",
    "uOkr": "Praha",
    "uOb": "Praha",
    "uObCa": "Vinohrady",
    "uStr": "Example",
    "uHomN": "1234",
    "uOriN": "12",
    "uPsc": "12000",
}

GUEST = {
    "cFrom": "2026-09-10T00:00:00",
    "cUntil": "2026-09-15T00:00:00",
    "cSurN": "SAMPLEGUEST",
    "cFirstN": "JOHN",
    "cDate": "01011990",
    "cPlac": None,
    "cNati": "GBR",
    "cDocN": "P1234567",
    "cVisN": None,
    "cResi": "Example Street 1, London",
    "cPurp": 10,
    "cSpz": None,
    "cNote": None,
}

PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PDF_B64 = base64.b64encode(PDF_BYTES).decode()
# The service may wrap long base64 (the 5.1.4 sample is broken across lines).
PDF_B64_WRAPPED = "\n".join(PDF_B64[i:i + 20] for i in range(0, len(PDF_B64), 20))

# Shaped exactly like appendix 5 section 5.1.1 (namespaces, prefixes), with the
# Chyby members of section 4.2 in the alphabetical order WCF serialises them.
DOCUMENTED_RESPONSE = """<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Header />
  <s:Body>
    <ZapisUbytovaneResponse xmlns="http://UBY.pcr.cz/WS_UBY">
      <ZapisUbytovaneResult xmlns:a="http://schemas.datacontract.org/2004/07/WS_UBY"
 xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
        <a:ChybyHlavicky></a:ChybyHlavicky>
        <a:ChybyZaznamu xmlns:b="http://schemas.microsoft.com/2003/10/Serialization/Arrays">
          <b:string>;</b:string>
        </a:ChybyZaznamu>
        <a:DokumentChybyPotvrzeni i:nil="true" />
        <a:DokumentPotvrzeni>{pdf}</a:DokumentPotvrzeni>
        <a:PseudoRazitko>F8EA613D-C8C5-4671-924D-EE4F8588E08D</a:PseudoRazitko>
      </ZapisUbytovaneResult>
    </ZapisUbytovaneResponse>
  </s:Body>
</s:Envelope>"""

# Appendix 5 section 5.1.1 response, verbatim apart from whitespace: no PDF.
DOCUMENTED_RESPONSE_WITHOUT_PDF = """<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Header />
  <s:Body>
    <ZapisUbytovaneResponse xmlns="http://UBY.pcr.cz/WS_UBY">
      <ZapisUbytovaneResult xmlns:a="http://schemas.datacontract.org/2004/07/WS_UBY"
 xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
        <a:ChybyHlavicky>5;6;7;8;9;10;11;12;13;</a:ChybyHlavicky>
        <a:ChybyZaznamu xmlns:b="http://schemas.microsoft.com/2003/10/Serialization/Arrays">
          <b:string>;112;106;</b:string>
        </a:ChybyZaznamu>
      </ZapisUbytovaneResult>
    </ZapisUbytovaneResponse>
  </s:Body>
</s:Envelope>"""


def _seznam_names(envelope: str):
    root = ET.fromstring(envelope)
    seznam = next(el for el in root.iter() if el.tag.endswith("Seznam"))
    return [child.tag.rsplit("}", 1)[-1] for child in seznam]


# --- request ---------------------------------------------------------------

def test_vracetpdf_sits_where_datacontractserializer_reads_it():
    names = _seznam_names(soap.build_zapis_ubytovane(HEADER, [GUEST]))
    assert names.index("VracetPDF") == names.index("Ubytovani") + 1
    assert names.index("VracetPDF") < names.index("uCont")
    assert names == sorted(names)


def test_seznam_uses_the_documented_data_contract_namespace():
    root = ET.fromstring(soap.build_zapis_ubytovane(HEADER, [GUEST]))
    seznam = next(el for el in root.iter() if el.tag.endswith("Seznam"))
    assert seznam.tag == "{http://UBY.pcr.cz/WS_UBY}Seznam"
    for child in seznam:
        assert child.tag.startswith("{http://schemas.datacontract.org/2004/07/WS_UBY}")
    vracet = next(c for c in seznam if c.tag.endswith("VracetPDF"))
    assert vracet.text == "true"


# --- parsing ---------------------------------------------------------------

def test_parser_extracts_the_dorucenka_from_the_documented_response():
    parsed = soap.parse_zapis_response(DOCUMENTED_RESPONSE.format(pdf=PDF_B64_WRAPPED))
    assert base64.b64decode(parsed["receipt_pdf"]) == PDF_BYTES
    # Stored canonical: no line breaks in the column.
    assert parsed["receipt_pdf"] == PDF_B64
    assert parsed["error_pdf"] == ""
    assert parsed["pseudo_stamp"] == "F8EA613D-C8C5-4671-924D-EE4F8588E08D"
    assert parsed["record_errors"] == [";"]
    assert parsed["pdf_problems"] == {}


def test_a_response_without_pdf_is_handled():
    parsed = soap.parse_zapis_response(DOCUMENTED_RESPONSE_WITHOUT_PDF)
    assert parsed["receipt_pdf"] == ""
    assert parsed["error_pdf"] == ""
    assert parsed["pdf_problems"] == {}
    assert parsed["header_errors"] == "5;6;7;8;9;10;11;12;13;"


@pytest.mark.parametrize(
    "content, problem",
    [
        ("not base64 !!!", "not_base64"),
        (base64.b64encode(b"<html>error</html>").decode(), "not_pdf"),
        ("", "empty"),
    ],
)
def test_an_unusable_document_is_dropped_not_stored(content, problem):
    parsed = soap.parse_zapis_response(DOCUMENTED_RESPONSE.format(pdf=content))
    assert parsed["receipt_pdf"] == ""
    assert parsed["pdf_problems"] == {"receipt_pdf": problem}


def test_an_oversized_document_is_dropped(monkeypatch):
    monkeypatch.setattr(soap, "MAX_PDF_BYTES", 16)
    parsed = soap.parse_zapis_response(DOCUMENTED_RESPONSE.format(pdf=PDF_B64))
    assert parsed["receipt_pdf"] == ""
    assert parsed["pdf_problems"] == {"receipt_pdf": "too_large"}


def test_response_element_names_are_logged_without_values(monkeypatch, caplog):
    client = UbyportClient("https://ubyport.invalid", use_ntlm=False)
    monkeypatch.setattr(
        client, "_post", lambda *_a: DOCUMENTED_RESPONSE.format(pdf=PDF_B64)
    )
    with caplog.at_level(logging.INFO, logger="ubyhost.ubyport"):
        result = client.submit(HEADER, [GUEST])
    assert result.receipt_pdf == PDF_B64
    text = caplog.text
    assert (
        "elements=ChybyHlavicky,ChybyZaznamu,DokumentChybyPotvrzeni,"
        "DokumentPotvrzeni,PseudoRazitko" in text
    )
    assert f"receipt_pdf_bytes={len(PDF_BYTES)}" in text
    assert PDF_B64 not in text
    assert "SAMPLEGUEST" not in text and "P1234567" not in text
    assert "F8EA613D" not in text


# --- mock follows the real contract ----------------------------------------

def _call_mock(envelope: str) -> str:
    with TestClient(mock_server.app) as mock:
        mock.post("/reset")
        response = mock.post(
            "/ws_uby_test/ws_uby.svc",
            content=envelope.encode(),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f"{soap.ACTION_PREFIX}ZapisUbytovane",
            },
        )
    assert response.status_code == 200
    return response.text


def test_mock_returns_the_dorucenka_for_a_correctly_ordered_request(tmp_path, monkeypatch):
    monkeypatch.setattr(mock_server, "STATE_FILE", tmp_path / "state.json")
    text = _call_mock(soap.build_zapis_ubytovane(HEADER, [GUEST]))
    parsed = soap.parse_zapis_response(text)
    assert base64.b64decode(parsed["receipt_pdf"]).startswith(b"%PDF")
    names = soap.response_element_names(text)
    assert names == sorted(names)


def test_mock_ignores_vracetpdf_sent_after_the_header_like_wcf(tmp_path, monkeypatch):
    """The pre-WP30 order: VracetPDF last. WCF skips it, so no Dorucenka."""
    monkeypatch.setattr(mock_server, "STATE_FILE", tmp_path / "state.json")
    envelope = soap.build_zapis_ubytovane(HEADER, [GUEST])
    flag = "<d:VracetPDF>true</d:VracetPDF>"
    assert flag in envelope
    old_order = envelope.replace(flag, "").replace("</Seznam>", flag + "</Seznam>")
    parsed = soap.parse_zapis_response(_call_mock(old_order))
    assert parsed["receipt_pdf"] == ""
    assert parsed["pseudo_stamp"]


# --- storage and download --------------------------------------------------

def _seed_owned(username: str, token: str):
    from tests.test_send_controls import _seed

    db.init_db()
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (username,))
    owner_id = existing["id"] if existing else auth.create_account(
        username, PASSWORD, "Receipt Owner", must_change_password=False
    )
    apartment, _reservation, guest_id = _seed("manual", token, owner_user_id=owner_id)
    return apartment, guest_id


def _cleanup(apartment):
    """Leave the database as found: the end-to-end suite expects it empty."""
    apartment_id = apartment["id"]
    db.execute("DELETE FROM alert WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM submission WHERE apartment_id = ?", (apartment_id,))
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment_id,),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment_id,))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment_id,))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def _submit_with_response(monkeypatch, apartment, response_xml):
    real = UbyportClient("https://ubyport.invalid", use_ntlm=False)
    monkeypatch.setattr(real, "_post", lambda *_a: response_xml)
    monkeypatch.setattr(reporting, "client_for", lambda *_a, **_k: real)
    monkeypatch.setattr(reporting.validation, "validate_apartment", lambda _a: [])
    pairs = reporting.collect_sendable(apartment["id"], ignore_automation=True)
    return reporting.submit_batch(apartment, pairs, mode="manual")


def _login(username):
    client = TestClient(app)
    response = client.post(
        "/login?lang=en",
        data={"username": username, "password": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client


def test_the_dorucenka_is_stored_and_downloads_as_pdf(monkeypatch):
    apartment, guest_id = _seed_owned("wp30-receipt", "tok-wp30-receipt")
    try:
        _submit_with_response(
            monkeypatch, apartment, DOCUMENTED_RESPONSE.format(pdf=PDF_B64_WRAPPED)
        )
        submission = db.query_one(
            "SELECT * FROM submission WHERE apartment_id = ? ORDER BY id DESC",
            (apartment["id"],),
        )
        assert submission["state"] == "ok"
        assert submission["receipt_pdf"] == PDF_B64
        guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
        assert guest["receipt_submission_id"] == submission["id"]

        response = _login("wp30-receipt").get(f"/submissions/{submission['id']}/receipt.pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content == PDF_BYTES
    finally:
        _cleanup(apartment)


def test_an_accept_without_pdf_stores_nothing_and_download_says_so(monkeypatch):
    apartment, _guest_id = _seed_owned("wp30-nopdf", "tok-wp30-nopdf")
    no_pdf = DOCUMENTED_RESPONSE.replace(
        "<a:DokumentPotvrzeni>{pdf}</a:DokumentPotvrzeni>",
        '<a:DokumentPotvrzeni i:nil="true" />',
    )
    try:
        _submit_with_response(monkeypatch, apartment, no_pdf)
        submission = db.query_one(
            "SELECT * FROM submission WHERE apartment_id = ? ORDER BY id DESC",
            (apartment["id"],),
        )
        assert submission["state"] == "ok"
        assert submission["receipt_pdf"] is None
        assert submission["pseudo_stamp"]
        response = _login("wp30-nopdf").get(f"/submissions/{submission['id']}/receipt.pdf")
        assert response.status_code == 404
    finally:
        _cleanup(apartment)
