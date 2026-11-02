"""Booking site setup page (brief 0819): steps, form parsing, Max gate, publish."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_setup, booking_site, config, db, property_page
from app.main import app
from tests.conftest import login_as

OWNER = "bsitehost"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        aid = a["id"]
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM settings WHERE key IN (?, ?)",
                   (f"booking_site:{aid}", f"booking_site_ical_done:{aid}"))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (aid,))
        db.execute("DELETE FROM guide_import WHERE apartment_id = ?", (aid,))
    db.execute("DELETE FROM stripe_account WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM alert WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM login_token", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Booking Site Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    try:
        yield int(oid)
    finally:
        _cleanup()


@pytest.fixture
def client(owner):
    client = TestClient(app)
    response = login_as(client, OWNER, url="/login?lang=en", follow_redirects=False)
    assert response.status_code == 303
    return client


@pytest.fixture
def stripe_mode(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_MODE", "test")


def _apartment(oid: int, name="Site Flat") -> int:
    return int(db.insert("apartment", {
        "owner_user_id": oid, "internal_name": name, "created_at": db.utcnow(),
    }))


def _connect_stripe(oid: int) -> None:
    now = db.utcnow()
    db.insert("stripe_account", {
        "owner_user_id": oid, "stripe_account_id": "acct_bsite_setup", "mode": "test",
        "onboarding_state": "complete", "charges_enabled": 1, "payouts_enabled": 1,
        "created_at": now, "updated_at": now,
    })


def _form(**extra):
    data = {
        "nightly_price_czk": "1800", "cleaning_fee_czk": "600", "min_nights": "2",
        "max_guests": "4", "cancellation_policy": "moderate", "notice": "0:18",
    }
    data.update(extra)
    return data


def test_steps_start_open_and_advance(owner, stripe_mode):
    aid = _apartment(owner)
    rows = booking_setup.steps(aid, owner)
    assert len(rows) == 6
    assert [r["current"] for r in rows].count(True) == 1
    assert next(r for r in rows if r["current"])["key"] == "stripe"
    assert not booking_setup.can_publish(rows)

    _connect_stripe(owner)
    booking_site.save_settings(aid, {"nightly_price_czk": 1800})
    rows = booking_setup.steps(aid, owner)
    done = {r["key"]: r["done"] for r in rows}
    assert done["stripe"] and done["price"] and done["policy"]
    assert next(r for r in rows if r["current"])["key"] == "page"
    assert booking_setup.can_publish(rows)


def test_parse_form_and_errors(owner):
    parsed = booking_setup.parse_form({
        "nightly_price_czk": "1 800", "cleaning_fee_czk": "", "min_nights": "2",
        "max_guests": "", "cancellation_policy": "moderate", "notice": "0:18",
    })
    assert parsed == {
        "nightly_price_czk": 1800, "cleaning_fee_czk": 0, "min_nights": 2,
        "max_guests": 0, "cancellation_policy": "moderate",
        "advance_notice_days": 0, "same_day_cutoff_hour": 18,
    }
    with pytest.raises(ValueError, match="advance_notice_days"):
        booking_setup.parse_form(_form(notice="5"))
    with pytest.raises(ValueError, match="nightly_price_czk"):
        booking_setup.parse_form(_form(nightly_price_czk="abc"))
    assert booking_setup.error_field(ValueError("same_day_cutoff_hour")) == "advance_notice_days"


def test_page_renders_for_the_owner(owner, client):
    aid = _apartment(owner)
    response = client.get(f"/apartments/{aid}/booking-site?lang=en")
    assert response.status_code == 200
    assert "Setup, step by step (0 of 6)" in response.text
    assert 'name="nightly_price_czk"' in response.text
    assert "/predplatne" not in response.text
    assert ".ics" in response.text
    assert "data:image/png;base64" in response.text

    auth.create_account("bsite-other@example.test", "Other Host", username="bsite-other")
    other = db.query_one("SELECT id FROM user_account WHERE username = ?", ("bsite-other",))["id"]
    try:
        foreign = _apartment(int(other), name="Foreign Flat")
        assert client.get(f"/apartments/{foreign}/booking-site?lang=en").status_code == 404
    finally:
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (other,))
        db.execute("DELETE FROM user_account WHERE id = ?", (other,))


def test_save_settings_roundtrip(owner, client):
    aid = _apartment(owner)
    response = client.post(f"/apartments/{aid}/booking-site", data=_form(),
                           follow_redirects=False)
    assert response.status_code == 303
    s = booking_site.settings(aid)
    assert s["nightly_price_czk"] == 1800
    assert s["cleaning_fee_czk"] == 600
    assert s["min_nights"] == 2
    assert s["max_guests"] == 4
    assert s["cancellation_policy"] == "moderate"
    assert property_page.nightly_price(aid) == 1800

    bad = client.post(f"/apartments/{aid}/booking-site", data=_form(nightly_price_czk="0"),
                      follow_redirects=False)
    assert bad.status_code == 303
    assert "err=" in bad.headers["location"]
    assert booking_site.settings(aid)["nightly_price_czk"] == 1800


def test_max_gate(owner, client, monkeypatch):
    aid = _apartment(owner)
    monkeypatch.setattr(booking_site, "site_allowed", lambda owner_user_id: False)
    response = client.get(f"/apartments/{aid}/booking-site?lang=en")
    assert "/predplatne" in response.text
    assert 'name="nightly_price_czk"' not in response.text

    before = booking_site.settings(aid)["nightly_price_czk"]
    refused = client.post(f"/apartments/{aid}/booking-site", data=_form(),
                          follow_redirects=False)
    assert refused.status_code == 303
    assert "err=" in refused.headers["location"]
    assert booking_site.settings(aid)["nightly_price_czk"] == before


def test_publish_needs_stripe_and_price(owner, client, stripe_mode):
    aid = _apartment(owner)
    client.post(f"/apartments/{aid}/booking-site", data={"publish": "1"},
                follow_redirects=False)
    assert not property_page.page_for(aid)["published"]

    _connect_stripe(owner)
    booking_site.save_settings(aid, {"nightly_price_czk": 1800})
    client.post(f"/apartments/{aid}/booking-site", data={"publish": "1"},
                follow_redirects=False)
    assert property_page.page_for(aid)["published"]

    client.post(f"/apartments/{aid}/booking-site", data={"unpublish": "1"},
                follow_redirects=False)
    assert not property_page.page_for(aid)["published"]


def test_ical_done_mark(owner, client, stripe_mode):
    aid = _apartment(owner)
    client.post(f"/apartments/{aid}/booking-site", data={"ical_done": "1"},
                follow_redirects=False)
    calendar = next(r for r in booking_setup.steps(aid, owner) if r["key"] == "calendar")
    assert calendar["done"]
