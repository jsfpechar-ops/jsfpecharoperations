"""UX-58 (A-22): the second person does not retype the family address.

Person 2 in a family types the same street, city and country as person 1, and
that is the longest run of typing left in the form. The device cookie already
names the guests this browser filled in, so the address was known - the /new
form simply started empty and said nothing about it.
"""
from __future__ import annotations

import base64
import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import claim, db, i18n
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim

TOKEN = "resprefilltok"
EN_HELP = "Your permanent home address, as in your passport or ID card."
CS_HELP = "Adresa trvalého bydliště podle pasu nebo občanského průkazu."
EN_COPIED = "Copied from %(name)s. Change it if this person lives elsewhere."
CS_COPIED = "Převzato od: %(name)s. Pokud tato osoba bydlí jinde, adresu změňte."
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
PAYLOAD = {
    "first_name": "John Paul",
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
        ("Residence Prefill",),
    )


def _seed(declared=2):
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Residence Prefill", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Prefill flat",
            "uby_name": "Prefill Facility",
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
            "uid": "residence-prefill-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "declared_guests": declared,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _request_without_cookies() -> Request:
    return Request(
        {"type": "http", "method": "GET", "path": "/", "query_string": b"", "headers": []}
    )


def _request_owning(guest_ids) -> Request:
    cookie = guest._serializer().dumps([int(g) for g in guest_ids])
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [(b"cookie", f"{guest.OWNED_COOKIE}={cookie}".encode())],
        }
    )


def _first_person_done(lang: str):
    """Register person 1 through the real form and hand back (browser, ids)."""
    reservation_id = _seed()
    browser = TestClient(app)
    browser.cookies.set(guest.LANG_COOKIE, lang)
    complete_guest_claim(browser, TOKEN, reservation_id, party_size=2, lang=lang)
    response = browser.post(
        f"/l/{TOKEN}/{reservation_id}/save?lang={lang}", data=dict(PAYLOAD)
    )
    assert response.status_code in (200, 303), response.text
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    rows = db.query("SELECT * FROM guest WHERE reservation_id = ?", (reservation_id,))
    return browser, reservation, rows


# --- the copy -------------------------------------------------------------


def test_the_help_no_longer_says_abroad_or_passport_only():
    assert i18n.translator("en")("residence_help") == EN_HELP
    assert i18n.translator("cs")("residence_help") == CS_HELP
    assert "abroad" not in EN_HELP
    assert "zahraničí" not in CS_HELP


def test_the_copied_hint_exists_in_both_languages():
    assert i18n.translator("en")("residence_copied", name="X") == EN_COPIED.replace(
        "%(name)s", "X"
    )
    assert i18n.translator("cs")("residence_copied", name="X") == CS_COPIED.replace(
        "%(name)s", "X"
    )


# --- the prefill itself ---------------------------------------------------


def test_a_device_that_owns_nobody_is_not_prefilled():
    try:
        reservation_id = _seed()
        reservation = db.query_one(
            "SELECT * FROM reservation WHERE id = ?", (reservation_id,)
        )
        assert guest._residence_prefill(_request_without_cookies(), reservation) == ({}, None)
    finally:
        _cleanup()


def test_the_address_comes_from_the_most_recent_completed_guest():
    try:
        browser, reservation, rows = _first_person_done("en")
        assert len(rows) == 1
        values, name = guest._residence_prefill(
            _request_owning([rows[0]["id"]]), reservation
        )
        assert values == {
            "res_street": "Baker Street 221B",
            "res_city": "London",
            "res_country": "GBR",
        }
        assert name == "John Paul Smith"
    finally:
        _cleanup()


def test_a_half_finished_guest_is_never_copied_from():
    """A record someone abandoned is not something to repeat for someone else."""
    try:
        browser, reservation, rows = _first_person_done("en")
        now = db.utcnow()
        half = db.insert(
            "guest",
            {
                "reservation_id": reservation["id"],
                "first_name": "Half",
                "surname": "Typed",
                "res_street": "Somewhere else 1",
                "res_city": "Prague",
                "res_country": "CZE",
                "created_at": now,
                "updated_at": now,
            },
        )
        values, name = guest._residence_prefill(
            _request_owning([rows[0]["id"], half]), reservation
        )
        assert values["res_street"] == "Baker Street 221B"
        assert name == "John Paul Smith"
    finally:
        _cleanup()


def test_an_owned_guest_from_another_stay_is_not_used():
    try:
        browser, reservation, rows = _first_person_done("en")
        other = _seed()
        assert other != reservation["id"]
        assert guest._residence_prefill(
            _request_owning([rows[0]["id"]]),
            db.query_one("SELECT * FROM reservation WHERE id = ?", (other,)),
        ) == ({}, None)
    finally:
        _cleanup()


# --- and the form the guest actually sees ---------------------------------


@pytest.mark.parametrize(
    "lang,expected_street,expected_city,expected_hint",
    [
        ("en", "Baker Street 221B", "London", "Copied from John Paul Smith"),
        ("cs", "Baker Street 221B", "London", "Převzato od: John Paul Smith"),
    ],
)
def test_the_next_person_sees_the_address_already_filled_in(
    lang, expected_street, expected_city, expected_hint
):
    try:
        browser, reservation, rows = _first_person_done(lang)
        page = browser.get(f"/l/{TOKEN}/{reservation['id']}/new?lang={lang}").text
        assert re.search(
            r'id="res_street"[^>]*value="' + re.escape(expected_street) + '"', page
        ), "the street was not prefilled"
        assert re.search(
            r'id="res_city"[^>]*value="' + re.escape(expected_city) + '"', page
        ), "the city was not prefilled"
        assert re.search(
            r'<option value="GBR"\s+selected', page
        ), "the country was not prefilled"
        assert expected_hint in page
    finally:
        _cleanup()


def test_the_first_person_sees_no_hint():
    try:
        reservation_id = _seed()
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, TOKEN, reservation_id, party_size=2, lang="en")
        page = browser.get(f"/l/{TOKEN}/{reservation_id}/new?lang=en").text
        assert "Copied from" not in page
        assert re.search(r'id="res_street"[^>]*value=""', page)
    finally:
        _cleanup()


def test_the_hint_is_announced_as_a_status_not_an_alert():
    """It is information, not a problem: nothing here is wrong."""
    try:
        browser, reservation, rows = _first_person_done("en")
        page = browser.get(f"/l/{TOKEN}/{reservation['id']}/new?lang=en").text
        match = re.search(r'<p class="hint"[^>]*>Copied from', page)
        assert match, "the copied hint is not on the page"
        assert 'role="status"' in match.group(0)
        assert "alert" not in match.group(0)
    finally:
        _cleanup()


def test_the_address_fields_use_the_autocomplete_tokens_that_fit_them():
    try:
        browser, reservation, rows = _first_person_done("en")
        page = browser.get(f"/l/{TOKEN}/{reservation['id']}/new?lang=en").text
        street = re.search(r"<input[^>]*id=\"res_street\"[^>]*>", page).group(0)
        assert 'autocomplete="address-line1"' in street
        assert "street-address" not in street
        country = re.search(r"<select[^>]*id=\"res_country\"[^>]*>", page).group(0)
        assert 'autocomplete="country"' in country
    finally:
        _cleanup()
