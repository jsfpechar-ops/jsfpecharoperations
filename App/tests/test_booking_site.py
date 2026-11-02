"""Brief 0814: booking site rules (settings, quote, refunds, rows)."""
from __future__ import annotations

from datetime import datetime

import pytest

from app import auth, booking_site, db, property_page

OWNER = "bookingsitehost"
PRAGUE = booking_site.PRAGUE


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def owner():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Booking Host", username=OWNER)
    oid = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"]
    try:
        yield int(oid)
    finally:
        _cleanup()


def _apartment(oid: int) -> int:
    return int(db.insert("apartment", {
        "owner_user_id": oid, "internal_name": "Site Flat", "created_at": db.utcnow(),
        "stay_fee_rate_czk": 50, "checkin_hour": 15,
    }))


NOW = datetime(2026, 11, 2, 12, 0, tzinfo=PRAGUE)


def _priced(aid: int, **extra) -> None:
    values = {"nightly_price_czk": 2000, "cleaning_fee_czk": 500}
    values.update(extra)
    booking_site.save_settings(aid, values)


def test_defaults_and_save(owner):
    aid = _apartment(owner)
    s = booking_site.settings(aid)
    assert s["cancellation_policy"] == "non_refundable"
    assert s["same_day_cutoff_hour"] == 18
    assert s["checkin_hour"] == 15 and s["city_tax_czk"] == 50
    _priced(aid, cancellation_policy="moderate", min_nights=2, max_guests=4)
    s = booking_site.settings(aid)
    assert (s["nightly_price_czk"], s["min_nights"], s["max_guests"]) == (2000, 2, 4)
    assert property_page.nightly_price(aid) == 2000


@pytest.mark.parametrize("field,value", [
    ("nightly_price_czk", 0), ("cleaning_fee_czk", -1), ("min_nights", 31),
    ("max_guests", 61), ("cancellation_policy", "strict"),
    ("advance_notice_days", 5), ("same_day_cutoff_hour", 24),
    ("nightly_price_czk", "2000"), ("min_nights", True),
])
def test_save_rejects_bad_values(owner, field, value):
    aid = _apartment(owner)
    with pytest.raises(ValueError, match=field):
        booking_site.save_settings(aid, {"nightly_price_czk": 1000, field: value})


def test_quote_lines(owner):
    aid = _apartment(owner)
    _priced(aid)
    q = booking_site.quote(aid, "2026-11-10", "2026-11-13", 2, now=NOW)
    assert q["error"] is None
    assert (q["nights"], q["accommodation_czk"], q["total_czk"]) == (3, 6000, 6500)
    assert q["city_tax_on_site_czk"] == 50 * 2 * 3


@pytest.mark.parametrize("dates,guests,code", [
    (("2026-11-10", "2026-11-10"), 2, "bad_dates"),
    (("bad", "2026-11-10"), 2, "bad_dates"),
    (("2026-11-10", "2026-12-15"), 2, "bad_dates"),
    (("2026-11-10", "2026-11-11"), 2, "min_nights"),
    (("2026-11-01", "2026-11-04"), 2, "too_soon"),
    (("2026-11-10", "2026-11-13"), 0, "guests"),
    (("2026-11-10", "2026-11-13"), 5, "guests"),
])
def test_quote_errors(owner, dates, guests, code):
    aid = _apartment(owner)
    _priced(aid, min_nights=2, max_guests=4)
    assert booking_site.quote(aid, dates[0], dates[1], guests, now=NOW)["error"] == code


def test_quote_without_price(owner):
    aid = _apartment(owner)
    assert booking_site.quote(aid, "2026-11-10", "2026-11-13", 2, now=NOW)["error"] == "no_price"


