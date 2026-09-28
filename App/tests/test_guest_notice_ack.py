"""BE-5/FE-2: a guest's notice acknowledgement is persisted, and its version shown.

The tick was validated but never stored, so the house book could not say which
privacy notice a guest had seen. The guest save now records the version, the
language and the time; the notice and the guest privacy page show the version.
"""
from __future__ import annotations

import base64
import io
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import claim, config, db, housebook, i18n
from app.main import app
from tests.conftest import complete_guest_claim

APP = Path(__file__).resolve().parents[1] / "app"
TOKEN = "noticeacktok"
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
PAYLOAD = {
    "first_name": "John",
    "surname": "Smith",
    "birth_date": "1.1.1990",
    "nationality": "GBR",
    "doc_number": "P1234567",
    "res_street": "Baker Street 221B",
    "res_city": "London",
    "res_country": "GBR",
    "purpose": "10",
    "signature": SIGNATURE,
    "legal_ack": "1",
}


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        return
    db.execute(
        "DELETE FROM guest WHERE reservation_id IN "
        "(SELECT id FROM reservation WHERE apartment_id = ?)",
        (apartment["id"],),
    )
    db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apartment["id"],))
    db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute(
        "DELETE FROM legal_entity WHERE name = ? AND id NOT IN "
        "(SELECT legal_entity_id FROM apartment WHERE legal_entity_id IS NOT NULL)",
        ("Notice Ack",),
    )


@pytest.fixture(autouse=True)
def _database():
    db.init_db()
    _cleanup()
    yield
    _cleanup()


def _seed() -> int:
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Notice Ack", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Notice flat",
            "uby_name": "Notice Facility",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "passport_photo_policy": "off",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    return db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "notice-ack-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "declared_guests": 1,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _browser(lang="en"):
    reservation_id = _seed()
    browser = TestClient(app)
    browser.cookies.set("ubyhost_guest_lang", lang)
    complete_guest_claim(browser, TOKEN, reservation_id, party_size=1, lang=lang)
    return browser, reservation_id


def test_a_guest_save_persists_the_notice_version_language_and_time():
    browser, reservation_id = _browser("en")
    response = browser.post(
        f"/l/{TOKEN}/{reservation_id}/save?lang=en", data=dict(PAYLOAD)
    )
    assert response.status_code in (200, 303), response.text
    guest = db.query_one(
        "SELECT * FROM guest WHERE reservation_id = ?", (reservation_id,)
    )
    assert guest is not None
    assert guest["notice_version"] == config.GUEST_NOTICE_VERSION
    assert guest["notice_lang"] == "en"
    assert guest["notice_ack_at"]


def test_a_missing_checkbox_persists_nothing():
    browser, reservation_id = _browser("en")
    payload = dict(PAYLOAD)
    payload.pop("legal_ack")
    response = browser.post(
        f"/l/{TOKEN}/{reservation_id}/save?lang=en", data=payload
    )
    assert response.status_code == 422, response.text
    assert db.query(
        "SELECT id FROM guest WHERE reservation_id = ?", (reservation_id,)
    ) == []


def test_the_host_save_path_does_not_record_an_acknowledgement():
    """The host is responsible for informing a guest they enter by hand."""
    source = (APP / "routes" / "admin.py").read_text(encoding="utf-8")
    assert "notice_version" not in source
    assert "notice_ack_at" not in source


def test_the_registration_pdf_names_the_acknowledged_notice_version():
    from pypdf import PdfReader

    browser, reservation_id = _browser("en")
    browser.post(f"/l/{TOKEN}/{reservation_id}/save?lang=en", data=dict(PAYLOAD))
    guest_id = db.query_one(
        "SELECT id FROM guest WHERE reservation_id = ?", (reservation_id,)
    )["id"]

    pdf = housebook.registration_form_pdf(guest_id)
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert f"Privacy notice v{config.GUEST_NOTICE_VERSION}" in text


@pytest.mark.parametrize("lang", ("en", "cs"))
def test_the_notice_version_is_shown_on_the_form_and_the_privacy_page(lang):
    browser, reservation_id = _browser(lang)
    expected = i18n.translator(lang)(
        "notice_version", version=config.GUEST_NOTICE_VERSION
    )

    form = browser.get(f"/l/{TOKEN}/{reservation_id}/new?lang={lang}")
    assert form.status_code == 200, form.text
    assert expected in form.text

    privacy = browser.get(f"/l/{TOKEN}/privacy?lang={lang}")
    assert privacy.status_code == 200, privacy.text
    assert expected in privacy.text
