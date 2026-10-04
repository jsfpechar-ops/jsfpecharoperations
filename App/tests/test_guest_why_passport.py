"""UX-60 (A-24): the passport point must not say two different things.

The guest was told, in English, that the upload happens "if your host asks for
it", and in Czech that every non-Czech must upload. Both halves of that are
true of the feature - the host turns the policy on, and foreign guests are
then the ones who have to upload - so the sentence has to say both, the same
way, in both languages.

WP17 (review 3.E item 4) then cut the "why" fold down to the accuracy point.
The passport fact now lives in one place: the legal notice on the form, which
is also gated on the policy. These tests follow it there.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app import claim, db, i18n
from app.main import app
from app.routes import guest
from tests.conftest import complete_guest_claim

TOKEN = "whypptoken"
OLD_EN = "asks for it"
OLD_CS = "nejste občanem ČR"
EN_PASSPORT = "Foreign guests upload a photo of their passport or ID page"
CS_PASSPORT = "Cizinci nahrají fotku stránky pasu nebo průkazu"


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
        ("Why PP Test",),
    )


def _seed(policy: str):
    db.init_db()
    _cleanup()
    now = db.utcnow()
    today = claim.prague_today()
    entity_id = db.insert("legal_entity", {"name": "Why PP Test", "created_at": now})
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "internal_name": "Why PP apartment",
            "permalink_token": TOKEN,
            "permalink_window_days": 14,
            "default_purpose": "10",
            "automation_mode": "manual",
            "passport_photo_policy": policy,
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "source": "airbnb",
            "uid": "why-pp-1",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=4)).isoformat(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    return reservation_id


def test_the_why_fold_no_longer_repeats_the_passport_point():
    for lang in ("en", "cs"):
        assert "why_point_passport" not in i18n.STRINGS[lang], lang
    template = (
        Path(__file__).resolve().parents[1] / "app" / "templates" / "guest" / "_why.html"
    ).read_text(encoding="utf-8")
    assert "why_point_passport" not in template
    assert "require_passport" not in template


def test_both_languages_say_foreign_guests_upload():
    """The two catalogues must carry the same fact, not two different rules."""
    en = i18n.STRINGS["en"]["legal_notice_passport_body"]
    cs = i18n.STRINGS["cs"]["legal_notice_passport_body"]
    assert en.startswith(EN_PASSPORT)
    assert cs.startswith(CS_PASSPORT)
    # Neither side may still claim the old, contradictory rule.
    assert OLD_EN not in en
    assert OLD_CS not in cs


def test_both_languages_say_only_the_host_sees_it_and_it_is_deleted():
    en = i18n.STRINGS["en"]["legal_notice_passport_body"]
    cs = i18n.STRINGS["cs"]["legal_notice_passport_body"]
    assert "Only your host sees it" in en
    assert "deleted after the check" in en
    assert "Uvidí ji jen ubytovatel" in cs
    assert "Po kontrole se smaže" in cs


def test_the_passport_point_renders_when_the_host_requires_it():
    reservation_id = _seed("required_foreign")
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, TOKEN, reservation_id, party_size=1)
        en_page = browser.get(f"/l/{TOKEN}/{reservation_id}", follow_redirects=True)
        assert en_page.status_code == 200
        assert EN_PASSPORT in en_page.text
        assert OLD_EN not in en_page.text

        cs_page = browser.get(
            f"/l/{TOKEN}/{reservation_id}?lang=cs", follow_redirects=True
        )
        assert cs_page.status_code == 200
        assert CS_PASSPORT in cs_page.text
        assert OLD_CS not in cs_page.text
    finally:
        _cleanup()


def test_the_passport_point_is_absent_when_the_host_does_not_ask_for_it():
    """The sentence is gated on the policy, so it cannot promise an upload."""
    reservation_id = _seed("off")
    try:
        browser = TestClient(app)
        browser.cookies.set(guest.LANG_COOKIE, "en")
        complete_guest_claim(browser, TOKEN, reservation_id, party_size=1)
        page = browser.get(f"/l/{TOKEN}/{reservation_id}", follow_redirects=True)
        assert page.status_code == 200
        assert EN_PASSPORT not in page.text
    finally:
        _cleanup()
