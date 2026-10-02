"""The country field on the guest form.

Two things are pinned here. The list is sorted with the diacritics folded away,
because ``sorted`` compares code points and would file "Česko" after "Zimbabwe"
-- a guest looking under "C" has to find their own country. And the eight
nationalities a Czech host actually files are lifted into their own group at the
top, so the guest does not scroll a 254-row wheel for the common case. The field
still starts empty: the guest's phone language says nothing about their
nationality.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import claim, codelists, db, i18n
from app.main import app
from tests.conftest import complete_guest_claim

TOKEN = "countrypick"


def _cleanup():
    apartment = db.query_one("SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,))
    if not apartment:
        db.execute(
            "DELETE FROM rate_limit_event WHERE scope LIKE 'claim_%' OR scope = 'claim_start'"
        )
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
        ("Country Pick",),
    )
    db.execute(
        "DELETE FROM rate_limit_event WHERE scope LIKE 'claim_%' OR scope = 'claim_start'"
    )


def _seed():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {"name": "Country Pick", "contact_email": "host@countrypick.test", "created_at": now},
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Country flat",
            "uby_name": "Country Facility",
            "permalink_token": TOKEN,
            "permalink_window_days": 2,
            "default_purpose": "10",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    stay_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "country-now",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return stay_id


@pytest.fixture(autouse=True)
def _bundled_country_list(monkeypatch):
    """Exercise the offline ISO fallback, so the sort is deterministic.

    The cached police list depends on whatever the mock UbyPort returned earlier
    in the session; the bundled list is the one a guest meets before the first
    successful refresh.
    """
    monkeypatch.setattr(codelists, "cached", lambda kind: [])


def _labels(lang):
    return [option["label"] for option in codelists.nationality_options(lang)]


def test_a_czech_letter_files_under_its_plain_latin_neighbour():
    """``sorted`` compares code points, which buries "Česko" at the very end.

    Folding the combining marks away for the comparison only puts it between
    "Černá Hora" and "Chile", where a guest scanning for "C" will look.
    """
    labels = _labels("cs")
    assert labels.index("Černá Hora") < labels.index("Česko") < labels.index("Chile")
    # The displayed label keeps its diacritics -- only the comparison is folded.
    assert "Česko" in labels


def test_the_list_is_sorted_the_same_way_in_english():
    labels = _labels("en")
    assert labels.index("Czechia") < labels.index("Denmark")


def test_the_usual_nationalities_come_first_in_a_group_of_their_own():
    groups = codelists.country_groups("cs")
    assert [group["key"] for group in groups] == ["countries_common", "countries_all"]
    common = [option["code"] for option in groups[0]["options"]]
    assert common == ["CZE", "SVK", "DEU", "POL", "AUT", "GBR", "USA", "UKR"]
    # The full list is still there, unchanged, for the guest who needs it.
    assert groups[1]["options"] == codelists.nationality_options("cs")


def test_a_common_code_the_code_list_does_not_know_is_skipped(monkeypatch):
    """A code the list does not carry must not leave a blank option behind."""
    short = [
        {"code": "CZE", "label": "Česko"},
        {"code": "POL", "label": "Polsko"},
    ]
    monkeypatch.setattr(codelists, "_all_countries", lambda lang: short)
    groups = codelists.country_groups("cs")
    assert [option["code"] for option in groups[0]["options"]] == ["CZE", "POL"]
    assert all(option["label"] for option in groups[0]["options"])
    # The full group is whatever the list has, not a truncated copy.
    assert groups[1]["options"] == short


@pytest.mark.parametrize(
    ("lang", "common_label", "all_label"),
    [("cs", "Nejčastější", "Všechny státy"), ("en", "Most common", "All countries")],
)
def test_the_form_offers_the_countries_in_two_translated_groups(
    lang, common_label, all_label
):
    stay_id = _seed()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, TOKEN, stay_id, lang=lang)
        form = browser.get(f"/l/{TOKEN}/{stay_id}/new?lang={lang}")
        assert form.status_code == 200
        assert f'<optgroup label="{common_label}">' in form.text
        assert f'<optgroup label="{all_label}">' in form.text
        # Both country fields get the grouping, not just the first.
        assert form.text.count(f'<optgroup label="{common_label}">') == 2
        assert form.text.count(f'<optgroup label="{all_label}">') == 2
        # And the copy really is the guest's language.
        assert i18n.STRINGS[lang]["countries_common"] in form.text
    finally:
        _cleanup()


def test_the_country_field_starts_empty():
    """The guest's phone language is not their nationality.

    The form defaults to Czech or English copy, but a German guest must not find
    "Germany" already chosen -- that is a wrong police report waiting to happen.
    """
    stay_id = _seed()
    try:
        browser = TestClient(app)
        complete_guest_claim(browser, TOKEN, stay_id, lang="cs")
        form = browser.get(f"/l/{TOKEN}/{stay_id}/new?lang=cs")
        assert form.status_code == 200
        assert '<option value="CZE" selected>' not in form.text
        assert '<option value=""' in form.text
    finally:
        _cleanup()


def test_kosovo_can_be_picked_and_passes_validation():
    from app import validation

    assert "Kosovo" in _labels("en")
    assert validation.country_name("XKX", "cs") == "Kosovo"
    assert "XKX" in validation.country_codes()
