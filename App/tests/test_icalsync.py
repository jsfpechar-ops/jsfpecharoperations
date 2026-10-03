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


def test_duration_is_used_when_dtend_is_missing():
    ics = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART;VALUE=DATE:20260910\nDURATION:P3D\nUID:duration@y\n"
        "SUMMARY:Reserved\nEND:VEVENT\nEND:VCALENDAR\n"
    )
    event = icalsync.parse_events(ics)[0]
    assert event["date_to"] == "2026-09-13"


def test_cancelled_status_is_flagged():
    ics = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART;VALUE=DATE:20260910\nDTEND;VALUE=DATE:20260912\n"
        "UID:cancelled@airbnb.com\nSUMMARY:Reserved\nSTATUS:CANCELLED\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    event = icalsync.parse_events(ics)[0]
    assert event["is_cancelled"] is True


def test_common_cancellation_variants_are_flagged():
    canceled = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART;VALUE=DATE:20260910\nUID:canceled@y\nSTATUS:CANCELED\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    method_cancel = canceled.replace(
        "VERSION:2.0", "VERSION:2.0\nMETHOD:CANCEL"
    ).replace("STATUS:CANCELED\n", "")

    assert icalsync.parse_events(canceled)[0]["is_cancelled"] is True
    assert icalsync.parse_events(method_cancel)[0]["is_cancelled"] is True


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


MOVED_STAY_FEED = (
    "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
    "DTSTART;VALUE=DATE:20990210\nDTEND;VALUE=DATE:20990212\n"
    "UID:moved-stay\nSUMMARY:Reserved\nEND:VEVENT\nEND:VCALENDAR\n"
)


