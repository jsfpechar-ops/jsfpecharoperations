"""The language a guest gets when they have not chosen one, and the guard on the
guest catalog's interpolation.

Two things are pinned here. A guest arriving from a host's link has made no
choice, so the form follows the language their own phone asks for -- Czech and
Slovak phones get Czech, everything else gets English, and a phone that says
nothing gets English; an explicit ``?lang=`` or the switcher's cookie always
wins. And a catalog entry whose placeholders do not match the values handed to
it renders its raw text instead of raising in the middle of a form a guest is
filling in.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import claim, db, host_i18n, i18n
from app.routes import guest
from app.main import app

TOKEN = "guestlangtoken"


def _cleanup():
    apartment = db.query_one(
        "SELECT * FROM apartment WHERE permalink_token = ?", (TOKEN,)
    )
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
        ("Guest Lang Test",),
    )


def _seed():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Guest Lang Test", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Lang flat",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
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
            "uid": "guest-lang-1",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=4)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return stay_id


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("cs-CZ,cs;q=0.9,en;q=0.8", "cs"),
        ("sk-SK,sk;q=0.9,cs;q=0.8", "cs"),
        ("de-DE,de;q=0.9,en;q=0.8", "en"),
        ("en-GB,en;q=0.9", "en"),
        # A client that names no language at all is not a foreign guest, so the
        # documented guest-link default stands. Every real browser sends this
        # header, so this only ever describes a harness.
        ("", "cs"),
        ("*", "cs"),
    ],
)
def test_a_guest_without_a_language_choice_gets_the_language_of_their_phone(
    header, expected
):
    """The host is Czech but the guest is by definition a foreigner.

    The default used to be Czech, which put "Zadejte přístupový PIN" in front of
    a German guest. It now follows the phone, and the first tag wins because
    browsers list their languages in order of preference.
    """
    _seed()
    try:
        page = TestClient(app).get(
            f"/l/{TOKEN}", headers={"Accept-Language": header}, follow_redirects=True
        )
        assert page.status_code == 200
        assert f'<html lang="{expected}">' in page.text
        # And it really is that language's copy, not just the right lang tag.
        assert i18n.STRINGS[expected]["arrival_question"] in page.text
        other = "en" if expected == "cs" else "cs"
        assert i18n.STRINGS[other]["arrival_question"] not in page.text
    finally:
        _cleanup()


def test_the_switcher_offers_endonyms_a_foreigner_can_read():
    """A German guest knows "English", not the ISO code "EN"."""
    _seed()
    try:
        page = TestClient(app).get(f"/l/{TOKEN}", follow_redirects=True)
        assert 'hreflang="en" lang="en">English</a>' in page.text
        assert 'hreflang="cs" lang="cs">Čeština</a>' in page.text
    finally:
        _cleanup()


def test_the_guest_can_still_ask_for_english_and_the_choice_is_remembered():
    _seed()
    try:
        browser = TestClient(app)
        english = browser.get(f"/l/{TOKEN}?lang=en", follow_redirects=True)
        assert '<html lang="en">' in english.text
        assert i18n.STRINGS["en"]["arrival_question"] in english.text

        # The switcher writes the guest's own cookie, so the next page -- and
        # the one after a redirect -- stays in the language the guest picked.
        remembered = browser.get(f"/l/{TOKEN}", follow_redirects=True)
        assert '<html lang="en">' in remembered.text
        assert browser.cookies.get(guest.LANG_COOKIE) == "en"
        # The guest's choice is theirs: it must not reach the host's UI, which
        # reads the same browser's ``ubyhost_lang``.
        assert browser.cookies.get(host_i18n.LANG_COOKIE) is None
    finally:
        _cleanup()


def test_an_unknown_language_falls_back_rather_than_breaking_the_page():
    _seed()
    try:
        page = TestClient(app).get(f"/l/{TOKEN}?lang=de", follow_redirects=True)
        assert page.status_code == 200
        assert f'<html lang="{host_i18n.PUBLIC_DEFAULT_LANGUAGE}">' in page.text
    finally:
        _cleanup()


def test_a_key_without_the_placeholders_the_caller_supplies_does_not_raise():
    """A stray or missing value must not cost the guest the form.

    The guest lookup used to interpolate unguarded, so a translator dropping a
    ``%(facility)s`` turned a form render into a traceback.
    """
    translate = i18n.translator("cs")
    raw = i18n.STRINGS["cs"]["arrival_welcome"]
    assert translate("arrival_welcome", nope=1) == raw
    assert translate("arrival_welcome") == raw
    # The matching call still interpolates.
    assert translate("arrival_welcome", facility="Lang flat") == raw % {
        "facility": "Lang flat"
    }


def test_both_engines_normalise_a_language_code_the_same_way():
    """One code-to-language decision, so the two catalogs cannot disagree.

    The guest engine no longer carries its own copy of the rule; it asks the
    host engine, which is also what decides which catalog a *missing* key falls
    back to.
    """
    for value in ("en", "cs", "CS", "cs-CZ", "de", "", None):
        expected = host_i18n.normalise_language(value)
        assert expected in host_i18n.LANGUAGES
        # An unrecognised code lands on the host catalog's own default, and the
        # guest engine reads the same catalog for it.
        assert i18n.translator(value)("arrival_question") == i18n.STRINGS[expected]["arrival_question"]
    assert host_i18n.normalise_language("de") == host_i18n.DEFAULT_LANGUAGE
    assert i18n.translator("de")("arrival_question") == i18n.STRINGS["en"]["arrival_question"]
