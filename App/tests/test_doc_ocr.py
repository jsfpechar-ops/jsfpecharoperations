"""Document scanning (OCR): local Tesseract MRZ read, Max plan only.

A suggestion, never a record: the scan route reads the photo the guest chose
and returns form values; nothing lands in the database or the photo store.
The engine is a local subprocess; tests monkeypatch it, so no binary is
needed to run them.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config, db
from app import doc_ocr
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim
from tests.test_guest_navigation import (
    _cleanup,
    _make_apartment_with_stays,
    _passport_files,
    PNG_BYTES,
    TOKEN,
)


def _jpeg(width=2000, height=1500):
    out = io.BytesIO()
    Image.new("RGB", (width, height), (200, 200, 200)).save(out, format="JPEG")
    return out.getvalue()


def _check(text: str) -> str:
    total = 0
    weights = (7, 3, 1)
    for i, ch in enumerate(text):
        value = "0123456789".find(ch)
        if value < 0:
            value = 0 if ch == "<" else 10 + ord(ch) - ord("A")
        total += value * weights[i % 3]
    return str(total % 10)


def _td3_text(doc: str = "P1234567", surname: str = "SMITH", given: str = "JOHN PAUL",
              nationality: str = "GBR", birth: str = "900101") -> str:
    doc = doc.ljust(9, "<")[:9]
    line2 = doc + _check(doc) + nationality + birth + _check(birth)
    line2 = line2.ljust(44, "<")
    line1 = ("P<" + nationality + surname.replace(" ", "<") + "<<" +
              given.replace(" ", "<")).ljust(44, "<")
    return line1 + "\n" + line2 + "\n"


def _td1_text(doc: str = "ID1234567", surname: str = "NOVAK", given: str = "JANA",
              nationality: str = "CZE", birth: str = "850505") -> str:
    doc = doc.ljust(9, "<")[:9]
    line1 = ("ID" + nationality + doc + _check(doc)).ljust(30, "<")
    # TD1 line 2: birth(6) check(1) sex(1) expiry(6) check(1) nationality(3).
    expiry = "300101"
    line2 = birth + _check(birth) + "M" + expiry + _check(expiry) + nationality
    line2 = line2.ljust(30, "<")
    line3 = (surname + "<<" + given).ljust(30, "<")
    return line1 + "\n" + line2 + "\n" + line3 + "\n"


def _max_owner(monkeypatch):
    """Give the fixture apartment an owner with an active Max subscription."""
    monkeypatch.setattr(config, "AI_TEST_EMAILS", "")
    monkeypatch.setattr(doc_ocr, "TESSERACT", "/usr/bin/tesseract")
    monkeypatch.setattr(billing_mod(), "entitlements", _max_entitlements)
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if (apartment["passport_photo_policy"] or "off") != "required_foreign":
        db.update("apartment", apartment["id"], {"passport_photo_policy": "required_foreign"})
    if not apartment["owner_user_id"]:
        owner_id = db.insert(
            "user_account",
            {
                "username": "ocr-owner",
                "password_hash": "x",
                "created_at": "2026-01-01",
                "must_change_password": 0,
            },
        )
        db.update("apartment", apartment["id"], {"owner_user_id": owner_id})
        apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    db.execute(
        "INSERT INTO billing_account (owner_user_id, status, plan, updated_at) "
        "VALUES (?, 'active', 'max', '2026-01-01') ON CONFLICT(owner_user_id) DO UPDATE SET "
        "status = 'active', plan = 'max'",
        (apartment["owner_user_id"],),
    )
    return apartment


def billing_mod():
    from app import billing

    return billing


def _max_entitlements(owner_user_id: int):
    from app import billing

    return billing.Entitlements(status="active", plan="max")


@pytest.fixture
def browser():
    db.init_db()
    token, stay, _other = _make_apartment_with_stays()
    client = TestClient(app)
    client.cookies.set(guest.LANG_COOKIE, "en")
    complete_guest_claim(client, token, stay, party_size=2)
    yield client, token, stay
    _cleanup()
    db.execute("DELETE FROM billing_account WHERE plan = 'max'")
    db.execute("DELETE FROM user_account WHERE username = 'ocr-owner'")


def _scan(client, token, stay, files=None):
    return client.post(
        f"/l/{token}/{stay}/scan",
        files=files if files is not None else _passport_files(),
        follow_redirects=False,
    )


# --- availability gates -------------------------------------------------------

def test_off_without_tesseract(browser, monkeypatch):
    _, token, stay = browser
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    monkeypatch.setattr(doc_ocr, "TESSERACT", "")
    monkeypatch.setattr(config, "AI_TEST_EMAILS", "")
    assert not doc_ocr.available(apartment)


def test_off_for_standard_and_trial_plans(browser, monkeypatch):
    _, token, stay = browser
    apartment = _max_owner(monkeypatch)
    assert doc_ocr.available(apartment)
    real = billing_mod().entitlements

    def standard(owner_user_id):
        return billing_mod().Entitlements(status="active", plan="standard")

    monkeypatch.setattr(billing_mod(), "entitlements", standard)
    assert not doc_ocr.available(apartment)

    def trial(owner_user_id):
        return billing_mod().Entitlements(status="trialing", plan="max")

    monkeypatch.setattr(billing_mod(), "entitlements", trial)
    assert not doc_ocr.available(apartment)
    monkeypatch.setattr(billing_mod(), "entitlements", real)


def test_the_form_hides_the_button_until_max_and_installed(browser, monkeypatch):
    client, token, stay = browser
    monkeypatch.setattr(doc_ocr, "TESSERACT", "")
    page = client.get(f"/l/{token}/{stay}/new?lang=en")
    assert "ocr-scan-toggle" not in page.text
    _max_owner(monkeypatch)
    page = client.get(f"/l/{token}/{stay}/new?lang=en")
    assert "ocr-scan-toggle" in page.text


# --- the route --------------------------------------------------------------

def test_the_scan_returns_values_and_stores_nothing(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    monkeypatch.setattr(doc_ocr, "run_tesseract", lambda jpeg: _td3_text())
    res = _scan(client, token, stay)
    assert res.status_code == 200
    data = res.json()
    assert data["kind"] == "values"
    assert data["values"] == {
        "surname": "SMITH", "first_name": "JOHN PAUL", "birth_date": "01011990",
        "nationality": "GBR", "doc_number": "P1234567",
    }
    # A suggestion, never a record: the read stored nothing.
    assert db.query_one("SELECT COUNT(*) AS n FROM guest")["n"] == 0


def test_the_scan_reads_a_td1_id_card_too(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    monkeypatch.setattr(doc_ocr, "run_tesseract", lambda jpeg: _td1_text())
    res = _scan(client, token, stay)
    assert res.status_code == 200
    values = res.json()["values"]
    assert values["surname"] == "NOVAK"
    assert values["doc_number"] == "ID1234567"


def test_a_pdf_is_refused_before_any_ocr(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    from tests.test_guest_navigation import MINIMAL_PDF

    res = _scan(client, token, stay, files={"passport_photo": ("form.pdf", MINIMAL_PDF, "application/pdf")})
    assert res.status_code == 400
    assert res.json()["kind"] == "error"


def test_an_unreadable_zone_is_422(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    monkeypatch.setattr(doc_ocr, "run_tesseract", lambda jpeg: "hello world\nnothing here\n")
    res = _scan(client, token, stay)
    assert res.status_code == 422
    assert res.json()["kind"] == "error"


def test_a_bad_check_digit_is_refused_not_guessed(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    text = _td3_text()
    # Corrupt the document-number check digit.
    lines = text.splitlines()
    bad = lines[1][:9] + ("0" if lines[1][9] != "0" else "1") + lines[1][10:]
    monkeypatch.setattr(doc_ocr, "run_tesseract", lambda jpeg: lines[0] + "\n" + bad + "\n")
    res = _scan(client, token, stay)
    assert res.status_code == 422


def test_a_missing_engine_answers_503(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    monkeypatch.setattr(doc_ocr, "TESSERACT", "")
    res = _scan(client, token, stay)
    assert res.status_code == 503
    assert res.json()["kind"] == "unavailable"


def test_a_claimless_browser_cannot_scan(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    stranger = TestClient(app)
    stranger.cookies.set(guest.LANG_COOKIE, "en")
    res = _scan(stranger, token, stay)
    assert res.status_code in (303, 403)


# --- image handling ---------------------------------------------------------

def test_prepare_image_shrinks_and_greyscales():
    big = _jpeg(3000, 2000)
    out = doc_ocr.prepare_image(big, "image/jpeg")
    with Image.open(io.BytesIO(out)) as image:
        assert image.format == "JPEG"
        assert image.mode == "L"
        assert max(image.size) <= doc_ocr.MAX_EDGE
    small = doc_ocr.prepare_image(PNG_BYTES, "image/png")
    assert small[:2] == b"\xff\xd8"  # JPEG magic


def test_prepare_image_refuses_a_pdf():
    from tests.test_guest_navigation import MINIMAL_PDF

    with pytest.raises(doc_ocr.BadDocument):
        doc_ocr.prepare_image(MINIMAL_PDF, "application/pdf")


# --- MRZ parsing ------------------------------------------------------------

def test_check_digits_are_the_icao_731_weights():
    # The module and this file's helper must agree on the 7-3-1 weights.
    for field in ("520927", "901010", "P1234567", "ID123456"):
        assert doc_ocr._check_digit(field) == _check(field)


def test_o_and_zero_confusion_resolves_by_check_digit():
    line1, line2 = _td3_text().splitlines()
    # The misread: 0 read as O inside the document number.
    misread = line2[:9].replace("0", "O") + line2[9:]
    values = doc_ocr._td3(line1, misread)
    assert values and values["doc_number"] == "P1234567"


def test_td3_requires_the_passport_marker():
    line1, line2 = _td3_text().splitlines()
    assert doc_ocr._td3("I<" + line1[2:], line2) is None


def test_nationality_is_validated_against_the_country_list():
    text = _td3_text(nationality="XX")  # not an ISO code the list knows
    with pytest.raises(doc_ocr.NothingRead):
        doc_ocr.parse_mrz(text)