def _moved_stay(
    tmp_path,
    monkeypatch,
    *,
    guest_stay_from="2099-01-10",
    guest_stay_to="2099-01-12",
    submit_state="pending",
):
    """One stay dated 2099-01-10..12 whose feed then reports it two months later."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "moved-feed.sqlite3")
    db.init_db()
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Moved feed test",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    feed_id = db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": "https://calendar.example/moved.ics",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "ical_feed_id": feed_id,
            "uid": "moved-stay",
            "date_from": "2099-01-10",
            "date_to": "2099-01-12",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "stay_from": guest_stay_from,
            "stay_to": guest_stay_to,
            "signature_png": "data:image/png;base64,signed",
            "signed_at": now,
            "entered_by": "guest",
            "submit_state": submit_state,
            "created_at": now,
            "updated_at": now,
        },
    )
    monkeypatch.setattr(icalsync, "fetch_feed", lambda _url: MOVED_STAY_FEED)
    return feed_id, reservation_id, guest_id


def _sync(feed_id):
    return icalsync.sync_feed(
        db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))
    )


def test_moved_ical_stay_keeps_the_signature_it_collected(monkeypatch, tmp_path):
    """D1 = keep, recorded as a test: the signature names the dates signed for."""
    feed_id, _reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)

    _sync(feed_id)

    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest["stay_from"] == "2099-02-10"
    assert guest["stay_to"] == "2099-02-12"
    assert guest["signature_png"] == "data:image/png;base64,signed"
    assert guest["signed_at"] is not None


def test_a_shrunk_booking_trims_an_unsent_guest_window(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "shrink-feed.sqlite3")
    db.init_db()
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {"internal_name": "Shrink feed test", "automation_mode": "manual", "active": 1, "created_at": now},
    )
    feed_id = db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": "https://calendar.example/shrink.ics",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "ical_feed_id": feed_id,
            "uid": "shrink-stay",
            "date_from": "2099-01-01",
            "date_to": "2099-01-10",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": reservation_id,
            "stay_from": "2099-01-03",
            "stay_to": "2099-01-08",
            "signature_png": "data:image/png;base64,signed",
            "signed_at": now,
            "submit_state": "pending",
            "created_at": now,
            "updated_at": now,
        },
    )
    shrunk = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART;VALUE=DATE:20990101\nDTEND;VALUE=DATE:20990105\n"
        "UID:shrink-stay\nSUMMARY:Reserved\nEND:VEVENT\nEND:VCALENDAR\n"
    )
    monkeypatch.setattr(icalsync, "fetch_feed", lambda _url: shrunk)
    icalsync.sync_feed(db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,)))
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest["stay_from"] == "2099-01-03"
    assert guest["stay_to"] == "2099-01-05"
    assert guest["signature_png"] == "data:image/png;base64,signed"


def test_a_filed_guest_is_not_moved_when_the_booking_changes(monkeypatch, tmp_path):
    feed_id, _reservation_id, guest_id = _moved_stay(
        tmp_path, monkeypatch, submit_state="sent"
    )
    before = db.query_one("SELECT stay_from, stay_to FROM guest WHERE id = ?", (guest_id,))
    _sync(feed_id)
    after = db.query_one("SELECT stay_from, stay_to FROM guest WHERE id = ?", (guest_id,))
    assert before == after


def test_moved_ical_stay_does_not_raise_a_resign_alert(monkeypatch, tmp_path):
    feed_id, reservation_id, _guest_id = _moved_stay(tmp_path, monkeypatch)

    _sync(feed_id)

    assert db.query_one(
        "SELECT * FROM alert WHERE dedupe_key = ?",
        (f"dates_changed_resign:{reservation_id}",),
    ) is None


def test_moved_ical_stay_leaves_a_guest_with_their_own_dates_alone(
    monkeypatch, tmp_path
):
    """A guest who legitimately leaves a day early keeps their own window."""
    feed_id, _reservation_id, guest_id = _moved_stay(
        tmp_path,
        monkeypatch,
        guest_stay_from="2099-01-10",
        guest_stay_to="2099-01-11",
    )

    _sync(feed_id)

    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest["stay_from"] == "2099-01-10"
    assert guest["stay_to"] == "2099-01-11"


# --- one bad feed must not stop every apartment --------------------------

def _feed_calendar(uids, *, start="2099-03-01", end="2099-03-05"):
    events = "".join(
        f"BEGIN:VEVENT\nDTSTART;VALUE=DATE:{start.replace('-', '')}\n"
        f"DTEND;VALUE=DATE:{end.replace('-', '')}\nUID:{uid}\n"
        f"SUMMARY:Reserved\nEND:VEVENT\n"
        for uid in uids
    )
    return f"BEGIN:VCALENDAR\nVERSION:2.0\n{events}END:VCALENDAR\n"


def _three_feeds(tmp_path, monkeypatch, name):
    """Three apartments, one feed each. Returns (feed_ids, url_by_id)."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / name)
    db.init_db()
    now = db.utcnow()
    feed_ids = []
    urls = {}
    for index in ("first", "middle", "third"):
        apartment_id = db.insert(
            "apartment",
            {
                "internal_name": f"{index} apartment",
                "automation_mode": "manual",
                "active": 1,
                "created_at": now,
            },
        )
        url = f"https://calendar.example/{index}.ics"
        urls[index] = url
        feed_ids.append(
            db.insert(
                "ical_feed",
                {
                    "apartment_id": apartment_id,
                    "url": url,
                    "active": 1,
                    "created_at": now,
                },
            )
        )
    return feed_ids, urls


def test_one_broken_feed_does_not_stop_the_others(monkeypatch, tmp_path):
    feed_ids, urls = _three_feeds(tmp_path, monkeypatch, "one-bad-feed.sqlite3")
    db.set_setting("last_ical_sync", "2000-01-01T00:00:00+00:00")

    def fetch(url):
        if url == urls["middle"]:
            raise AttributeError("'NoneType' object has no attribute 'text'")
        return _feed_calendar([f"stay-{url.rsplit('/', 1)[-1]}"])

    monkeypatch.setattr(icalsync, "fetch_feed", fetch)

    totals = icalsync.sync_all()

    assert totals["feeds"] == 3
    assert totals["errors"] == 1
    assert totals["created"] == 2

    first, middle, third = (
        db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))
        for feed_id in feed_ids
    )
    assert first["last_status"] == "ok"
    assert third["last_status"] == "ok"
    assert middle["last_status"] == "error"
    assert "has no attribute" in middle["last_error"]

    for feed in (first, third):
        assert db.query_one(
            "SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ?",
            (feed["apartment_id"],),
        )["n"] == 1
    assert db.query_one(
        "SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ?",
        (middle["apartment_id"],),
    )["n"] == 0

    # The whole pass still counts as done, so the host is not told the sync
    # never happened.
    assert db.get_setting("last_ical_sync") != "2000-01-01T00:00:00+00:00"


