"""WP33: two changes the council asked for before the first real host.

1. A stay past its police deadline with a guest still unfiled is in the default
   Stays view, even after the guests left. The dashboard counted it as overdue
   while the Stays list, which opens on "Upcoming & current", hid it.
2. ``UBYHOST_GUEST_LANGS`` keeps German, Spanish and French off until a native
   speaker has read them. English and Czech are always on.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import auth, db, deadlines, host_i18n, i18n, reporting
from app.main import app

USERNAME = "wp33-overdue-host"
PASSWORD = "Secure-Password-123"
TOKEN = "wp33overduetoken"


def _cleanup() -> None:
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
    if apartment["legal_entity_id"]:
        db.execute("DELETE FROM legal_entity WHERE id = ?", (apartment["legal_entity_id"],))


def _past_deadline_arrival() -> date:
    """An arrival 10 to 20 days ago, its deadline long gone, guests already left."""
    now = deadlines.local_now()
    for back in range(10, 21):
        candidate = date.today() - timedelta(days=back)
        if deadlines.reporting_deadline(candidate) < now:
            return candidate
    pytest.skip("no past-deadline arrival found")


@pytest.fixture
def stays():
    db.init_db()
    _cleanup()
    now = db.utcnow()
    existing = db.query_one("SELECT id FROM user_account WHERE username = ?", (USERNAME,))
    user_id = (
        existing["id"]
        if existing
        else auth.create_account(USERNAME, PASSWORD, "WP33 Host", must_change_password=False)
    )
    entity_id = db.insert(
        "legal_entity", {"name": "WP33 s.r.o.", "owner_user_id": user_id, "created_at": now}
    )
    apartment_id = db.insert(
        "apartment",
        {
            "legal_entity_id": entity_id,
            "owner_user_id": user_id,
            "internal_name": "WP33 Loft",
            "permalink_token": TOKEN,
            "automation_mode": "manual",
            "default_purpose": "10",
            "uby_mark": "DEMO1",
            "active": 1,
            "created_at": now,
        },
    )
    arrival = _past_deadline_arrival()

    def add(uid: str, state: str) -> int:
        reservation_id = db.insert(
            "reservation",
            {
                "apartment_id": apartment_id,
                "source": "airbnb",
                "uid": uid,
                "date_from": arrival.isoformat(),
                "date_to": (arrival + timedelta(days=3)).isoformat(),
                "status": "active",
                "expected_guests_override": 1,
                "created_at": now,
                "updated_at": now,
            },
        )
        db.insert(
            "guest",
            {
                "reservation_id": reservation_id,
                "surname": f"WP33{uid.upper()}",
                "first_name": "ANNA",
                "birth_date": "01011990",
                "nationality": "DEU",
                "doc_number": "P9988771",
                "res_street": "Hauptstrasse 5",
                "res_city": "Berlin",
                "res_country": "DEU",
                "purpose": "10",
                "is_lead": 1,
                "entered_by": "guest",
                "signature_png": "imported",
                "signed_at": now,
                "passport_photo_at": now,
                "identity_verified_at": now,
                "stay_from": arrival.isoformat(),
                "stay_to": (arrival + timedelta(days=3)).isoformat(),
                "submit_state": state,
                "submitted_at": now if state == reporting.SENT else None,
                "created_at": now,
                "updated_at": now,
            },
        )
        return reservation_id

    unfiled = add("unfiled", reporting.PENDING)
    filed = add("filed", reporting.SENT)
    client = TestClient(app)
    client.post("/login", data={"username": USERNAME, "password": PASSWORD}, follow_redirects=False)
    client.cookies.set(host_i18n.LANG_COOKIE, "en")
    yield client, unfiled, filed
    _cleanup()


def test_an_overdue_unfiled_stay_is_in_the_default_stays_view(stays):
    client, unfiled, _filed = stays

    page = client.get("/reservations")

    assert page.status_code == 200
    assert f"/reservations/{unfiled}" in page.text


def test_a_filed_past_stay_stays_out_of_the_default_view(stays):
    client, _unfiled, filed = stays

    page = client.get("/reservations")

    assert f"/reservations/{filed}" not in page.text


def test_the_past_view_is_unchanged(stays):
    client, unfiled, filed = stays

    page = client.get("/reservations?range=past")

    assert f"/reservations/{unfiled}" in page.text
    assert f"/reservations/{filed}" in page.text


def test_guest_languages_default_to_english_and_czech(monkeypatch):
    monkeypatch.delenv("UBYHOST_GUEST_LANGS", raising=False)

    assert i18n.enabled_languages() == ("en", "cs")
    assert i18n.supported_language("de") is None
    assert i18n.accept_language_match("de-AT,de;q=0.9,en;q=0.5") == "en"
    assert i18n.normalise_language("fr") == "en"


def test_a_language_is_switched_on_by_name(monkeypatch):
    monkeypatch.setenv("UBYHOST_GUEST_LANGS", "en,cs,de")

    assert i18n.enabled_languages() == ("en", "cs", "de")
    assert i18n.accept_language_match("de-AT") == "de"
    assert i18n.supported_language("es") is None


def test_english_and_czech_cannot_be_switched_off(monkeypatch):
    monkeypatch.setenv("UBYHOST_GUEST_LANGS", "de")

    assert i18n.enabled_languages() == ("en", "cs", "de")


def test_the_switcher_offers_only_enabled_languages(monkeypatch):
    from app.routes import guest

    monkeypatch.setenv("UBYHOST_GUEST_LANGS", "en,cs")

    class _Url:
        path = "/g/x"

    class _Request:
        url = _Url()

        class query_params:
            @staticmethod
            def multi_items():
                return []

    assert list(guest._lang_urls(_Request())) == ["en", "cs"]
