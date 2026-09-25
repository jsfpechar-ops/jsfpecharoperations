"""UX-54 (A-18): the purpose and the home country read as a person says them.

A guest used to be shown the police shapes: "10 - TURISTIKA" for the purpose
and "GBR-United Kingdom" for their own country, on a page written for them.
Both are now plain. The stored values are untouched — the numeric purpose code
and the "GBR-United Kingdom" residence UbyPort's appendix 3 wants are still
what goes out.
"""
from __future__ import annotations

import base64
import re
from datetime import timedelta

from fastapi.testclient import TestClient

from app import claim, codelists, db, validation
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim

TOKEN = "purposedisplaytok"
SIGNATURE = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6300010000050001od7a1f0000000049454e44ae42"
        "6082".replace("od", "0d")
    )
).decode()

# The audit's sentence-case list, in code order (A-18).
CS_LABELS = {
    "00": "Zdravotní",
    "01": "Obchodní",
    "02": "Kulturní",
    "03": "Návštěva rodiny nebo přátel",
    "04": "Pozvání",
    "05": "Oficiální (politický)",
    "06": "Podnikání (OSVČ)",
    "07": "Sportovní",
    "10": "Turistika",
    "11": "Studium (školení, stáž)",
    "12": "Tranzit (průjezd)",
    "13": "Letištní tranzit",
    "27": "Zaměstnání",
    "93": "Vízum ADS (občané Číny)",
    "99": "Ostatní",
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
        ("Purpose Display",),
    )


def _seed():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Purpose Display", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Purpose flat",
            "uby_name": "Purpose Facility",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
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
            "uid": "purpose-stay",
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


def _option_label(page: str, code: str) -> str:
    match = re.search(r'<option value="%s"[^>]*>\s*(.*?)\s*</option>' % code, page, re.S)
    assert match, f"no option for purpose {code}"
    return re.sub(r"\s+", " ", match.group(1))


def test_the_purpose_label_has_no_police_code():
    assert validation.purpose_label("10", "en") == "Tourism"
    assert validation.purpose_label("10", "cs") == "Turistika"
    assert " - " not in validation.purpose_label("10", "en")
    assert " - " not in validation.purpose_label("10", "cs")


def test_every_purpose_code_maps_to_a_label_in_both_languages():
    for code, cs, en in validation.PURPOSES:
        assert validation.purpose_label(code, "cs") == cs
        assert validation.purpose_label(code, "en") == en
        # An unknown code is shown as itself rather than swallowed.
        assert validation.purpose_label(code, "en") != code


def test_the_czech_purpose_labels_are_sentence_case():
    """The audit's exact list, so the police wording cannot creep back."""
    assert {code: validation.purpose_label(code, "cs") for code, _cs, _en in validation.PURPOSES} == CS_LABELS
    for label in CS_LABELS.values():
        assert label != label.upper(), f"{label!r} is still shouting"


def test_the_czech_labels_ignore_the_fetched_police_text():
    """The bundled sentence-case list wins over the fetched text_cs."""
    for code, label in CS_LABELS.items():
        assert validation.purpose_label(code, "cs") == label


def test_the_form_offers_plain_purpose_labels_in_both_languages():
    reservation_id = _seed()
    try:
        for lang, expected in (("en", "Tourism"), ("cs", "Turistika")):
            browser = TestClient(app)
            browser.cookies.set(guest.LANG_COOKIE, lang)
            complete_guest_claim(browser, TOKEN, reservation_id, party_size=2, lang=lang)
            page = browser.get(f"/l/{TOKEN}/{reservation_id}/new?lang={lang}").text
            label = _option_label(page, "10")
            assert label == expected
            assert "10 -" not in label
            # The code is still what the select submits.
            assert '<option value="10"' in page
    finally:
        _cleanup()


def test_the_purpose_options_keep_the_code_and_drop_the_prefix():
    for lang, expected in (("en", "Tourism"), ("cs", "Turistika")):
        options = codelists.purpose_options(lang)
        by_code = {option["code"]: option["label"] for option in options}
        assert by_code["10"] == expected
        assert all(" - " not in label for label in by_code.values())


def test_the_summary_country_has_no_iso_code():
    assert (
        validation.display_residence("Baker Street 221B", "London", "GBR", "en")
        == "Baker Street 221B, London, United Kingdom"
    )
    assert (
        validation.display_residence("Baker Street 221B", "London", "GBR", "cs")
        == "Baker Street 221B, London, Spojené království"
    )


def test_ubyport_still_gets_the_coded_residence():
    """Appendix 3 wants the code; only the guest-facing copy drops it."""
    assert (
        validation.compose_residence("Baker Street 221B", "London", "GBR", "en")
        == "Baker Street 221B, London, GBR-United Kingdom"
    )


def test_the_stay_summary_shows_a_plain_purpose_and_country():
    reservation_id = _seed()
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, TOKEN, reservation_id, party_size=2, lang="en")
        saved = browser.post(
            f"/l/{TOKEN}/{reservation_id}/save",
            data=_payload(),
            follow_redirects=False,
        )
        assert saved.status_code == 303, saved.text
        hub = browser.get(f"/l/{TOKEN}/{reservation_id}?lang=en")
        assert hub.status_code == 200
        summary = re.search(r'<dl class="g-summary-list">(.*?)</dl>', hub.text, re.S)
        assert summary, "the stay hub has no summary list"
        body = summary.group(1)
        assert "<dd>Tourism</dd>" in body
        assert "United Kingdom" in body
        assert "10 -" not in body
        assert "GBR-" not in body
    finally:
        _cleanup()