def test_a_feed_that_escapes_sync_feed_does_not_stop_the_others(monkeypatch, tmp_path):
    """Belt and braces: the failure is caught even outside sync_feed's own try."""
    feed_ids, urls = _three_feeds(tmp_path, monkeypatch, "escaped-feed.sqlite3")
    db.set_setting("last_ical_sync", "2000-01-01T00:00:00+00:00")
    real = icalsync.sync_feed
    middle_id = feed_ids[1]

    def flaky(feed):
        if feed["id"] == middle_id:
            raise AttributeError("sync_feed itself blew up")
        return real(feed)

    monkeypatch.setattr(icalsync, "fetch_feed", lambda url: _feed_calendar([url]))
    monkeypatch.setattr(icalsync, "sync_feed", flaky)

    totals = icalsync.sync_all()

    assert totals["feeds"] == 3
    assert totals["errors"] == 1
    assert totals["created"] == 2
    assert db.get_setting("last_ical_sync") != "2000-01-01T00:00:00+00:00"


# --- a feed returning a fraction of its stays must not mass-cancel --------

def _stored_stays(tmp_path, monkeypatch, name, *, stored, returned):
    """A feed holding ``stored`` future stays whose calendar now returns
    ``returned`` of them (the first N UIDs)."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / name)
    db.init_db()
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Ratio apartment",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    feed_id = db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": "https://calendar.example/ratio.ics",
            "active": 1,
            "created_at": now,
        },
    )
    uids = [f"ratio-{index}" for index in range(stored)]
    for uid in uids:
        db.insert(
            "reservation",
            {
                "apartment_id": apartment_id,
                "ical_feed_id": feed_id,
                "uid": uid,
                "date_from": "2099-03-01",
                "date_to": "2099-03-05",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )
    monkeypatch.setattr(
        icalsync, "fetch_feed", lambda _url: _feed_calendar(uids[:returned])
    )
    return feed_id, apartment_id, uids


def _active_count(apartment_id):
    return db.query_one(
        "SELECT COUNT(*) AS n FROM reservation WHERE apartment_id = ? AND status = 'active'",
        (apartment_id,),
    )["n"]


def test_a_feed_returning_a_fraction_of_its_stays_cancels_nothing(monkeypatch, tmp_path):
    from app import alerts

    feed_id, apartment_id, _uids = _stored_stays(
        tmp_path, monkeypatch, "ratio-fraction.sqlite3", stored=10, returned=1
    )

    stats = icalsync.sync_feed(
        db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))
    )

    assert stats["cancelled"] == 0
    assert _active_count(apartment_id) == 10
    feed = db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))
    assert feed["last_status"] == "suspect"
    assert feed["last_error"] is None

    open_alerts = alerts.open_alerts()
    assert len(open_alerts) == 1
    assert open_alerts[0]["kind"] == "feed_incomplete"
    assert open_alerts[0]["level"] == "warning"
    assert open_alerts[0]["dedupe_key"] == f"feed_incomplete:{feed_id}"
    assert open_alerts[0]["apartment_id"] == apartment_id


def test_a_feed_missing_one_of_ten_stays_cancels_only_that_one(monkeypatch, tmp_path):
    from app import alerts

    feed_id, apartment_id, uids = _stored_stays(
        tmp_path, monkeypatch, "ratio-missing-one.sqlite3", stored=10, returned=9
    )
    # A previous incomplete sync left its warning open; a trustworthy pass clears it.
    alerts.raise_alert(
        "warning",
        "feed_incomplete",
        "Calendar could not be trusted.",
        dedupe_key=f"feed_incomplete:{feed_id}",
        apartment_id=apartment_id,
    )

    stats = icalsync.sync_feed(
        db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))
    )

    assert stats["cancelled"] == 1
    assert _active_count(apartment_id) == 9
    gone = db.query_one(
        "SELECT status FROM reservation WHERE apartment_id = ? AND uid = ?",
        (apartment_id, uids[-1]),
    )
    assert gone["status"] == "cancelled"
    assert db.query_one(
        "SELECT last_status FROM ical_feed WHERE id = ?", (feed_id,)
    )["last_status"] == "ok"
    assert alerts.open_alerts() == []


def test_an_incomplete_feed_alert_is_refreshed_not_duplicated(monkeypatch, tmp_path):
    from app import alerts

    feed_id, _apartment_id, _uids = _stored_stays(
        tmp_path, monkeypatch, "ratio-refresh.sqlite3", stored=10, returned=1
    )
    feed = db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))

    icalsync.sync_feed(feed)
    icalsync.sync_feed(feed)

    assert len(alerts.open_alerts()) == 1


# --- Timezones ---------------------------------------------------------------
# Prague is UTC+1 in winter and UTC+2 in summer (CEST), so a UTC timestamp in
# the evening belongs to the next local day. Taking .date() off an aware
# datetime without converting used to store the previous day, which shifted a
# stay's arrival - and with it the three-working-day reporting deadline.


def _one_event(ics: str):
    events = icalsync.parse_events(ics)
    assert len(events) == 1, events
    return events[0]


def test_a_utc_evening_start_is_the_next_prague_day():
    # 20260910T230000Z is 2026-09-11 01:00 CEST.
    event = _one_event(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART:20260910T230000Z\n"
        "DTEND:20260912T100000Z\n"
        "UID:utc-evening@airbnb.com\n"
        "SUMMARY:Reserved\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    assert event["date_from"] == "2026-09-11"
    assert event["date_to"] == "2026-09-12"


def test_a_utc_midnight_start_is_the_same_prague_day():
    # 20260910T220000Z is 2026-09-11 00:00 CEST: the boundary itself.
    event = _one_event(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART:20260910T220000Z\n"
        "DTEND:20260911T100000Z\n"
        "UID:utc-midnight@airbnb.com\n"
        "SUMMARY:Reserved\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    assert event["date_from"] == "2026-09-11"


def test_a_utc_winter_evening_uses_the_winter_offset():
    # January is UTC+1, so 20260110T230000Z is 2026-01-11 00:00 CET.
    event = _one_event(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART:20260110T230000Z\n"
        "DTEND:20260112T100000Z\n"
        "UID:utc-winter@airbnb.com\n"
        "SUMMARY:Reserved\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    assert event["date_from"] == "2026-01-11"


def test_a_tzid_start_is_read_in_prague_time():
    event = _one_event(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART;TZID=Europe/Prague:20260910T140000\n"
        "DTEND;TZID=Europe/Prague:20260913T100000\n"
        "UID:tzid@booking.com\n"
        "SUMMARY:CLOSED - Not available\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    assert event["date_from"] == "2026-09-10"
    assert event["date_to"] == "2026-09-13"


def test_a_foreign_tzid_is_converted_to_prague():
    # 20260911T020000 in Tokyo is 2026-09-10 19:00 CEST.
    event = _one_event(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART;TZID=Asia/Tokyo:20260911T020000\n"
        "DTEND;TZID=Asia/Tokyo:20260912T020000\n"
        "UID:tokyo@agoda.com\n"
        "SUMMARY:Reserved\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    assert event["date_from"] == "2026-09-10"


def test_a_floating_start_is_taken_as_local_wall_clock():
    # No timezone at all: the feed means local time, so no conversion is right.
    event = _one_event(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART:20260910T140000\n"
        "DTEND:20260913T100000\n"
        "UID:floating@vrbo.com\n"
        "SUMMARY:Reserved\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    assert event["date_from"] == "2026-09-10"


def test_an_all_day_value_date_is_unchanged():
    # VALUE=DATE is a bare calendar day and must not be shifted by a timezone.
    event = _one_event(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART;VALUE=DATE:20260910\n"
        "DTEND;VALUE=DATE:20260913\n"
        "UID:allday@airbnb.com\n"
        "SUMMARY:Reserved\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    assert event["date_from"] == "2026-09-10"
    assert event["date_to"] == "2026-09-13"


def test_the_timezone_used_is_the_configured_one(monkeypatch):
    """The conversion follows config.TIMEZONE rather than a hard-coded zone."""
    monkeypatch.setattr(config, "TIMEZONE", "UTC")
    event = _one_event(
        "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\n"
        "DTSTART:20260910T230000Z\n"
        "DTEND:20260912T100000Z\n"
        "UID:tz-config@airbnb.com\n"
        "SUMMARY:Reserved\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    assert event["date_from"] == "2026-09-10"


# --- W4.6: UID and lifecycle holes [F5, F6, F7, F12, F13] -----------------

def _vevent(uid, start, end, summary="Reserved", extra=""):
    return (
        f"BEGIN:VEVENT\nDTSTART;VALUE=DATE:{start.replace('-', '')}\n"
        f"DTEND;VALUE=DATE:{end.replace('-', '')}\nUID:{uid}\n"
        f"SUMMARY:{summary}\n{extra}END:VEVENT\n"
    )


def _calendar(events, method=None):
    head = "BEGIN:VCALENDAR\nVERSION:2.0\n"
    if method:
        head += f"METHOD:{method}\n"
    return head + "".join(events) + "END:VCALENDAR\n"


def _feed_db(tmp_path, monkeypatch, name, ics):
    """A fresh database holding one apartment with one feed returning ``ics``."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / f"{name}.sqlite3")
    db.init_db()
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": f"{name} property",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    feed_id = db.insert(
        "ical_feed",
        {
            "apartment_id": apartment_id,
            "url": f"https://calendar.example/{name}.ics",
            "active": 1,
            "created_at": now,
        },
    )
    monkeypatch.setattr(icalsync, "fetch_feed", lambda _url: ics)
    return apartment_id, feed_id


