"""The validation sentences the host reads, in the host's language.

``validation.py`` writes its messages in English because that is the language
the code reads in. The host is the one who sees them, in the banner above the
property form and on the guest cards, and used to get the English sentence on an
otherwise Czech page.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db, validation, validation_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "validation-i18n-host"


def _cleanup():
    for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,)):
        user_id = row["id"]
        db.execute(
            "DELETE FROM guest WHERE reservation_id IN "
            "(SELECT id FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?))",
            (user_id,),
        )
        db.execute(
            "DELETE FROM reservation WHERE apartment_id IN "
            "(SELECT id FROM apartment WHERE owner_user_id = ?)",
            (user_id,),
        )
        db.execute("DELETE FROM ical_feed WHERE apartment_id IN "
                   "(SELECT id FROM apartment WHERE owner_user_id = ?)", (user_id,))
        for table in ("alert", "audit", "apartment"):
            db.execute(f"DELETE FROM {table} WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _broken_apartment(**overrides):
    """A property with nothing UbyPort needs, so every message fires."""
    row = {
        "internal_name": "Untranslated Flat",
        "addr_city": "Praha",
        "uby_idub": "",
        "uby_mark": "",
        "uby_name": "",
        "uby_ws_user": "",
        "uby_ws_password": "",
        "addr_house_no": "",
        "addr_zip": "",
        "addr_obec": "",
        "legal_entity_id": None,
    }
    row.update(overrides)
    return row


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Validation Host", username=USERNAME)
    try:
        yield
    finally:
        _cleanup()


def _signed_in(lang: str) -> TestClient:
    client = TestClient(app)
    response = login_as(client, USERNAME, url=f"/login?lang={lang}", follow_redirects=False)
    assert response.status_code == 303, response.text
    return client


def _apartment(**overrides):
    owner_id = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )["id"]
    now = db.utcnow()
    data = {
        "internal_name": "Untranslated Flat",
        "automation_mode": "manual",
        "active": 1,
        "owner_user_id": owner_id,
        "created_at": now,
    }
    data.update(overrides)
    return db.insert("apartment", data)


def test_every_apartment_issue_has_czech():
    """A Czech host must not be handed an English reason the banner is red."""
    samples = [
        _broken_apartment(),
        _broken_apartment(uby_idub="short", uby_mark="abc", uby_name="X" * 40),
        _broken_apartment(
            uby_idub="123456789012",
            uby_mark="AAKLI",
            uby_name="Penzion",
            addr_house_no="12X4",
            addr_orient_no="12345",
            addr_zip="1234",
        ),
        _broken_apartment(
            uby_idub="123456789012",
            uby_mark="AAKLI",
            uby_name="Penzion",
            addr_house_no="12",
            addr_zip="12000",
            addr_obec="Praha",
            uby_ws_user="ub1234567",
        ),
        _broken_apartment(
            uby_idub="123456789012",
            uby_mark="AAKLI",
            uby_name="Penzion",
            addr_house_no="12",
            addr_zip="12000",
            addr_obec="Praha",
            uby_ws_user="UBY-WS123abc",
            legal_entity_id=1,
        ),
    ]
    checked = 0
    for sample in samples:
        for issue in validation.validate_apartment(sample):
            czech = validation_i18n.localize(issue.message)
            assert czech != issue.message, f"no Czech for {issue.field}: {issue.message!r}"
            checked += 1
    assert checked >= 12


def test_the_property_banner_names_the_missing_fields_in_czech(host):
    apartment_id = _apartment()
    page = _signed_in("cs").get(f"/apartments/{apartment_id}")

    assert page.status_code == 200
    assert "Bez IDUB nelze nic nahlásit." in page.text
    assert "Vyplňte PSČ." in page.text
    assert "IDUB is required before anything can be reported." not in page.text


def test_an_english_host_still_reads_english(host):
    apartment_id = _apartment()
    page = _signed_in("en").get(f"/apartments/{apartment_id}")

    assert page.status_code == 200
    assert "IDUB is required before anything can be reported." in page.text
    assert "Bez IDUB nelze nic nahlásit." not in page.text


def test_a_guest_card_on_a_stay_speaks_the_host_language(host):
    apartment_id = _apartment(
        uby_idub="123456789012",
        uby_mark="AAKLI",
        uby_name="Penzion",
        addr_house_no="12",
        addr_zip="12000",
        addr_obec="Praha",
        uby_ws_user="UBY-WS123abc",
        uby_ws_password_enc=db.encrypt_secret("secret"),
    )
    today = date.today()
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "uid": "validation-i18n-uid",
            "source": "manual",
            "date_from": (today + timedelta(days=1)).isoformat(),
            "date_to": (today + timedelta(days=4)).isoformat(),
            "status": "active",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )
    db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "surname": "",
            "first_name": "",
            "submit_state": "pending",
            "created_at": db.utcnow(),
            "updated_at": db.utcnow(),
        },
    )

    page = _signed_in("cs").get(f"/reservations/{reservation_id}")

    assert page.status_code == 200
    assert "Příjmení je povinné." in page.text
    assert "Surname is required." not in page.text


def test_a_czech_message_that_has_no_entry_is_shown_as_it_is():
    """An unknown sentence stays visible rather than turning blank."""
    assert validation_i18n.localize("Something nobody has written yet.") == (
        "Something nobody has written yet."
    )


def test_the_patterns_cover_the_sentences_that_embed_a_value():
    assert validation_i18n.localize("'XYZ' is not a valid three-letter country code.") == (
        "„XYZ“ není platný třímístný kód země (např. GBR, USA, DEU)."
    )
    assert validation_i18n.localize("Must be at most 48 characters.") == "Nejvýše 48 znaků."
