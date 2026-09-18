"""Demo seeding must work on hosts that block loopback calendar fetches.

Staging runs with UBYPORT_ENV=mock and a loopback mock URL, while the SSRF
screening in feed_url.py is active. Seeding used to point the sample feed at
that loopback address, so "Load demo data" raised a feed error and imported
no stays at all.
"""
from __future__ import annotations

from datetime import timedelta

from app import claim, config, db, demo


def _clear_demo() -> None:
    demo.clear()


def test_sample_feed_url_is_public_not_the_mock_server(monkeypatch):
    monkeypatch.setattr(config, "UBYPORT_ENV", "mock")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://ubyhost-staging.example")

    url = demo.sample_calendar_url()

    assert url == "https://ubyhost-staging.example/sample-airbnb.ics"
    assert "127.0.0.1" not in url


def test_demo_data_cannot_be_seeded_against_real_ubyport(monkeypatch):
    db.init_db()
    monkeypatch.setattr(config, "UBYPORT_ENV", "production")

    assert demo.seed() is None


def test_seed_imports_stays_without_fetching_the_calendar(monkeypatch):
    db.init_db()
    _clear_demo()
    monkeypatch.setattr(config, "UBYPORT_ENV", "mock")
    monkeypatch.setattr(config, "ICAL_ALLOW_PRIVATE", False)

    def _no_network(*args, **kwargs):
        raise AssertionError("demo seeding must not fetch the sample calendar")

    monkeypatch.setattr(demo.icalsync, "fetch_feed", _no_network)

    try:
        apartment_id = demo.seed()
        assert apartment_id

        studio = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
        loft = db.query_one(
            "SELECT * FROM apartment WHERE internal_name = ?", (demo.DEMO_LOFT,)
        )
        assert studio["internal_name"] == demo.DEMO_APARTMENT
        assert loft is not None
        assert studio["permalink_pin"] == demo.DEMO_PINS[demo.DEMO_APARTMENT]
        assert loft["permalink_pin"] == demo.DEMO_PINS[demo.DEMO_LOFT]
        assert (studio["passport_photo_policy"] or "off") == "off"
        assert loft["passport_photo_policy"] == "required_foreign"
        assert studio["data_controller_entity_id"] in (None, 0)
        assert loft["data_controller_entity_id"]
        controller = db.query_one(
            "SELECT * FROM legal_entity WHERE id = ?",
            (loft["data_controller_entity_id"],),
        )
        assert controller["name"] == demo.DEMO_CONTROLLER
        assert studio["automation_mode"] == "manual"
        assert loft["automation_mode"] == "scheduled"

        today = claim.prague_today()
        stays = db.query(
            "SELECT * FROM reservation WHERE apartment_id = ? ORDER BY date_from",
            (apartment_id,),
        )
        assert len(stays) == 9
        dates = {stay["date_from"] for stay in stays}
        assert today.isoformat() in dates
        assert (today - timedelta(days=1)).isoformat() in dates
        assert (today + timedelta(days=1)).isoformat() in dates
        assert (today + timedelta(days=2)).isoformat() in dates

        # Arrival-lane window: today through +3 days includes multiple stays.
        horizon = (today + timedelta(days=3)).isoformat()
        visible = [
            stay
            for stay in stays
            if today.isoformat() <= stay["date_from"] <= horizon
        ]
        assert len(visible) >= 3

        # Claim / console path: provisional on today, assigned further out.
        today_stay = next(s for s in stays if s["date_from"] == today.isoformat())
        assigned = next(
            s for s in stays if s["date_from"] == (today + timedelta(days=2)).isoformat()
        )
        past = next(
            s for s in stays if s["date_from"] == (today - timedelta(days=8)).isoformat()
        )
        locked = next(
            s for s in stays if s["date_from"] == (today + timedelta(days=6)).isoformat()
        )
        assert claim.ensure_row(today_stay["id"])["state"] == claim.PROVISIONAL
        assert claim.ensure_row(assigned["id"])["state"] == claim.CLAIMED
        assert claim.ensure_row(past["id"])["state"] == claim.CLAIMED
        assert claim.ensure_row(locked["id"])["guest_access_locked_at"]

        czech = next(
            s for s in stays if s["date_from"] == (today + timedelta(days=9)).isoformat()
        )
        czech_guests = db.query(
            "SELECT nationality FROM guest WHERE reservation_id = ?", (czech["id"],)
        )
        assert czech_guests and all(g["nationality"] == "CZE" for g in czech_guests)

        feed = db.query_one(
            "SELECT * FROM ical_feed WHERE apartment_id = ?", (apartment_id,)
        )
        assert feed["last_status"] == "ok"
        assert not feed["last_error"]
        assert not db.query_one(
            "SELECT 1 AS x FROM alert WHERE apartment_id = ? AND kind = 'feed_error' "
            "AND resolved_at IS NULL",
            (apartment_id,),
        )

        assert demo.clear()
        assert not db.query_one(
            "SELECT 1 AS x FROM apartment WHERE internal_name IN (?, ?)",
            (demo.DEMO_APARTMENT, demo.DEMO_LOFT),
        )
        assert not db.query_one(
            "SELECT 1 AS x FROM legal_entity WHERE name IN (?, ?)",
            (demo.DEMO_ENTITY, demo.DEMO_CONTROLLER),
        )
    finally:
        _clear_demo()