def _sync_now(feed_id):
    return icalsync.sync_feed(
        db.query_one("SELECT * FROM ical_feed WHERE id = ?", (feed_id,))
    )


def _stays(apartment_id):
    return db.query("SELECT * FROM reservation WHERE apartment_id = ?", (apartment_id,))


def _alert(dedupe_key):
    return db.query_one("SELECT * FROM alert WHERE dedupe_key = ?", (dedupe_key,))


def _open_alert(dedupe_key):
    alert = _alert(dedupe_key)
    return alert if alert and alert["resolved_at"] is None else None


def test_a_duplicate_uid_is_reported_and_imported_once(monkeypatch, tmp_path):
    """[F6] Two events under one UID used to reconcile onto the same row."""
    first = _vevent("dup-1", "2099-05-01", "2099-05-03")
    second = _vevent("dup-1", "2099-05-08", "2099-05-10")
    apartment_id, feed_id = _feed_db(
        tmp_path, monkeypatch, "dupuid", _calendar([first, second])
    )

    _sync_now(feed_id)

    stays = _stays(apartment_id)
    assert len(stays) == 1
    assert stays[0]["date_from"] == "2099-05-01"  # the first occurrence wins
    alert = _open_alert(f"feed_duplicate_uid:{feed_id}")
    assert alert is not None
    assert alert["kind"] == "feed_duplicate_uid"
    assert alert["level"] == "warning"
    assert alert["apartment_id"] == apartment_id
    assert alert["message"] and alert["detail"]

    # Once the feed stops repeating itself the warning goes away.
    monkeypatch.setattr(icalsync, "fetch_feed", lambda _url: _calendar([first]))
    _sync_now(feed_id)
    assert _open_alert(f"feed_duplicate_uid:{feed_id}") is None


