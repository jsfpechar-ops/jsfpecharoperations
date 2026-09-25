"""A stay's length is spelled, not concatenated.

A-13 [UX-50] found the picker, claim, assigned, form and stay pages printing
`{{ nights(...) }} {{ t('nights') }}` against one fixed key. That gives an
English guest "1 nights" and a Czech guest "3 nocí", when Czech wants
"3 noci" and "1 noc". The fix is a `nights_label(from, to)` Jinja global that
picks the plural form from the count.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import claim, db, i18n, templating
from app.main import app

TOKEN = "nightspluraltok"


class _Context:
    """The two keys `nights_label` reads off a Jinja render context."""

    def __init__(self, lang: str):
        self._lang = lang

    def get(self, key, default=None):
        return self._lang if key == "lang" else default


def _label(lang: str, date_from: str, date_to: str) -> str:
    return templating._nights_label(_Context(lang), date_from, date_to)


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
        ("Nights Plural",),
    )


def _seed():
    """One apartment holding a 1-night, a 3-night and a 5-night stay."""
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert(
        "legal_entity",
        {
            "name": "Nights Plural",
            "contact_email": "host@nights.test",
            "contact_phone": "+420111222333",
            "created_at": now,
        },
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Nights flat",
            "uby_name": "Nights Facility",
            "guest_message": "Welcome to Nights Facility.",
            "permalink_token": TOKEN,
            "permalink_window_days": 2,
            "default_purpose": "10",
            "automation_mode": "scheduled",
            "submit_after_hours": 24,
            "active": 1,
            "created_at": now,
        },
    )
    for uid, length in (("nights-1", 1), ("nights-3", 3), ("nights-5", 5)):
        db.insert(
            "reservation",
            {
                "apartment_id": apartment_id,
                "source": "airbnb",
                "uid": uid,
                "date_from": today.isoformat(),
                "date_to": (today + timedelta(days=length)).isoformat(),
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )
    return apartment_id


def test_one_night_is_singular_in_both_languages():
    assert _label("en", "2026-05-01", "2026-05-02") == "1 night"
    assert _label("cs", "2026-05-01", "2026-05-02") == "1 noc"


def test_two_to_four_nights_take_the_czech_few_form():
    for length, czech in ((2, "noci"), (3, "noci"), (4, "noci")):
        day_to = f"2026-05-{length + 1:02d}"
        assert _label("en", "2026-05-01", day_to) == f"{length} nights"
        assert _label("cs", "2026-05-01", day_to) == f"{length} {czech}"


def test_five_or_more_nights_take_the_czech_many_form():
    assert _label("cs", "2026-05-01", "2026-05-06") == "5 nocí"
    assert _label("cs", "2026-05-01", "2026-06-01") == "31 nocí"
    assert _label("en", "2026-05-01", "2026-05-06") == "5 nights"


def test_zero_nights_is_not_treated_as_one():
    # a same-day booking still has to read as a count, not as "1 night"
    assert _label("cs", "2026-05-01", "2026-05-01") == "0 nocí"
    assert _label("en", "2026-05-01", "2026-05-01") == "0 nights"


def test_a_missing_or_broken_date_does_not_raise():
    assert _label("cs", "", "") == "0 nocí"
    assert _label("cs", "not-a-date", "2026-05-06") == "0 nocí"


def test_the_plural_keys_are_at_parity():
    keys = {"night_one", "nights_few", "nights_many"}
    assert keys <= set(i18n.STRINGS["en"])
    assert keys <= set(i18n.STRINGS["cs"])


def test_the_old_fixed_label_key_is_gone():
    # it only ever produced "1 nights" / "1 nocí"; nothing may reach for it again
    assert "nights" not in i18n.STRINGS["en"]
    assert "nights" not in i18n.STRINGS["cs"]


@pytest.mark.parametrize("name", ["pick", "claim", "assigned", "form", "stay"])
def test_no_guest_page_still_concatenates_the_count(name):
    source = (
        templating.config.BASE_DIR / "templates" / "guest" / f"{name}.html"
    ).read_text(encoding="utf-8")
    assert "t('nights')" not in source
    assert "nights_label(" in source


def test_the_picker_spells_each_stay_in_the_page_language():
    _seed()
    try:
        client = TestClient(app)
        english = client.get(f"/l/{TOKEN}?lang=en", follow_redirects=True).text
        assert "<span>1 night</span>" in english
        assert "<span>3 nights</span>" in english
        assert "<span>5 nights</span>" in english
        assert "<span>1 nights</span>" not in english

        czech = client.get(f"/l/{TOKEN}?lang=cs", follow_redirects=True).text
        assert "<span>1 noc</span>" in czech
        assert "<span>3 noci</span>" in czech
        assert "<span>5 nocí</span>" in czech
        assert "<span>1 nocí</span>" not in czech
        assert "<span>3 nocí</span>" not in czech
    finally:
        _cleanup()
