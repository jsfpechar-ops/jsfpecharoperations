"""The suggested portal message is pasted into Airbnb, where most readers are foreign.

A Czech host used to copy a Czech-only message ("Vážení hosté, český zákon
vyžaduje…") into a portal whose guests are the foreign nationals who must
register. The message is now English first, Czech second, whatever the host's UI
language, and the ⋯ menu offers the English half on its own.
"""
from __future__ import annotations


import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "guest-links-bilingual-host"
TOKEN = "guestlinksbilingual1"
PIN = "4821"

EN_OPENING = "Dear guests,"
CS_OPENING = "Vážení hosté,"


def _cleanup():
    ids = [
        row["id"]
        for row in db.query("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    ]
    for user_id in ids:
        db.execute("DELETE FROM alert WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM reservation WHERE apartment_id IN (SELECT id FROM apartment WHERE owner_user_id = ?)", (user_id,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (user_id,))
        db.execute("DELETE FROM user_account WHERE id = ?", (user_id,))


def _apartment_id() -> int:
    owner_id = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))["id"]
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Bilingual s.r.o.",
            "seat": "Praha",
            "ico": "12345678",
            "contact_email": "host@bilingual.test",
            "owner_user_id": owner_id,
            "created_at": db.utcnow(),
        },
    )
    return db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": owner_id,
            "internal_name": "Bilingual Flat",
            "permalink_token": TOKEN,
            "permalink_pin": PIN,
            "automation_mode": "manual",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": db.utcnow(),
            "uby_idub": "100227887600",
            "uby_mark": "CZGFW",
            "uby_name": "Bilingual Flat",
            "uby_contact": "host@bilingual.test",
            "addr_okres": "Praha 2",
            "addr_obec": "Praha",
            "addr_obec_cast": "Vinohrady",
            "addr_street": "Korunní",
            "addr_house_no": "1234",
            "addr_orient_no": "12a",
            "addr_zip": "12000",
            "uby_ws_user": "UBY-WS12cdef",
            "uby_ws_password_enc": db.encrypt_secret("demo-password"),
        },
    )


@pytest.fixture
def host():
    db.init_db()
    _cleanup()
    auth.create_account(f"{USERNAME}@example.test", "Bilingual Host", username=USERNAME)
    client = TestClient(app)
    response = login_as(client, USERNAME, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303, response.text
    try:
        yield client
    finally:
        _cleanup()


def test_the_property_page_drops_the_suggested_portal_message(host):
    """0094 (owner correction): no Suggested portal message on the property
    page; the guest link, PIN with Copy and Preview stay at the top of Guest links."""
    apartment_id = _apartment_id()
    for lang in ("en", "cs"):
        page = host.get(f"/apartments/{apartment_id}?lang={lang}").text
        assert host_i18n.STRINGS[lang]["guest_links.message_title"] not in page
        assert host_i18n.STRINGS[lang]["guest_links.copy_message_en"] not in page
        assert 'class="message-template"' not in page
        assert 'id="permalink"' in page and 'id="permalink_pin"' in page
        assert host_i18n.STRINGS[lang]["guest_links.preview"] in page


def test_the_helper_puts_english_first():
    text = host_i18n.bilingual_message("guest_links.message", link="https://x/l/t", pin="1")

    assert text.index(EN_OPENING) < text.index(CS_OPENING)
    assert "\n\n" in text


def test_the_helper_can_be_asked_for_one_language():
    text = host_i18n.bilingual_message(
        "guest_links.message", languages=["en"], link="https://x/l/t", pin="1"
    )

    assert EN_OPENING in text
    assert CS_OPENING not in text


def test_the_helper_survives_a_missing_placeholder():
    """A half-written translation must not raise inside a template."""
    text = host_i18n.bilingual_message("guest_links.message", languages=["en"])

    assert "%(link)s" in text