def test_a_uid_less_event_keeps_its_key_when_the_dates_move():
    """[F7] The old key embedded the dates, so a move looked like a new stay."""
    before = icalsync.parse_events(
        _calendar([_vevent("", "2099-05-01", "2099-05-03", summary="Anna")])
    )
    after = icalsync.parse_events(
        _calendar([_vevent("", "2099-06-01", "2099-06-03", summary="Anna")])
    )
    assert before[0]["uid"].startswith("synthetic-")
    assert before[0]["uid"] == after[0]["uid"]


def test_a_uid_less_event_keeps_the_guest_details_collected_against_it(
    monkeypatch, tmp_path
):
    apartment_id, feed_id = _feed_db(
        tmp_path,
        monkeypatch,
        "synthmove",
        _calendar([_vevent("", "2099-05-01", "2099-05-03", summary="Anna")]),
    )
    _sync_now(feed_id)
    stay = _stays(apartment_id)[0]
    now = db.utcnow()
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": stay["id"],
            "stay_from": "2099-05-01",
            "stay_to": "2099-05-03",
            "submit_state": "pending",
            "created_at": now,
            "updated_at": now,
        },
    )

    monkeypatch.setattr(
        icalsync,
        "fetch_feed",
        lambda _url: _calendar([_vevent("", "2099-06-01", "2099-06-03", summary="Anna")]),
    )
    stats = _sync_now(feed_id)

    stays = _stays(apartment_id)
    assert len(stays) == 1
    assert stays[0]["id"] == stay["id"]
    assert stays[0]["date_from"] == "2099-06-01"
    assert stats["created"] == 0 and stats["cancelled"] == 0
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    assert guest is not None and guest["reservation_id"] == stay["id"]


