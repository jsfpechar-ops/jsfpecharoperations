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
    tmp_path, monkeypatch, *, guest_stay_from="2099-01-10", guest_stay_to="2099-01-12"
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
            "submit_state": "pending",
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


def test_moved_ical_stay_alerts_the_host(monkeypatch, tmp_path):
    feed_id, reservation_id, _guest_id = _moved_stay(tmp_path, monkeypatch)

    _sync(feed_id)

    alert = db.query_one(
        "SELECT * FROM alert WHERE dedupe_key = ?",
        (f"dates_changed_resign:{reservation_id}",),
    )
    assert alert is not None
    assert alert["kind"] == "dates_changed_resign"
    assert alert["level"] == "critical"
    assert alert["reservation_id"] == reservation_id
    assert alert["resolved_at"] is None
    assert alert["message"] and alert["detail"]


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
