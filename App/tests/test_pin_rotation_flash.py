"""The new guest PIN must never travel in the redirect URL.

``back()`` carries the flash in the query string, so putting the PIN in the
message wrote the secret into browser history, bookmarks and the access log of
every proxy in front of the app. The guest link card already shows the PIN, so
the flash only has to point at it.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import auth, db, host_i18n
from app.main import app
from tests.conftest import login_as

USERNAME = "pin-rotation-host"
TOKEN = "pinrotationtoken"
PIN = "314159"

_ENTITY_ID: int | None = None


def _cleanup():
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,)
    )
    if apartment:
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    global _ENTITY_ID
    if _ENTITY_ID is not None:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (_ENTITY_ID,))
        _ENTITY_ID = None
    # The account itself stays: other tables hold a foreign key to it, and the
    # empty-install canary only counts properties, stays and guests.


def _host() -> tuple[TestClient, int]:
    db.init_db()
    _cleanup()
    now = db.utcnow()
    existing = db.query_one(
        "SELECT id FROM user_account WHERE username = ?", (USERNAME,)
    )
    user_id = (
        existing["id"]
        if existing
        else auth.create_account(f"{USERNAME}@example.test", "PIN Host", username=USERNAME)
    )
    entity_id = db.insert(
        "legal_entity",
        {"name": "PIN s.r.o.", "owner_user_id": user_id, "created_at": now},
    )
    global _ENTITY_ID
    _ENTITY_ID = entity_id
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": user_id,
            "internal_name": "PIN 1",
            "permalink_token": TOKEN,
            "permalink_pin": PIN,
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
        },
    )
    client = TestClient(app)
    login_as(client, USERNAME, follow_redirects=False)
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    return client, apartment_id


@pytest.fixture
def host():
    client, apartment_id = _host()
    try:
        yield client, apartment_id
    finally:
        _cleanup()


def _flash_of(location: str) -> str:
    query = parse_qs(urlsplit(location).query)
    return query["msg"][0]


def _rotate(client: TestClient, apartment_id: int) -> tuple[str, str]:
    """POST the regenerate button and return (new pin, redirect location)."""
    response = client.post(
        f"/apartments/{apartment_id}/regenerate-pin",
        data={"return_to": "/guest-links"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.status_code
    pin = db.query_one(
        "SELECT permalink_pin FROM apartment WHERE id = ?", (apartment_id,)
    )["permalink_pin"]
    return pin, response.headers["location"]


def test_regenerating_still_replaces_the_pin(host):
    client, apartment_id = host
    pin, _location = _rotate(client, apartment_id)
    assert pin != PIN, "the button must still rotate the PIN"
    assert re.fullmatch(r"[0-9]{6}", pin)


def test_the_new_pin_is_not_in_the_redirect_url(host):
    client, apartment_id = host
    pin, location = _rotate(client, apartment_id)
    assert pin not in location, f"the PIN {pin} leaks into the URL"
    assert pin not in unquote(location)


def test_the_redirect_lands_on_the_guest_link_page(host):
    client, apartment_id = host
    _pin, location = _rotate(client, apartment_id)
    assert location.startswith("/guest-links?")


def test_the_flash_points_at_the_card_instead_of_the_pin(host):
    client, apartment_id = host
    _pin, location = _rotate(client, apartment_id)
    assert _flash_of(location) == host_i18n.STRINGS["en"][
        "flash.apartments.pin_rotated"
    ]


def test_the_pin_free_flash_is_pinned_in_both_languages():
    assert host_i18n.STRINGS["en"]["flash.apartments.pin_rotated"] == (
        "New PIN generated. Copy it from the guest link card and update your "
        "portal messages."
    )
    assert host_i18n.STRINGS["cs"]["flash.apartments.pin_rotated"] == (
        "Nový PIN je vygenerovaný. Zkopírujte ho z karty odkazu a upravte "
        "zprávy na portálech."
    )
    for lang in ("en", "cs"):
        assert "%(pin)s" not in host_i18n.STRINGS[lang][
            "flash.apartments.pin_rotated"
        ]


def test_a_czech_host_reads_the_pin_free_flash_in_czech():
    client, apartment_id = _host()
    try:
        client.cookies.set(host_i18n.LANG_COOKIE, "cs")
        response = client.post(
            f"/apartments/{apartment_id}/regenerate-pin",
            data={"return_to": "/guest-links"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert _flash_of(response.headers["location"]) == (
            "Nový PIN je vygenerovaný. Zkopírujte ho z karty odkazu a upravte "
            "zprávy na portálech."
        )
    finally:
        _cleanup()