def test_a_row_keyed_by_the_old_synthetic_scheme_is_re_keyed_not_replaced(
    monkeypatch, tmp_path
):
    """The one-off upgrade path: W4.6 changed the synthetic key."""
    ics = _calendar([_vevent("", "2099-05-01", "2099-05-03", summary="Anna")])
    apartment_id, feed_id = _feed_db(tmp_path, monkeypatch, "legacyuid", ics)
    now = db.utcnow()
    legacy_uid = icalsync._legacy_synthetic_uid("2099-05-01", "2099-05-03", "Anna")
    stay_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "ical_feed_id": feed_id,
            "uid": legacy_uid,
            "date_from": "2099-05-01",
            "date_to": "2099-05-03",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )

    stats = _sync_now(feed_id)

    stays = _stays(apartment_id)
    assert len(stays) == 1
    assert stays[0]["id"] == stay_id
    assert stays[0]["uid"] == icalsync.parse_events(ics)[0]["uid"]
    assert stats["created"] == 0 and stats["cancelled"] == 0


def test_a_cancelled_stay_that_comes_back_reopens_guest_access(monkeypatch, tmp_path):
    """[F7] A revived stay used to reappear with a dead guest link."""
    live = _calendar([_vevent("revive-1", "2099-05-01", "2099-05-03")])
    apartment_id, feed_id = _feed_db(tmp_path, monkeypatch, "revive", live)
    _sync_now(feed_id)
    stay = _stays(apartment_id)[0]
    now = db.utcnow()
    db.insert(
        "reservation_claim",
        {
            "reservation_id": stay["id"],
            "state": "claimed",
            "token_hash": "claimed-token-hash",
            "claimed_at": now,
            "created_at": now,
            "updated_at": now,
        },
    )

    monkeypatch.setattr(
        icalsync,
        "fetch_feed",
        lambda _url: _calendar(
            [_vevent("revive-1", "2099-05-01", "2099-05-03")], method="CANCEL"
        ),
    )
    _sync_now(feed_id)
    cancelled = db.query_one("SELECT status FROM reservation WHERE id = ?", (stay["id"],))
    assert cancelled["status"] == "cancelled"
    locked = db.query_one(
        "SELECT * FROM reservation_claim WHERE reservation_id = ?", (stay["id"],)
    )
    assert locked["guest_access_locked_at"]
    assert locked["token_hash"] is None

    monkeypatch.setattr(icalsync, "fetch_feed", lambda _url: live)
    _sync_now(feed_id)

    revived = db.query_one("SELECT status FROM reservation WHERE id = ?", (stay["id"],))
    assert revived["status"] == "active"
    reopened = db.query_one(
        "SELECT * FROM reservation_claim WHERE reservation_id = ?", (stay["id"],)
    )
    assert reopened["guest_access_locked_at"] is None
    assert reopened["guest_access_reopened_at"]