def test_quote_taken_by_reservation(owner):
    aid = _apartment(owner)
    _priced(aid)
    db.insert("reservation", {
        "apartment_id": aid, "source": "manual", "uid": "t-1",
        "date_from": "2026-11-12", "date_to": "2026-11-14", "status": "active",
        "created_at": db.utcnow(), "updated_at": db.utcnow(),
    })
    assert booking_site.quote(aid, "2026-11-10", "2026-11-13", 2, now=NOW)["error"] == "taken"
    assert booking_site.quote(aid, "2026-11-14", "2026-11-16", 2, now=NOW)["error"] is None


def test_same_day_cutoff_and_notice(owner):
    aid = _apartment(owner)
    _priced(aid)
    s = booking_site.settings(aid)
    assert booking_site.earliest_check_in(s, NOW).isoformat() == "2026-11-02"
    late = datetime(2026, 11, 2, 18, 0, tzinfo=PRAGUE)
    assert booking_site.earliest_check_in(s, late).isoformat() == "2026-11-03"
    _priced(aid, advance_notice_days=3)
    s = booking_site.settings(aid)
    assert booking_site.earliest_check_in(s, NOW).isoformat() == "2026-11-05"


def _booking(policy: str) -> dict:
    return {"total_czk": 6500, "cleaning_fee_czk": 500, "refunded_czk": 0,
            "date_from": "2026-11-10", "cancellation_policy": policy}


@pytest.mark.parametrize("policy,when,expected", [
    ("non_refundable", datetime(2026, 11, 1, 12, 0), 0),
    ("flexible", datetime(2026, 11, 9, 15, 0), 6500),
    ("flexible", datetime(2026, 11, 9, 15, 1), 0),
    ("moderate", datetime(2026, 11, 5, 15, 0), 6500),
    ("moderate", datetime(2026, 11, 8, 12, 0), 500 + 3000),
    ("moderate", datetime(2026, 11, 10, 15, 0), 0),
])
def test_refund_rule(policy, when, expected):
    now = when.replace(tzinfo=PRAGUE)
    assert booking_site.refund_czk(_booking(policy), checkin_hour=15, now=now) == expected


def test_refund_by_host_is_full():
    now = datetime(2026, 11, 10, 20, 0, tzinfo=PRAGUE)
    assert booking_site.refund_czk(_booking("non_refundable"), checkin_hour=15,
                                   now=now, by_host=True) == 6500


def test_booking_rows_and_transitions(owner):
    aid = _apartment(owner)
    _priced(aid)
    q = booking_site.quote(aid, "2026-11-10", "2026-11-13", 2, now=NOW)
    row = booking_site.create_pending(aid, owner, q, guest_name="  Jana   Nová ",
                                      guest_email="jana@example.test", lang="cs", hold_id=None)
    assert row["status"] == "pending" and row["guest_name"] == "Jana Nová"
    assert row["cancel_token_hash"] == booking_site.token_hash(row["cancel_token"])
    booking_site.attach_session(row["id"], "cs_test_1")
    assert booking_site.by_session("cs_test_1")["id"] == row["id"]
    assert booking_site.set_status(row["id"], "paid", paid_at=db.utcnow()) is True
    assert booking_site.set_status(row["id"], "paid") is False
    with pytest.raises(ValueError):
        booking_site.set_status(row["id"], "pending")
    assert booking_site.set_status(row["id"], "cancelled", refunded_czk=0) is True


def test_ical_token_is_stable(owner):
    aid = _apartment(owner)
    token = booking_site.ical_token(aid)
    assert len(token) >= 20 and booking_site.ical_token(aid) == token


def test_site_allowed_follows_plan(owner, monkeypatch):
    from app import billing, config

    monkeypatch.setattr(config, "BILLING_ENABLED", False)
    assert booking_site.site_allowed(owner) is True
    monkeypatch.setattr(config, "BILLING_ENABLED", True)
    monkeypatch.setattr(billing, "entitlements",
                        lambda oid: billing.Entitlements(status="active", plan="standard"))
    assert booking_site.site_allowed(owner) is False
    monkeypatch.setattr(billing, "entitlements",
                        lambda oid: billing.Entitlements(status="active", plan="max"))
    assert booking_site.site_allowed(owner) is True
