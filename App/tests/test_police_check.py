"""A4: the police setup consistency check. Fake values only (SAMPLE_*)."""
from __future__ import annotations

import pytest

from app import db, police_check, police_letter, validation
from app.ubyport_sample_pdf import SAMPLE_FACILITY_LINE1, SAMPLE_FACILITY_LINE2, SAMPLE_IDUB, SAMPLE_WS_PASSWORD, SAMPLE_WS_USER

HEAD = (
    "Přihlašovací údaje pro robotické vkládání Ubyport Webová služba\n"
    f"Přihlašovací jméno: {SAMPLE_WS_USER}\n"
    f"Přístupové heslo: {SAMPLE_WS_PASSWORD}\n"
    f"IDUB: {SAMPLE_IDUB}\n"
)
BRACKET_LETTER = HEAD + "Ubytovací zařízení:\nFIKTIVNI 1234/56 - BYT A3.3 [A33]\n(PRAHA, PRAHA 2, FIKTIVNI, 1234/56)\n"
SAMPLE_LETTER = HEAD + f"Ubytovací zařízení:\n{SAMPLE_FACILITY_LINE1}\n{SAMPLE_FACILITY_LINE2}\n"
FORM = {
    "uby_ws_user": SAMPLE_WS_USER, "uby_idub": SAMPLE_IDUB, "uby_mark": "DEMO1",
    "uby_name": "FIKTIVNI 1234/56 - BYT A3.3 [A33]", "addr_street": "Fiktivni", "addr_house_no": "1234",
}


def _letter(text):
    return police_check.letter_values(police_letter.parse_letter(text), text)


def test_bracket_short_name_is_read_and_flagged():
    letter = _letter(BRACKET_LETTER)
    assert letter["uby_mark"] == "A33"
    codes = {(f.code, f.field) for f in police_check.letter_findings(letter, FORM)}
    assert codes == {("letter_mismatch", "uby_mark")}


def test_flat_number_bracket_is_not_a_short_name():
    assert "uby_mark" not in _letter(SAMPLE_LETTER)


def test_two_different_brackets_compare_nothing():
    text = HEAD + "Ubytovací zařízení:\nFIKTIVNI [A33] [B44]\n"
    assert "uby_mark" not in _letter(text)


def test_every_compared_field_can_mismatch():
    letter = {"uby_ws_user": "UBY-WS_OTHER", "uby_idub": "111111111111", "uby_mark": "ZZ9", "uby_name": "Other 1", "address_numbers": "9 99"}
    fields = {f.field for f in police_check.letter_findings(letter, FORM)}
    assert fields == {"uby_ws_user", "uby_idub", "uby_mark", "uby_name"}
    assert any(f.code == "letter_address" for f in police_check.letter_findings(letter, FORM))


def test_equal_values_ignore_case_and_diacritics():
    letter = {"uby_name": "fiktivní 1234/56 - byt a3.3 [a33]", "uby_mark": "demo1"}
    assert police_check.letter_findings(letter, FORM) == []


def test_the_password_never_reaches_a_finding():
    letter = _letter(BRACKET_LETTER)
    assert SAMPLE_WS_PASSWORD not in repr(letter)
    texts = [police_check.render("en", f)["text"] for f in police_check.letter_findings(letter, FORM)]
    assert SAMPLE_WS_PASSWORD not in " ".join(texts)


def test_short_name_equals_login_suffix_only_while_nothing_was_accepted():
    assert [f.code for f in police_check.local_findings(FORM, has_accepted=False)] == ["mark_is_login_suffix"]
    assert police_check.local_findings(FORM, has_accepted=True) == []


def test_facility_name_without_street_or_house_number():
    form = {**FORM, "uby_mark": "OTHER", "uby_name": "Airbnb Fiktivni - A3.3"}
    assert [f.code for f in police_check.local_findings(form, has_accepted=False)] == ["name_address"]
    assert police_check.local_findings({**form, "uby_name": "FIKTIVNI 1234/56 BYT"}, has_accepted=False) == []


