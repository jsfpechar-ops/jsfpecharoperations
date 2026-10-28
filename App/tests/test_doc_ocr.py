"""Document scanning (OCR): the Max-plan guest prefill, through the one AI door.

A suggestion, never a record: the scan route reads the photo the guest chose
and returns form values; nothing lands in the database or the photo store.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import ai, config, db
from app.main import app
from app.routes import guest
from app import doc_ocr
from tests.ai_fake import FakeClient, reply
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


def _max_owner(monkeypatch):
    """Give the fixture apartment an owner on the AI test list, active on Max."""
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"doc_ocr"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "AI_TEST_EMAILS", "")
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
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


@pytest.fixture
def browser():
    db.init_db()
    token, stay, _other = _make_apartment_with_stays()
    client = TestClient(app)
    client.cookies.set(guest.LANG_COOKIE, "en")
    complete_guest_claim(client, token, stay, party_size=2)
    yield client, token, stay
    ai.set_client_for_tests(None)
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

def test_off_without_the_flag_and_key(browser, monkeypatch):
    _, token, stay = browser
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    monkeypatch.setattr(config, "AI_FEATURES", frozenset())
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    assert not doc_ocr.available(apartment)
    monkeypatch.setattr(config, "AI_FEATURES", frozenset({"doc_ocr"}))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    assert not doc_ocr.available(apartment)


def test_off_for_the_mistral_provider(browser, monkeypatch):
    _, token, stay = browser
    apartment = _max_owner(monkeypatch)
    monkeypatch.setattr(config, "AI_PROVIDER", "mistral")
    assert not doc_ocr.available(apartment)


def test_off_for_standard_and_trial_plans(browser, monkeypatch):
    _, token, stay = browser
    apartment = _max_owner(monkeypatch)
    assert doc_ocr.available(apartment)
    db.execute(
        "UPDATE billing_account SET plan = 'standard' WHERE owner_user_id = ?",
        (apartment["owner_user_id"],),
    )
    assert not doc_ocr.available(apartment)
    db.execute(
        "UPDATE billing_account SET status = 'trialing', plan = 'max' WHERE owner_user_id = ?",
        (apartment["owner_user_id"],),
    )
    assert not doc_ocr.available(apartment)


def test_the_form_hides_the_button_until_max_and_flagged(browser, monkeypatch):
    client, token, stay = browser
    page = client.get(f"/l/{token}/{stay}/new?lang=en")
    assert "ocr-scan-btn" not in page.text
    _max_owner(monkeypatch)
    page = client.get(f"/l/{token}/{stay}/new?lang=en")
    assert "ocr-scan-btn" in page.text


# --- the route --------------------------------------------------------------

def test_the_scan_returns_values_and_stores_nothing(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    fake = FakeClient([reply({
        "surname": "Smith", "first_name": "John Paul", "birth_date": "1990-01-01",
        "nationality": "GBR", "doc_number": "P 1234567",
    })])
    ai.set_client_for_tests(fake)
    res = _scan(client, token, stay)
    assert res.status_code == 200
    data = res.json()
    assert data["kind"] == "values"
    assert data["values"] == {
        "surname": "SMITH", "first_name": "JOHN PAUL", "birth_date": "01011990",
        "nationality": "GBR", "doc_number": "P1234567",
    }
    kwargs = fake.calls[0]
    assert kwargs["model"] == "claude-haiku-5-5"
    block = kwargs["messages"][0]["content"][0]
    assert block["type"] == "image"
    assert block["source"]["media_type"] == "image/jpeg"
    # A suggestion, never a record: the read stored nothing.
    assert db.query_one("SELECT COUNT(*) AS n FROM guest")["n"] == 0
    assert not db.query_one("SELECT * FROM ai_usage WHERE feature = 'doc_ocr' AND key = ''")


def test_the_scan_sends_the_property_key_and_records_usage(browser, monkeypatch):
    client, token, stay = browser
    apartment = _max_owner(monkeypatch)
    db.execute("DELETE FROM ai_usage WHERE feature = 'doc_ocr'", ())
    fake = FakeClient([reply({
        "surname": "SMITH", "first_name": "JOHN", "birth_date": "1990-01-01",
        "nationality": "GBR", "doc_number": "P1234567",
    })])
    ai.set_client_for_tests(fake)
    res = _scan(client, token, stay)
    assert res.status_code == 200
    row = db.query_one("SELECT * FROM ai_usage WHERE feature = 'doc_ocr'")
    assert row["key"] == str(apartment["id"])
    assert row["requests"] == 1


def test_a_pdf_is_refused_before_any_model_call(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    fake = FakeClient([])
    ai.set_client_for_tests(fake)
    from tests.test_guest_navigation import MINIMAL_PDF

    res = _scan(client, token, stay, files={"passport_photo": ("form.pdf", MINIMAL_PDF, "application/pdf")})
    assert res.status_code == 400
    assert res.json()["kind"] == "error"
    assert not fake.calls


def test_a_model_failure_is_502_with_a_friendly_message(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    fake = FakeClient([reply({}, text="not json", thinking_first=False)])
    ai.set_client_for_tests(fake)
    res = _scan(client, token, stay)
    assert res.status_code == 502
    assert "hand" in res.json()["message"]


def test_an_empty_read_is_422(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    fake = FakeClient([reply({
        "surname": "", "first_name": "", "birth_date": "", "nationality": "XX", "doc_number": ""
    })])
    ai.set_client_for_tests(fake)
    res = _scan(client, token, stay)
    assert res.status_code == 422
    assert res.json()["kind"] == "error"


def test_the_budget_cap_ends_in_503_not_an_error_page(browser, monkeypatch):
    client, token, stay = browser
    _max_owner(monkeypatch)
    db.execute("DELETE FROM ai_usage", ())
    monkeypatch.setattr(config, "ai_monthly_usd", lambda feature: 0.0 if feature == "doc_ocr" else 10.0)
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

def test_prepare_image_shrinks_and_reencodes():
    big = _jpeg(3000, 2000)
    out = doc_ocr.prepare_image(big, "image/jpeg")
    with Image.open(io.BytesIO(out)) as image:
        assert image.format == "JPEG"
        assert max(image.size) <= doc_ocr.MAX_EDGE
    small = doc_ocr.prepare_image(PNG_BYTES, "image/png")
    assert small[:2] == b"\xff\xd8"  # JPEG magic


def test_prepare_image_refuses_a_pdf():
    from tests.test_guest_navigation import MINIMAL_PDF

    with pytest.raises(doc_ocr.BadDocument):
        doc_ocr.prepare_image(MINIMAL_PDF, "application/pdf")


def test_the_input_estimate_counts_an_image_block_not_its_bytes():
    tiny = "x" * 100
    small = ai.estimate_input_tokens(["p"], [{"role": "user", "content": tiny}])
    image = [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "A" * 2_000_000}},
        {"type": "text", "text": tiny},
    ]}]
    large = ai.estimate_input_tokens(["p"], image)
    # The base64 payload must not be counted as text, or every scan is refused.
    assert large < small + 2 * 3400
