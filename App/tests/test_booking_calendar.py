"""Brief 0818: public booking calendar helpers (taken nights, grid states, month bounds)."""
from __future__ import annotations

from datetime import date

import pytest

from app import auth, booking_calendar, booking_checkout, booking_site, db, property_page

OWNER = "calhost"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM site_booking WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM booking_hold WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def apartment():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Calendar Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Calendar Flat",
                                      "created_at": db.utcnow()}))
    booking_site.save_settings(aid, {"nightly_price_czk": 2000})
    property_page.publish_page(aid, published=True)
    try:
        yield aid
    finally:
        _cleanup()


def _reservation(aid: int, uid: str, date_from: str, date_to: str) -> None:
    now = db.utcnow()
    db.insert("reservation", {"apartment_id": aid, "source": "manual", "uid": uid,
                              "date_from": date_from, "date_to": date_to,
                              "status": "active", "created_at": now, "updated_at": now})


def _cells(grid):
    return {c["iso"]: c for week in grid["weeks"] for c in week if c["iso"]}


def test_taken_and_hold_nights(apartment):
    _reservation(apartment, "cal-1", "2027-05-10", "2027-05-13")
    assert booking_checkout.hold_dates(apartment, "2027-05-20", "2027-05-22") is not None
    taken = booking_calendar.taken_nights(apartment, date(2027, 5, 1), date(2027, 6, 1))
    assert taken == {"2027-05-10", "2027-05-11", "2027-05-12", "2027-05-20", "2027-05-21"}


def test_grid_marks_states(apartment):
    _reservation(apartment, "cal-2", "2027-05-10", "2027-05-13")
    grid = booking_calendar.month_grid(apartment, 2027, 5, date_from="2027-05-05",
                                       date_to="2027-05-08", today=date(2027, 5, 1))
    cells = _cells(grid)
    assert cells["2027-05-05"]["state"] == "start"
    assert cells["2027-05-06"]["state"] == "range"
    assert cells["2027-05-08"]["state"] == "end"
    assert cells["2027-05-11"]["state"] == "taken"
    assert cells["2027-05-11"]["pick"] is None


def test_pick_end_blocked_by_taken_night(apartment):
    _reservation(apartment, "cal-3", "2027-05-10", "2027-05-13")
    grid = booking_calendar.month_grid(apartment, 2027, 5, date_from="2027-05-08",
                                       today=date(2027, 5, 1))
    cells = _cells(grid)
    assert cells["2027-05-13"]["pick"] == ("2027-05-13", "")
    assert cells["2027-05-10"]["pick"] == ("2027-05-08", "2027-05-10")


def test_month_bounds(apartment):
    today = date(2027, 5, 1)
    grid = booking_calendar.month_grid(apartment, 2027, 5, today=today)
    assert grid["prev"] is None
    assert grid["next"] == (2027, 6)
    far = booking_calendar.month_grid(apartment, 2028, 5, today=today)
    assert far["next"] is None