def test_reopening_is_skipped_when_access_was_never_locked(monkeypatch, tmp_path):
    """The guard: claim.reopen_guest_access stamps the column unconditionally."""
    ics = _calendar([_vevent("unlocked-1", "2099-05-01", "2099-05-03")])
    apartment_id, feed_id = _feed_db(tmp_path, monkeypatch, "unlocked", ics)
    _sync_now(feed_id)
    stay = _stays(apartment_id)[0]
    now = db.utcnow()
    db.insert(
        "reservation_claim",
        {
            "reservation_id": stay["id"],
            "state": "unclaimed",
            "created_at": now,
            "updated_at": now,
        },
    )

    assert icalsync._reopen_guest_access(stay["id"]) is False

    claim = db.query_one(
        "SELECT * FROM reservation_claim WHERE reservation_id = ?", (stay["id"],)
    )
    assert claim["guest_access_locked_at"] is None
    assert claim["guest_access_reopened_at"] is None


def test_a_moved_stay_that_was_already_reported_warns_the_host(monkeypatch, tmp_path):
    """[F5] The filed record keeps the old dates; only the host can fix that."""
    feed_id, reservation_id, _guest_id = _moved_stay(
        tmp_path, monkeypatch, submit_state="sent"
    )

    _sync(feed_id)

    alert = _open_alert(f"moved_after_report:{reservation_id}")
    assert alert is not None
    assert alert["kind"] == "moved_after_report"
    assert alert["level"] == "warning"
    assert alert["reservation_id"] == reservation_id
    assert "2099-01-10" in alert["message"] and "2099-02-10" in alert["message"]
    assert alert["detail"]


def test_a_moved_stay_with_nothing_filed_does_not_warn_about_a_report(
    monkeypatch, tmp_path
):
    feed_id, reservation_id, _guest_id = _moved_stay(tmp_path, monkeypatch)

    _sync(feed_id)

    assert _open_alert(f"moved_after_report:{reservation_id}") is None
    assert _open_alert(f"dates_changed_resign:{reservation_id}") is None


def test_a_stay_that_now_looks_like_a_block_is_not_cancelled(monkeypatch, tmp_path):
    """[F13] The block wording is free text; it must not delete a real stay.

    Two other stays keep coming back, so the feed stays above the completeness
    threshold and the disappearance sweep really does run - which is what makes
    the kept stay's absence from ``seen_uids`` visible.
    """
    apartment_id, feed_id = _feed_db(
        tmp_path,
        monkeypatch,
        "blockrename",
        _calendar(
            [
                _vevent("keep-1", "2099-05-01", "2099-05-03"),
                _vevent("keep-2", "2099-05-10", "2099-05-12"),
                _vevent("renamed-1", "2099-05-20", "2099-05-22"),
            ]
        ),
    )
    _sync_now(feed_id)
    renamed = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND uid = ?",
        (apartment_id, "renamed-1"),
    )

    monkeypatch.setattr(
        icalsync,
        "fetch_feed",
        lambda _url: _calendar(
            [
                _vevent("keep-1", "2099-05-01", "2099-05-03"),
                _vevent("keep-2", "2099-05-10", "2099-05-12"),
                _vevent("renamed-1", "2099-05-20", "2099-05-22", summary="Blocked"),
            ]
        ),
    )
    stats = _sync_now(feed_id)

    kept = db.query_one("SELECT status FROM reservation WHERE id = ?", (renamed["id"],))
    assert kept["status"] == "active"
    assert stats["cancelled"] == 0
    assert stats["blocks_skipped"] == 1
    assert len(_stays(apartment_id)) == 3
    assert _open_alert(f"feed_incomplete:{feed_id}") is None


def test_a_block_with_no_stored_stay_is_still_skipped(monkeypatch, tmp_path):
    apartment_id, feed_id = _feed_db(
        tmp_path,
        monkeypatch,
        "blocknew",
        _calendar([_vevent("block-1", "2099-05-01", "2099-05-03", summary="Blocked")]),
    )

    stats = _sync_now(feed_id)

    assert stats["blocks_skipped"] == 1
    assert _stays(apartment_id) == []


def test_parse_events_flags_every_recurrence_property():
    for prop in (
        "RRULE:FREQ=WEEKLY;COUNT=3\n",
        "RDATE;VALUE=DATE:20990508\n",
        "EXDATE;VALUE=DATE:20990508\n",
    ):
        events = icalsync.parse_events(
            _calendar([_vevent("rec", "2099-05-01", "2099-05-03", extra=prop)])
        )
        assert events[0]["recurring"] is True, prop
    plain = icalsync.parse_events(_calendar([_vevent("plain", "2099-05-01", "2099-05-03")]))
    assert plain[0]["recurring"] is False


