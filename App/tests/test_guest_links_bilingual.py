"""The suggested portal message is pasted into Airbnb, where most readers are foreign.

A Czech host used to copy a Czech-only message ("Vážení hosté, český zákon
vyžaduje…") into a portal whose guests are the foreign nationals who must
register. The message is now English first, Czech second, whatever the host's UI
language, and the ⋯ menu offers the English half on its own.
"""
from __future__ import annotations

import html

import pytest
from fastapi.testclient import TestClient

from app import auth, db, guest_slug, host_i18n
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


def _message_block(text: str, element_id: str) -> str:
    """The text inside the <pre> with this id."""
    marker = f'id="{element_id}"'
    assert marker in text, f"no element with {marker}"
    body = text.split(marker, 1)[1].split(">", 1)[1]
    return html.unescape(body.split("</pre>", 1)[0])


def test_a_czech_host_still_gets_the_english_half(host):
    """The whole point: the Czech host's message must be readable by a foreign guest."""
    apartment_id = _apartment_id()

    page = host.get("/guest-links?lang=cs")

    assert page.status_code == 200
    message = _message_block(page.text, f"message-{apartment_id}")
    assert EN_OPENING in message, "the message a Czech host copies has no English half"
    assert CS_OPENING in message
    assert message.index(EN_OPENING) < message.index(CS_OPENING), "Czech came first"


def test_an_english_host_gets_the_same_bilingual_message(host):
    apartment_id = _apartment_id()

    page = host.get("/guest-links?lang=en")

    message = _message_block(page.text, f"message-{apartment_id}")
    assert EN_OPENING in message and CS_OPENING in message
    assert message.index(EN_OPENING) < message.index(CS_OPENING)


def test_the_message_carries_the_link_and_the_pin(host):
    """Both halves have to be usable on their own, so both carry link and PIN."""
    apartment_id = _apartment_id()

    page = host.get("/guest-links?lang=cs")

    message = _message_block(page.text, f"message-{apartment_id}")
    english, czech = message.split(CS_OPENING, 1)
    slug = guest_slug.current(apartment_id)
    assert slug and f"/l/{slug}" in english
    assert PIN in english
    assert f"/l/{slug}" in czech
    assert PIN in czech


def test_the_pin_and_link_actions_sit_with_the_fields(host):
    """Copy, a chosen PIN and a new PIN belong next to the PIN, not in a menu."""
    apartment_id = _apartment_id()

    page = host.get("/guest-links?lang=en")

    assert "Copy English only" not in page.text
    text = page.text
    pin_at = text.index(f'id="pin-{apartment_id}"')
    link_at = text.index(f'id="link-{apartment_id}"')
    assert link_at < text.index("Generate a new link") < pin_at
    assert pin_at < text.index("Set a specific PIN") < text.index("Generate a new PIN")
    assert f'href="/apartments/{apartment_id}#communication"' in text
    assert f'action="/apartments/{apartment_id}/regenerate-pin"' in text
    assert f'action="/apartments/{apartment_id}/regenerate-link"' in text


def test_the_lede_says_the_form_opens_in_the_guest_language(host):
    _apartment_id()

    page = host.get("/guest-links?lang=en")

    assert "Guests from abroad read the English part" in page.text


def test_the_lede_is_in_czech_too(host):
    _apartment_id()

    page = host.get("/guest-links?lang=cs")

    assert "Zahraniční hosté si přečtou anglickou část" in page.text


def test_the_property_page_shows_the_same_bilingual_message(host):
    apartment_id = _apartment_id()

    page = host.get(f"/apartments/{apartment_id}?lang=en")

    assert page.status_code == 200
    body = html.unescape(page.text)
    assert EN_OPENING in body and CS_OPENING in body
    assert body.index(EN_OPENING) < body.index(CS_OPENING)


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
