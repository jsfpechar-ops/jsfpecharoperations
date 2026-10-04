"""UX-55 (A-19): the guest's own errors, named the way the guest's form names them.

``validation.py`` writes for the host app, where a field is a column: "Country",
"Nationality". The guest form labels those fields "Country" / "Stát" and
"Nationality" / "Státní občanství", and the birth date has a label of its own, so
"Month must be between 01 and 12." read as a sentence about nothing the guest
could see. Each summary line now names the field by its label and links to it,
so tapping it opens the step the field is on.
"""
from __future__ import annotations

import base64
import re
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import claim, db, i18n, validation_i18n
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim

TOKEN = "errsummarytok"
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()
ASSETS = Path(__file__).resolve().parents[1] / "app" / "static"


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
        ("Error Summary",),
    )


def _seed():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Error Summary", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Error flat",
            "uby_name": "Error Facility",
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
            "uid": "error-summary-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _payload(**overrides):
    data = {
        "surname": "Smith",
        "first_name": "John Paul",
        "birth_date": "1.1.1990",
        "nationality": "GBR",
        "doc_number": "P1234567",
        "res_street": "Baker Street 221B",
        "res_city": "London",
        "res_country": "GBR",
        "purpose": "10",
        "party_size": "2",
        "signature": SIGNATURE,
        "legal_ack": "1",
    }
    data.update(overrides)
    return data


def _page(lang: str, **overrides) -> str:
    """The rendered form after a guest submits a broken one."""
    reservation_id = _seed()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, lang)
        complete_guest_claim(browser, TOKEN, reservation_id, party_size=2, lang=lang)
        response = browser.post(
            f"/l/{TOKEN}/{reservation_id}/save?lang={lang}", data=_payload(**overrides)
        )
        assert response.status_code == 422
        return response.text
    finally:
        _cleanup()


def _summary(page: str) -> str:
    match = re.search(r'<div class="g-err">.*?</div>', page, re.S)
    assert match, "the error summary did not render"
    return match.group(0)


def _items(page: str) -> dict:
    """The summary's links, as {field: sentence}."""
    return dict(re.findall(r'<li><a href="#([^"]+)">(.*?)</a></li>', _summary(page), re.S))


# --- the wording names the field the way its label names it -----------------


def test_the_nationality_error_names_the_nationality_label():
    assert validation_i18n.guest_localize("Nationality is required.", "en") == (
        "Choose your nationality."
    )
    assert validation_i18n.guest_localize("Nationality is required.", "cs") == (
        "Vyberte státní občanství."
    )
    # The labels the guest actually sees, in both languages.
    assert i18n.translator("en")("nationality") == "Nationality"
    assert i18n.translator("cs")("nationality") == "Státní občanství"


def test_the_country_error_names_the_home_address_label():
    assert validation_i18n.guest_localize("Country is required.", "en") == (
        "Choose the country of your home address."
    )
    assert validation_i18n.guest_localize("Country is required.", "cs") == (
        "Vyberte stát trvalého bydliště."
    )
    assert i18n.translator("cs")("res_country") == "Stát"


def test_every_birth_date_sentence_says_it_is_about_the_birth_date():
    """The field is "Date of birth" / "Datum narození", so the sentence says so."""
    for message in (
        "Enter the full date as DD.MM.YYYY.",
        "Year must be 1900 or later.",
        "Month must be between 01 and 12.",
        "Day must be between 01 and 31.",
        "That date does not exist - please check day and month.",
    ):
        assert validation_i18n.guest_localize(message, "en").startswith("Date of birth: ")
        assert validation_i18n.guest_localize(message, "cs").startswith("Datum narození: ")


def test_the_guest_overrides_do_not_reach_the_host():
    """The host app still reads ``validation.py``'s own wording."""
    assert validation_i18n.localize("Nationality is required.", "cs") == (
        "Státní příslušnost je povinná."
    )
    assert validation_i18n.localize("Country is required.", "cs") == "Země je povinná."
    assert validation_i18n.localize("Month must be between 01 and 12.") == (
        "Měsíc musí být mezi 01 a 12."
    )


def test_a_message_with_no_guest_entry_still_gets_its_host_translation():
    assert validation_i18n.guest_localize("Surname is required.", "cs") == (
        "Příjmení je povinné."
    )


def test_the_expired_form_says_nothing_was_saved():
    assert i18n.translator("en")("form_expired_help") == (
        "Nothing was saved. Start again from the link below."
    )
    assert i18n.translator("cs")("form_expired_help") == (
        "Nic se neuložilo. Začněte znovu přes odkaz níže."
    )


# --- the summary items are links to the field -------------------------------


def test_the_summary_items_link_to_the_field_they_name():
    items = _items(_page("en", nationality="", res_country=""))
    assert items["nationality"] == "Choose your nationality."
    assert items["res_country"] == "Choose the country of your home address."


def test_the_czech_summary_links_the_same_way():
    items = _items(_page("cs", nationality="", res_country=""))
    assert items["nationality"] == "Vyberte státní občanství."
    assert items["res_country"] == "Vyberte stát trvalého bydliště."


def test_a_bad_birth_date_reads_as_a_sentence_about_the_birth_date():
    items = _items(_page("en", birth_date="31/02/1990"))
    assert items["birth_date"] == (
        "Date of birth: that date does not exist. Check the day and month."
    )
    items = _items(_page("cs", birth_date="31/02/1990"))
    assert items["birth_date"] == (
        "Datum narození: takové datum neexistuje. Zkontrolujte den a měsíc."
    )


def test_every_summary_link_points_at_a_field_that_is_on_the_page():
    """A link into the wizard is only useful if the id it names exists."""
    page = _page("en", nationality="", res_country="", birth_date="31/02/1990")
    fields = set(_items(page))
    assert {"nationality", "res_country", "birth_date"} <= fields
    for field in fields:
        assert f'id="{field}"' in page, f"the summary links to #{field}, which is not a field"


def test_the_wizard_script_drives_the_summary_links():
    """A "#field" jump cannot reach a hidden step, so the script takes over."""
    script = (ASSETS / "signature.js").read_text(encoding="utf-8")
    assert "function initErrorSummary()" in script
    assert """querySelectorAll(".g-err a[href^='#']")""" in script
    assert "guest-wizard:show" in script
    assert "initErrorSummary();" in script


def test_the_summary_links_stay_readable_inside_the_error_box():
    css = (ASSETS / "guest.css").read_text(encoding="utf-8")
    assert re.search(r"\.g-err a\s*\{[^}]*color:\s*inherit", css)