def test_login_prefix():
    form = {**FORM, "uby_ws_user": "PORTAL_LOGIN", "uby_mark": "OTHER"}
    assert [f.code for f in police_check.local_findings(form, has_accepted=False)] == ["login_prefix"]
    assert police_check.local_findings({**FORM, "uby_ws_user": "UBY-TWS12345", "uby_mark": "X"}, has_accepted=False) == []


@pytest.mark.parametrize("mark", ["AB CD", "ABCDEFG"])
def test_short_name_shape_is_already_a_validation_error(mark):
    """So no warning is added for it: validate_apartment reports it."""
    issues = validation.validate_apartment({"uby_idub": SAMPLE_IDUB, "uby_mark": mark, "uby_name": "X 1"})
    assert any(issue.field == "uby_mark" for issue in validation.errors_only(issues))


@pytest.mark.parametrize("lang", ["en", "cs", "vi"])
def test_every_code_has_text_in_every_language(lang):
    from app import host_i18n
    for finding in (
        police_check.Finding("letter_mismatch", "uby_mark", {"letter": "A33", "form": "DEMO1"}),
        police_check.Finding("letter_address", "uby_name", {"letter": "9", "form": "1234"}),
        police_check.Finding("mark_is_login_suffix", "uby_mark", {"mark": "DEMO1"}),
        police_check.Finding("name_address", "uby_name"),
        police_check.Finding("login_prefix", "uby_ws_user"),
        police_check.Finding("first_filing"),
    ):
        text = police_check.render(lang, finding)["text"]
        assert text and not text.startswith("police_check."), (lang, finding.code)
        assert "—" not in text


from fastapi.testclient import TestClient  # noqa: F401  (client comes from the host fixture)
from tests.test_police_letter_flow import (  # noqa: F401
    SAVED_LOGIN, _apartment, _audit_text, _payload, _paste, _status_line, host, no_client,
)

JSON = {"accept": "application/json"}


def _set(apartment_id, **values):
    db.update("apartment", apartment_id, values)


def test_paste_json_warns_about_a_printed_short_name_and_saves_nothing(host, no_client):
    before = dict(_apartment())
    response = host.post(
        f"/apartments/{before['id']}/police-letter",
        data={"letter_text": BRACKET_LETTER}, headers=JSON, follow_redirects=False,
    )
    body = response.json()
    assert any("A33" in line and "DEMO1" in line for line in body["warnings"]), body["warnings"]
    assert body["message"] and not any(line in body["message"] for line in body["warnings"])
    assert SAMPLE_WS_PASSWORD not in response.text.replace(body["fields"]["uby_ws_password"]["value"], "")
    assert dict(_apartment()) == before
    audit = _audit_text()
    assert "A33" not in audit and SAMPLE_WS_USER not in audit


def test_paste_html_shows_the_note_beside_the_short_name_box(host, no_client):
    page = _paste(host, _apartment()["id"], BRACKET_LETTER).text
    assert 'data-police-check-code="letter_mismatch"' in page
    assert "A33" in page


def test_saved_page_shows_heuristics_and_the_banner_until_a_filing_was_accepted(host):
    row = _apartment()
    _set(row["id"], uby_ws_user=SAMPLE_WS_USER, uby_mark="DEMO1", uby_idub=SAMPLE_IDUB, uby_name="Penzion Letter")
    url = f"/apartments/{row['id']}?view=settings&section=reporting"
    page = host.get(url).text
    for code in ("mark_is_login_suffix", "name_address", "first_filing"):
        assert f'data-police-check-code="{code}"' in page, code
    db.insert("submission", {"apartment_id": row["id"], "created_at": db.utcnow(), "state": "ok"})
    page = host.get(url).text
    assert 'data-police-check-code="first_filing"' not in page
    assert 'data-police-check-code="mark_is_login_suffix"' not in page
    assert 'data-police-check-code="name_address"' in page


def test_a_warning_never_blocks_the_save(host, no_client):
    row = _apartment()
    response = host.post(
        f"/apartments/{row['id']}",
        data=_payload(uby_ws_user="PORTAL_LOGIN", uby_mark="ABCDE"),
        follow_redirects=False,
    )
    assert response.status_code in (303, 422), response.text[:200]
