"""Brief 0817: booking site iCal export."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, booking_ical, booking_site, db, property_page
from app.main import app

OWNER = "icalhost"


def _cleanup():
    row = db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))
    if not row:
        return
    oid = row["id"]
    for a in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
        db.execute("DELETE FROM reservation WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_slug_history WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM property_page WHERE apartment_id = ?", (a["id"],))
        db.execute("DELETE FROM settings WHERE key = ?", (f"booking_site:{a['id']}",))
    db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
    db.execute("DELETE FROM rate_limit_event", ())
    db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


@pytest.fixture
def apartment():
    db.init_db()
    _cleanup()
    auth.create_account(f"{OWNER}@example.test", "Ical Host", username=OWNER)
    oid = int(db.query_one("SELECT id FROM user_account WHERE username = ?", (OWNER,))["id"])
    aid = int(db.insert("apartment", {"owner_user_id": oid, "internal_name": "Ical Flat",
                                      "created_at": db.utcnow()}))
    property_page.ensure_slug(aid)
    try:
        yield aid
    finally:
        _cleanup()


def _stay(aid: int, uid: str, source: str, d_from: str, d_to: str, status: str = "active") -> int:
    return int(db.insert("reservation", {
        "apartment_id": aid, "source": source, "uid": uid, "date_from": d_from,
        "date_to": d_to, "summary": "Jana Nová", "guest_email": "jana@example.test",
        "status": status, "created_at": db.utcnow(), "updated_at": db.utcnow(),
    }))


def test_export_has_site_and_manual_only(apartment):
    site = _stay(apartment, "site-1", "site", "2027-05-01", "2027-05-03")
    _stay(apartment, "m-1", "manual", "2027-05-05", "2027-05-06")
    _stay(apartment, "abnb-1", "ical", "2027-05-10", "2027-05-12")
    _stay(apartment, "c-1", "site", "2027-05-20", "2027-05-22", status="cancelled")
    _stay(apartment, "old-1", "manual", "2027-01-01", "2027-01-02")
    body = booking_ical.export_ics(apartment, today=date(2027, 4, 1))
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert body.count("BEGIN:VEVENT") == 2
    assert f"UID:ubyhost-{site}@ubyhost.cz" in body
    assert "DTSTART;VALUE=DATE:20270501" in body and "DTEND;VALUE=DATE:20270503" in body
    assert "Jana" not in body and "@example.test" not in body


def test_route_needs_the_token(apartment):
    _stay(apartment, "site-2", "site", "2027-06-01", "2027-06-04")
    slug = property_page.account_row(apartment)["slug"]
    token = booking_site.ical_token(apartment)
    client = TestClient(app)
    ok = client.get(f"/p/{slug}/{token}.ics")
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("text/calendar")
    assert "DTSTART;VALUE=DATE:20270601" in ok.text
    assert client.get(f"/p/{slug}/wrong-token.ics").status_code == 404
    assert client.get(f"/p/no-such-slug/{token}.ics").status_code == 404


def test_feed_survives_rename(apartment):
    slug = property_page.account_row(apartment)["slug"]
    token = booking_site.ical_token(apartment)
    db.execute("INSERT INTO property_slug_history (old_slug, apartment_id, created_at)"
               " VALUES (?, ?, ?)", ("old-name-abcd", apartment, db.utcnow()))
    client = TestClient(app)
    assert client.get(f"/p/old-name-abcd/{token}.ics").status_code == 200
    assert client.get(f"/p/{slug}/{token}.ics").status_code == 200
