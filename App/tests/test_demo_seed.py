"""Demo seeding must work on hosts that block loopback calendar fetches.

Staging runs with UBYPORT_ENV=mock and a loopback mock URL, while the SSRF
screening in feed_url.py is active. Seeding used to point the sample feed at
that loopback address, so "Load demo data" raised a feed error and imported
no stays at all.
"""
from __future__ import annotations

from datetime import timedelta

from app import auth, claim, config, db, demo


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
        owner = auth.create_account(
            "demo-seed@example.test", "Demo Seed", role="host", username="demo-seed"
        )
        apartment_id = demo.seed(owner)
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
        # 9 feed stays plus the paid site booking's own reservation.
        assert len(stays) == 10
        dates = {stay["date_from"] for stay in stays}
        assert today.isoformat() in dates
        assert (today - timedelta(days=1)).isoformat() in dates
        assert (today + timedelta(days=1)).isoformat() in dates
        assert (today + timedelta(days=3)).isoformat() in dates
        # One property never holds two overlapping stays.
        intervals = sorted((s["date_from"], s["date_to"]) for s in stays)
        for (_, end), (start, _) in zip(intervals, intervals[1:]):
            assert start >= end

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
            s for s in stays if s["date_from"] == (today + timedelta(days=5)).isoformat()
        )
        past = next(
            s for s in stays if s["date_from"] == (today - timedelta(days=8)).isoformat()
        )
        locked = next(
            s for s in stays if s["date_from"] == (today + timedelta(days=7)).isoformat()
        )
        assert claim.ensure_row(today_stay["id"])["state"] == claim.PROVISIONAL
        assert claim.ensure_row(assigned["id"])["state"] == claim.CLAIMED
        assert claim.ensure_row(past["id"])["state"] == claim.CLAIMED
        assert claim.ensure_row(locked["id"])["guest_access_locked_at"]

        czech = next(
            s for s in stays if s["date_from"] == (today + timedelta(days=12)).isoformat()
        )
        czech_guests = db.query(
            "SELECT nationality FROM guest WHERE reservation_id = ?", (czech["id"],)
        )
        assert czech_guests and all(g["nationality"] == "CZE" for g in czech_guests)

        loft_stays = db.query(
            "SELECT * FROM reservation WHERE apartment_id = ? ORDER BY date_from",
            (loft["id"],),
        )
        cancelled = next(
            s
            for s in loft_stays
            if s["date_from"] == (today + timedelta(days=45)).isoformat()
        )
        assert cancelled["status"] == "cancelled"

        passport_stay = next(
            s
            for s in loft_stays
            if s["date_from"] == (today + timedelta(days=1)).isoformat()
        )
        passport_guest = db.query_one(
            "SELECT * FROM guest WHERE reservation_id = ? AND is_lead = 1",
            (passport_stay["id"],),
        )
        assert passport_guest["nationality"] == "FRA"
        assert passport_guest["passport_photo_at"]
        from app import passport_photos, reporting

        assert passport_photos.has_photo(int(passport_guest["id"]))
        assert reporting.guest_has_passport_photo(passport_guest)

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

        # The zkratka follows the app rule: derived from the WS login.
        assert studio["uby_mark"] == "12CDEF"
        assert loft["uby_mark"] == "34ABCD"

        # Stay fee on the studio only: config, rate, one filing + adjustment.
        assert studio["stay_fee_collect"] == 1
        assert studio["stay_fee_guest_rails"] == "qr,iban"
        assert studio["stay_fee_rate_czk"] == 500
        assert not loft["stay_fee_collect"]
        assert db.query_one(
            "SELECT 1 AS x FROM stay_fee_rate WHERE apartment_id = ?", (apartment_id,)
        )
        # No sealed filing: invented rows cannot produce an honest PDF/CSV payload.
        assert not db.query_one(
            "SELECT 1 AS x FROM stay_fee_filing WHERE apartment_id = ?", (apartment_id,)
        )

        # Guest pay: today's lead guest is charged; two QR payment requests.
        today_stay = next(s for s in stays if s["date_from"] == today.isoformat())
        lead = db.query_one(
            "SELECT * FROM guest WHERE reservation_id = ? AND is_lead = 1", (today_stay["id"],)
        )
        assert lead["fee_host_decision"] == "charge"
        requests = db.query(
            "SELECT * FROM payment_request WHERE apartment_id = ? ORDER BY id", (apartment_id,)
        )
        assert len(requests) == 2
        assert {r["status"] for r in requests} == {"paid", "awaiting_payment"}
        assert all(r["rail"] == "qr" and r["variable_symbol"] for r in requests)

        # Door code, cleaning, published property page, one paid site booking.
        door_code = db.query_one(
            "SELECT * FROM door_code WHERE reservation_id = ?", (today_stay["id"],)
        )
        assert door_code
        # The window matches the one-night stay and is not due before it opens.
        assert door_code["valid_to"] == (today + timedelta(days=1)).isoformat() + "T11:00:00+00:00"
        assert door_code["next_attempt_at"] == door_code["valid_to"]
        assert db.query(
            "SELECT 1 AS x FROM cleaning_property WHERE apartment_id IN (?, ?)",
            (apartment_id, loft["id"]),
        )
        assert (
            len(
                db.query(
                    "SELECT * FROM cleaning_event WHERE apartment_id IN (?, ?)",
                    (apartment_id, loft["id"]),
                )
            )
            == 2
        )
        assert db.query_one(
            "SELECT 1 AS x FROM property_slug WHERE apartment_id = ? AND published = 1",
            (apartment_id,),
        )
        page = db.query_one(
            "SELECT * FROM property_page WHERE apartment_id = ? AND published = 1", (apartment_id,)
        )
        assert page and page["nightly_price_czk"] == 1500
        assert page["hide_from_search"] == 1
        booking = db.query_one(
            "SELECT * FROM site_booking WHERE apartment_id = ? AND status = 'paid'", (apartment_id,)
        )
        assert booking and booking["total_czk"] == 3000
        # A paid booking owns a reservation, so its dates are blocked and it
        # shows in Stays (booking_direct does the same on payment).
        assert booking["reservation_id"]
        site_stay = db.query_one(
            "SELECT * FROM reservation WHERE id = ?", (booking["reservation_id"],)
        )
        assert site_stay and site_stay["source"] == "site" and site_stay["status"] == "active"

        assert demo.clear()
        assert not db.query_one(
            "SELECT 1 AS x FROM apartment WHERE internal_name IN (?, ?)",
            (demo.DEMO_APARTMENT, demo.DEMO_LOFT),
        )
        assert not db.query_one(
            "SELECT 1 AS x FROM legal_entity WHERE name IN (?, ?)",
            (demo.DEMO_ENTITY, demo.DEMO_CONTROLLER),
        )
        for table in (
            "payment_request",
            "stay_fee_filing",
            "stay_fee_adjustment",
            "stay_fee_rate",
            "door_code",
            "cleaning_event",
            "cleaning_property",
            "property_page",
            "property_slug",
            "site_booking",
            "booking_hold",
        ):
            assert not db.query_one(
                f"SELECT 1 AS x FROM {table} WHERE apartment_id IN (?, ?)",
                (apartment_id, loft["id"]),
            )
    finally:
        _clear_demo()


def test_booking_checkout_refuses_demo_apartments(monkeypatch):
    """A demo property is never publicly bookable, even off the mock."""
    db.init_db()
    _clear_demo()
    monkeypatch.setattr(config, "UBYPORT_ENV", "mock")
    from app import booking_checkout

    try:
        owner = auth.create_account(
            "demo-book@example.test", "Demo Book", role="host", username="demo-book"
        )
        studio = demo.seed(owner)
        assert studio
        q = {"date_from": "2099-01-01", "date_to": "2099-01-03", "total_czk": 100}
        assert booking_checkout.start(
            studio, "slug", q, guest_name="X", guest_email="x@example.test", lang="en"
        ) == {"error": "unavailable"}
        assert booking_checkout.start_direct(
            studio, q, guest_name="X", guest_email="x@example.test", lang="en"
        ) == {"error": "unavailable"}
        assert not db.query_one(
            "SELECT 1 AS x FROM booking_hold WHERE apartment_id = ?", (studio,)
        )
        assert not db.query_one(
            "SELECT 1 AS x FROM site_booking WHERE apartment_id = ? AND status != 'paid'",
            (studio,),
        )
    finally:
        _clear_demo()
