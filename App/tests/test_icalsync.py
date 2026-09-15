from app import config, db, icalsync

AIRBNB = """BEGIN:VCALENDAR
PRODID;X-RICAL-TZSOURCE=TZINFO:-//Airbnb Inc//Hosting Calendar 0.8.8//EN
CALSCALE:GREGORIAN
VERSION:2.0
BEGIN:VEVENT
DTEND;VALUE=DATE:20260915
DTSTART;VALUE=DATE:20260910
UID:1418fb94e984-aaaa@airbnb.com
DESCRIPTION:Reservation URL: https://www.airbnb.com/hosting/reservations/details/HM123ABC\\nPhone Number (Last 4 Digits): 0431
SUMMARY:Reserved
END:VEVENT
BEGIN:VEVENT
DTEND;VALUE=DATE:20260920
DTSTART;VALUE=DATE:20260918
UID:1418fb94e984-bbbb@airbnb.com
SUMMARY:Airbnb (Not available)
END:VEVENT
END:VCALENDAR
"""

BOOKING = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Booking.com//Calendar//EN
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261001
DTEND;VALUE=DATE:20261004
UID:booking-12345@booking.com
SUMMARY:CLOSED - Not available
END:VEVENT
END:VCALENDAR
"""


def test_airbnb_reservation_is_extracted():
    events = icalsync.parse_events(AIRBNB)
    reservations = [e for e in events if not e["is_block"]]
    assert len(reservations) == 1
    event = reservations[0]
    assert event["date_from"] == "2026-09-10"
    assert event["date_to"] == "2026-09-15"
    assert event["reservation_url"] == "https://www.airbnb.com/hosting/reservations/details/HM123ABC"
    assert event["phone_last4"] == "0431"
    # Airbnb removed guest names from the export in 2019; nothing to hint at.
    assert event["name_hint"] == ""


def test_airbnb_block_is_recognised():
    events = icalsync.parse_events(AIRBNB)
    blocks = [e for e in events if e["is_block"]]
    assert len(blocks) == 1
    assert blocks[0]["date_from"] == "2026-09-18"


def test_booking_closed_is_imported_as_a_stay():
    # Booking.com labels every reservation "CLOSED - Not available". We import
    # them as stays; the host can mark a manual closure as "ignored" later.
    events = icalsync.parse_events(BOOKING)
    assert len(events) == 1
    assert events[0]["is_block"] is False


def test_is_block_keywords():
    assert icalsync.is_block("Airbnb (Not available)")
    assert icalsync.is_block("Blocked")
    assert not icalsync.is_block("CLOSED - Not available")
    assert not icalsync.is_block("Reserved")
    assert not icalsync.is_block("Anna Smith")


def test_guest_name_hint_only_for_non_generic_summaries():
    assert icalsync._guest_name_hint("Reserved") == ""
    assert icalsync._guest_name_hint("CLOSED") == ""
    assert icalsync._guest_name_hint("Anna S.") == "Anna S."


def test_missing_dtend_becomes_one_night():
    ics = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART;VALUE=DATE:20260910\nUID:x@y\nSUMMARY:Reserved\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    event = icalsync.parse_events(ics)[0]
    assert event["date_from"] == "2026-09-10"
    assert event["date_to"] == "2026-09-11"


def test_cancelled_status_is_flagged():
    ics = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART;VALUE=DATE:20260910\nDTEND;VALUE=DATE:20260912\n"
        "UID:cancelled@airbnb.com\nSUMMARY:Reserved\nSTATUS:CANCELLED\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    event = icalsync.parse_events(ics)[0]
    assert event["is_cancelled"] is True


def test_platform_detection_for_major_otas():
    assert icalsync.platform_of("https://www.airbnb.com/calendar/ical/abc.ics") == "airbnb"
    assert icalsync.platform_of("https://admin.booking.com/hotel/ical/abc") == "booking"
    assert icalsync.platform_of("https://ycs.agoda.com/ical/abc.ics") == "agoda"
    assert icalsync.platform_of("https://www.vrbo.com/ical/abc") == "vrbo"
    assert icalsync.platform_of("https://unknown.example/feed.ics") == "ical"


def test_event_without_uid_gets_a_stable_synthetic_one():
    ics = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART;VALUE=DATE:20260910\nDTEND;VALUE=DATE:20260912\nSUMMARY:Reserved\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    first = icalsync.parse_events(ics)[0]["uid"]
    second = icalsync.parse_events(ics)[0]["uid"]
    assert first == second
    assert first.startswith("synthetic-")


def test_empty_calendar_does_not_mass_cancel_future_stays(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "empty-feed.sqlite3")
    db.init_db()
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Empty feed test",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    feed_id = db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": "https://calendar.example/empty.ics",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "ical_feed_id": feed_id,
            "uid": "must-survive",
            "date_from": "2099-01-10",
            "date_to": "2099-01-12",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    monkeypatch.setattr(
        icalsync,
        "fetch_feed",
        lambda _url: "BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n",
    )

    stats = icalsync.sync_feed(
        db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))
    )

    assert stats["cancelled"] == 0
    assert db.query_one(
        "SELECT status FROM reservation WHERE id = ?", (reservation_id,)
    )["status"] == "active"
