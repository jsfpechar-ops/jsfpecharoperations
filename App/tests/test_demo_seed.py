"""Demo seeding must work on hosts that block loopback calendar fetches.

Staging runs with UBYPORT_ENV=mock and a loopback mock URL, while the SSRF
screening in feed_url.py is active. Seeding used to point the sample feed at
that loopback address, so "Load demo data" raised a feed error and imported
no stays at all.
"""
from __future__ import annotations

from datetime import date, timedelta

from app import config, db, demo


def _clear_demo() -> None:
    entity = db.query_one("SELECT * FROM legal_entity WHERE name = ?", (demo.DEMO_ENTITY,))
    if not entity:
        return
    apartments = db.query(
        "SELECT id FROM apartment WHERE legal_entity_id = ?", (entity["id"],)
    )
    for apartment in apartments:
        db.execute("DELETE FROM alert WHERE apartment_id = ?", (apartment["id"],))
        db.execute("DELETE FROM apartment WHERE id = ?", (apartment["id"],))
    db.execute("DELETE FROM legal_entity WHERE id = ?", (entity["id"],))


def test_sample_feed_url_is_public_not_the_mock_server(monkeypatch):
    monkeypatch.setattr(config, "UBYPORT_ENV", "mock")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://ubyhost-staging.example")

    url = demo.sample_calendar_url()

    assert url == "https://ubyhost-staging.example/sample-airbnb.ics"
    assert "127.0.0.1" not in url


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

        stays = db.query(
            "SELECT * FROM reservation WHERE apartment_id = ? ORDER BY date_from",
            (apartment_id,),
        )
        assert len(stays) == 3
        assert {stay["date_from"] for stay in stays} >= {
            date.today().isoformat(),
            (date.today() - timedelta(days=1)).isoformat(),
        }

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
    finally:
        _clear_demo()
