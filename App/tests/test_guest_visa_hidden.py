"""UX-113 (A-26): a guest who cannot hold a Schengen visa is not asked for one.

A Czech, EU, EEA or Swiss guest enters on their own document, so the visa
question has exactly one possible answer and only added a decision to the
longest step of the form. The field is hidden and emptied in JavaScript rather
than removed from the template, so a number typed before the nationality was
picked cannot be saved behind the guest's back.

There is no JavaScript runtime in this suite, so the behaviour is pinned at the
source, the way the child-document rule is.
"""
from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import claim, db
from app.main import app
from tests.conftest import complete_guest_claim

TOKEN = "visahidden"
ASSETS = Path(__file__).resolve().parents[1] / "app" / "static"

# The 27 member states, plus the three EEA states, plus Switzerland. A national
# of any of these is in the Schengen area by right and is never issued a
# Schengen visa.
EU_EEA_CH = (
    "AUT BEL BGR CHE CYP CZE DEU DNK ESP EST FIN FRA GRC HRV HUN IRL ISL ITA "
    "LIE LTU LUX LVA MLT NLD NOR POL PRT ROU SVK SVN SWE"
).split()

# Guests who really do need a visa, so their field must stay.
NEEDS_A_VISA = ("UKR", "CHN", "IND", "TUR", "RUS", "SRB", "VNM")


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
        ("Visa Hidden",),
    )


def _seed():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Visa Hidden", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Visa flat",
            "uby_name": "Visa Facility",
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
            "uid": "visa-hidden-stay",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )


def _script() -> str:
    return (ASSETS / "signature.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    return _script().split(f"function {name}()", 1)[1].split("\n  }", 1)[0]


def _visa_free_countries() -> list:
    block = _script().split("var VISA_FREE_COUNTRIES = [", 1)[1].split("];", 1)[0]
    return json.loads("[" + block + "]")


def _guest_form(lang: str) -> str:
    reservation_id = _seed()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, TOKEN, reservation_id, lang=lang)
        response = browser.get(f"/l/{TOKEN}/{reservation_id}/new?lang={lang}")
        assert response.status_code == 200
        return response.text
    finally:
        _cleanup()


# --- who is exempt ----------------------------------------------------------


def test_every_nationality_that_can_never_hold_a_visa_is_on_the_list():
    assert sorted(_visa_free_countries()) == sorted(EU_EEA_CH)


def test_the_list_is_a_set_of_codes_with_no_duplicates():
    codes = _visa_free_countries()
    assert len(codes) == len(set(codes)) == 31
    assert all(re.fullmatch(r"[A-Z]{3}", code) for code in codes)


def test_a_guest_who_does_need_a_visa_keeps_the_field():
    free = set(_visa_free_countries())
    assert [code for code in NEEDS_A_VISA if code in free] == []


# --- how it is hidden -------------------------------------------------------


def test_the_field_is_hidden_and_emptied_when_the_nationality_is_exempt():
    body = _function("initVisaVisibility")
    assert 'getElementById("nationality")' in body
    assert 'getElementById("visa_number")' in body
    assert 'wrap.style.display = free ? "none" : ""' in body
    # Hidden *and* emptied: a number typed before the nationality was chosen
    # must not travel to the server behind an invisible field.
    assert "if (free) visa.value = \"\";" in body


def test_the_field_comes_back_when_the_nationality_changes_again():
    body = _function("initVisaVisibility")
    assert 'nationality.addEventListener("change", apply)' in body
    # And the state is worked out on load too, so a redisplayed form with an
    # exempt nationality preselected does not show the field again.
    assert body.rstrip().endswith("apply();")


def test_the_wrapper_is_the_field_and_not_a_neighbour():
    body = _function("initVisaVisibility")
    assert 'visa.closest(".g-field") || visa' in body


def test_the_rule_runs_with_the_other_form_helpers():
    script = _script()
    boot = script.split('document.addEventListener("DOMContentLoaded"', 1)[1]
    assert "initVisaVisibility();" in boot.split("});", 1)[0]


# --- and the markup it relies on --------------------------------------------


def test_the_visa_question_sits_alone_in_a_field_wrapper():
    form = _guest_form("en")
    head = form[: form.index('id="visa_number"')]
    wrapper = head.rsplit('<div class="g-field"', 1)[1]
    # The wrapper holds one field and no closing tag, so hiding it hides the
    # whole question and nothing else.
    assert wrapper.count("<input") == 1
    assert "</div>" not in wrapper
    assert 'for="visa_number"' in wrapper


def test_the_nationality_select_is_the_one_the_script_reads():
    form = _guest_form("cs")
    assert 'id="nationality"' in form
    assert 'name="nationality"' in form
    assert '<option value=""' in form, "an empty value must not read as exempt"