def test_a_repeating_booking_is_reported_and_imported_once(monkeypatch, tmp_path):
    """[F12] Only the first occurrence is imported, so the host must be told."""
    apartment_id, feed_id = _feed_db(
        tmp_path,
        monkeypatch,
        "recurring",
        _calendar(
            [
                _vevent(
                    "rec-1",
                    "2099-05-01",
                    "2099-05-03",
                    extra="RRULE:FREQ=WEEKLY;COUNT=3\nEXDATE;VALUE=DATE:20990508\n",
                )
            ]
        ),
    )

    _sync_now(feed_id)

    assert len(_stays(apartment_id)) == 1
    alert = _open_alert(f"feed_recurring_event:{feed_id}")
    assert alert is not None
    assert alert["kind"] == "feed_recurring_event"
    assert alert["level"] == "warning"
    assert alert["apartment_id"] == apartment_id


def test_a_repeating_block_does_not_warn(monkeypatch, tmp_path):
    """A weekly block is never imported anyway, so it is not a missing stay."""
    _apartment_id, feed_id = _feed_db(
        tmp_path,
        monkeypatch,
        "recurringblock",
        _calendar(
            [
                _vevent(
                    "rec-block",
                    "2099-05-01",
                    "2099-05-03",
                    summary="Blocked",
                    extra="RRULE:FREQ=WEEKLY\n",
                )
            ]
        ),
    )

    _sync_now(feed_id)

    assert _alert(f"feed_recurring_event:{feed_id}") is None


def test_two_unlabelled_bookings_with_the_same_words_stay_two_stays(
    monkeypatch, tmp_path
):
    """Our synthetic key colliding is not the feed repeating itself."""
    apartment_id, feed_id = _feed_db(
        tmp_path,
        monkeypatch,
        "syntheticcollision",
        _calendar(
            [
                _vevent("", "2099-05-01", "2099-05-03", summary="Reserved"),
                _vevent("", "2099-05-10", "2099-05-12", summary="Reserved"),
            ]
        ),
    )

    _sync_now(feed_id)

    stays = _stays(apartment_id)
    assert sorted(stay["date_from"] for stay in stays) == ["2099-05-01", "2099-05-10"]
    assert len({stay["uid"] for stay in stays}) == 2
    assert _alert(f"feed_duplicate_uid:{feed_id}") is None


def test_a_stay_that_vanishes_loses_its_guest_link(monkeypatch, tmp_path):
    """AR-27: a stay removed from the calendar must not keep a live guest link."""
    vanished_event = _vevent("vanish-1", "2099-05-01", "2099-05-03")
    kept_event = _vevent("keep-1", "2099-05-10", "2099-05-12")
    apartment_id, feed_id = _feed_db(
        tmp_path, monkeypatch, "vanishlink", _calendar([vanished_event, kept_event])
    )
    _sync_now(feed_id)
    vanished = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND uid = ?",
        (apartment_id, "vanish-1"),
    )
    now = db.utcnow()
    db.insert(
        "reservation_claim",
        {
            "reservation_id": vanished["id"],
            "state": "claimed",
            "token_hash": "claimed-token-hash",
            "claimed_at": now,
            "created_at": now,
            "updated_at": now,
        },
    )

    # One of two stored stays comes back, which clears the completeness bar, so
    # the disappearance sweep really runs and treats the missing stay as
    # cancelled upstream.
    monkeypatch.setattr(icalsync, "fetch_feed", lambda _url: _calendar([kept_event]))
    stats = _sync_now(feed_id)

    assert stats["cancelled"] == 1
    assert db.query_one(
        "SELECT status FROM reservation WHERE id = ?", (vanished["id"],)
    )["status"] == "cancelled"
    assert db.query_one(
        "SELECT token_hash FROM reservation_claim WHERE reservation_id = ?",
        (vanished["id"],),
    )["token_hash"] is None
