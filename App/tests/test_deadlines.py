from datetime import date, datetime, timezone

from app import deadlines as d


def test_easter_sunday_known_years():
    assert d.easter_sunday(2024) == date(2024, 3, 31)
    assert d.easter_sunday(2025) == date(2025, 4, 20)
    assert d.easter_sunday(2026) == date(2026, 4, 5)


def test_czech_public_holidays():
    holidays = d.public_holidays(2026)
    assert date(2026, 1, 1) in holidays
    assert date(2026, 7, 5) in holidays
    assert date(2026, 11, 17) in holidays
    assert date(2026, 12, 26) in holidays
    # Easter Monday 2026 follows Easter Sunday on 5 April.
    assert date(2026, 4, 6) in holidays
    # Good Friday.
    assert date(2026, 4, 3) in holidays


def test_good_friday_only_from_2016():
    assert d.easter_sunday(2015) - __import__("datetime").timedelta(days=2) not in d.public_holidays(2015)
    assert d.easter_sunday(2016) - __import__("datetime").timedelta(days=2) in d.public_holidays(2016)


def test_weekends_are_not_working_days():
    assert not d.is_working_day(date(2026, 9, 12))  # Saturday
    assert not d.is_working_day(date(2026, 9, 13))  # Sunday
    assert d.is_working_day(date(2026, 9, 14))      # Monday


def test_working_day_arithmetic_skips_weekend():
    # Thursday 10 Sep 2026 is itself the first working day, so the third is
    # Monday 14 Sep. Counting the arrival day is decision D3.
    assert d.add_working_days(date(2026, 9, 10), 3) == date(2026, 9, 14)


def test_working_day_arithmetic_skips_public_holiday():
    # 17 Nov 2026 is a public holiday (a Tuesday), so it does not count.
    assert d.add_working_days(date(2026, 11, 16), 3) == date(2026, 11, 19)


def test_a_weekend_arrival_opens_the_count_on_the_next_working_day():
    # Saturday 12 Sep 2026 cannot be a working day, so the window runs
    # Monday 14, Tuesday 15, Wednesday 16.
    assert d.add_working_days(date(2026, 9, 12), 3) == date(2026, 9, 16)


def test_deadline_is_end_of_the_third_working_day():
    deadline = d.reporting_deadline(date(2026, 9, 10))
    assert deadline == datetime(2026, 9, 14, 23, 59, 59)


def test_a_monday_check_in_files_by_wednesday():
    """The plan's example for D3: Monday + three working days = Wednesday."""
    assert d.reporting_deadline(date(2026, 9, 14)) == datetime(2026, 9, 16, 23, 59, 59)


def test_aware_instants_are_compared_in_czech_civil_time_across_dst():
    check_in = date(2026, 3, 26)
    assert d.reporting_deadline(check_in) == datetime(2026, 3, 30, 23, 59, 59)
    assert d.hours_left(
        check_in, datetime(2026, 3, 30, 21, 0, tzinfo=timezone.utc)
    ) > 0
    assert d.urgency(
        check_in, datetime(2026, 3, 30, 22, 0, tzinfo=timezone.utc)
    ) == "overdue"


def test_urgency_buckets():
    check_in = date(2026, 9, 10)
    assert d.urgency(check_in, datetime(2026, 9, 9, 12, 0)) == "future"
    assert d.urgency(check_in, datetime(2026, 9, 10, 12, 0)) == "ok"
    assert d.urgency(check_in, datetime(2026, 9, 13, 12, 0)) == "soon"
    assert d.urgency(check_in, datetime(2026, 9, 14, 12, 0)) == "urgent"
    assert d.urgency(check_in, datetime(2026, 9, 15, 12, 0)) == "overdue"


def test_urgency_order_puts_overdue_first():
    order = sorted(["ok", "overdue", "future", "urgent", "soon"], key=d.URGENCY_ORDER.get)
    assert order == ["overdue", "urgent", "soon", "ok", "future"]


def test_describe_time_left_reads_naturally():
    assert "left" in d.describe_time_left(date(2026, 9, 10), datetime(2026, 9, 14, 12, 0))
    assert "overdue" in d.describe_time_left(date(2026, 9, 10), datetime(2026, 9, 17, 12, 0))
    assert "arrives in" in d.describe_time_left(date(2026, 9, 20), datetime(2026, 9, 15, 12, 0))


def test_countdown_is_translated_for_a_czech_host():
    """The deadline is the most important text on the queue; it must not be
    the one English string left on a Czech page."""
    from app import host_i18n
    from app.deadlines import time_left_parts

    def render(kind, amount):
        key = f"deadline.{kind}"
        if kind in ("arrives_days", "days_left", "overdue_days"):
            if amount == 1:
                key += ".one"
            elif 2 <= amount <= 4:
                key += ".few"
        return host_i18n.translate("cs", key, n=amount)

    # Czech has three forms for "day": 1 den / 2-4 dny / 5+ dni.
    assert render("days_left", 1) == "zbývá 1 den"
    assert render("days_left", 3) == "zbývají 3 dny"
    assert render("days_left", 7) == "zbývá 7 dní"
    assert render("overdue_days", 1) == "po termínu o 1 den"
    assert render("overdue_days", 2) == "po termínu o 2 dny"
    assert render("arrives_days", 5) == "přijíždí za 5 dní"
    assert render("hours_left", 12) == "zbývá 12 h"
    assert render("overdue_hours", 6) == "po termínu o 6 h"

    # No key may fall through to its own name.
    for kind in ("arrives_days", "days_left", "overdue_days", "hours_left", "overdue_hours"):
        for amount in (1, 3, 9):
            for lang in ("en", "cs"):
                key = f"deadline.{kind}"
                if kind in ("arrives_days", "days_left", "overdue_days"):
                    if amount == 1:
                        key += ".one"
                    elif 2 <= amount <= 4:
                        key += ".few"
                assert host_i18n.translate(lang, key, n=amount) != key


def test_time_left_parts_matches_the_english_sentence():
    from datetime import datetime

    from app import deadlines

    check_in = date(2026, 6, 1)  # Monday
    now = datetime(2026, 6, 1, 12, 0)
    kind, amount = deadlines.time_left_parts(check_in, now)
    assert kind == "days_left"
    assert deadlines.describe_time_left(check_in, now) == f"{amount} days left"


def test_deadline_watch_uses_czech_time_and_keeps_old_compliance_debt(monkeypatch):
    from app import reporting

    captured = {}
    local = datetime(2026, 9, 15, 23, 0)
    monkeypatch.setattr(reporting.deadlines, "local_now", lambda _now: local)

    def query(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(reporting.db, "query", query)

    reporting.check_deadlines(datetime(2026, 9, 15, 21, 0, tzinfo=timezone.utc))

    assert "date_from >= ?" not in captured["sql"]
    assert captured["params"][-1] == "2026-09-15"


# --- the anchor the deadline actually runs from --------------------------

def _stay_with_guests(monkeypatch, tmp_path, name, *, date_from, date_to, guests):
    """One reservation plus guest rows carrying their own stay dates."""
    from app import config, db

    monkeypatch.setattr(config, "DB_PATH", tmp_path / name)
    db.init_db()
    now = db.utcnow()
    apartment_id = db.insert(
        "apartment",
        {
            "internal_name": "Anchor test",
            "automation_mode": "manual",
            "active": 1,
            "created_at": now,
        },
    )
    reservation_id = db.insert(
        "reservation",
        {
            "apartment_id": apartment_id,
            "uid": f"anchor-{name}",
            "date_from": date_from,
            "date_to": date_to,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
    )
    for index, (stay_from, stay_to, archived) in enumerate(guests):
        db.insert(
            "guest",
            {
                "reservation_id": reservation_id,
                "surname": f"Guest {index}",
                "first_name": "Test",
                "nationality": "DEU",
                "stay_from": stay_from,
                "stay_to": stay_to,
                "archived_at": archived,
                "created_at": now,
                "updated_at": now,
            },
        )
    return db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))


def test_a_guest_arriving_early_moves_the_deadline_and_the_urgency(monkeypatch, tmp_path):
    """The filed cFrom is the guest's arrival, so the clock starts there."""
    from app import reporting

    reservation = _stay_with_guests(
        monkeypatch,
        tmp_path,
        "anchor-earlier.sqlite3",
        date_from="2026-09-09",
        date_to="2026-09-14",
        guests=[("2026-09-04", "2026-09-12", None)],
    )

    anchor = reporting.reservation_deadline_anchor(reservation)

    assert anchor == date(2026, 9, 4)
    assert (date(2026, 9, 9) - anchor).days == 5
    assert d.reporting_deadline(anchor) == d.reporting_deadline(date(2026, 9, 4))
    assert d.reporting_deadline(anchor) < d.reporting_deadline(date(2026, 9, 9))

    # Wednesday 9 Sep, noon: still inside the window the reservation claims,
    # already past the one the guest's arrival sets.
    thursday = datetime(2026, 9, 9, 12, 0)
    assert d.urgency(date(2026, 9, 9), thursday) == "ok"
    assert d.urgency(anchor, thursday) == "overdue"


def test_a_stay_with_no_guest_dates_is_unchanged(monkeypatch, tmp_path):
    from app import reporting

    reservation = _stay_with_guests(
        monkeypatch,
        tmp_path,
        "anchor-none.sqlite3",
        date_from="2026-09-09",
        date_to="2026-09-14",
        guests=[],
    )

    assert reporting.reservation_deadline_anchor(reservation) == date(2026, 9, 9)


def test_a_guest_without_dates_falls_back_to_the_reservation(monkeypatch, tmp_path):
    from app import reporting

    reservation = _stay_with_guests(
        monkeypatch,
        tmp_path,
        "anchor-blank.sqlite3",
        date_from="2026-09-09",
        date_to="2026-09-14",
        guests=[(None, None, None), ("", "", None)],
    )

    assert reporting.reservation_deadline_anchor(reservation) == date(2026, 9, 9)


def test_the_earliest_guest_arrival_wins(monkeypatch, tmp_path):
    from app import reporting

    reservation = _stay_with_guests(
        monkeypatch,
        tmp_path,
        "anchor-earliest.sqlite3",
        date_from="2026-09-09",
        date_to="2026-09-14",
        guests=[
            ("2026-09-08", "2026-09-12", None),
            ("2026-09-06", "2026-09-12", None),
            ("2026-09-07", "2026-09-12", None),
        ],
    )

    assert reporting.reservation_deadline_anchor(reservation) == date(2026, 9, 6)


def test_an_archived_guest_does_not_pull_the_deadline_earlier(monkeypatch, tmp_path):
    from app import reporting

    reservation = _stay_with_guests(
        monkeypatch,
        tmp_path,
        "anchor-archived.sqlite3",
        date_from="2026-09-09",
        date_to="2026-09-14",
        guests=[
            ("2026-09-01", "2026-09-12", "2026-09-02T00:00:00Z"),
            ("2026-09-08", "2026-09-12", None),
        ],
    )

    assert reporting.reservation_deadline_anchor(reservation) == date(2026, 9, 8)


def test_the_deadline_alert_runs_from_the_guest_arrival(monkeypatch, tmp_path):
    """The dashboard and the alert must not disagree with the filed record."""
    from app import alerts, reporting

    _stay_with_guests(
        monkeypatch,
        tmp_path,
        "anchor-alert.sqlite3",
        date_from="2026-09-09",
        date_to="2026-09-14",
        guests=[("2026-09-07", "2026-09-12", None)],
    )
    monkeypatch.setattr(
        reporting.deadlines, "local_now", lambda _now=None: datetime(2026, 9, 12, 12, 0)
    )

    raised = reporting.check_deadlines(datetime(2026, 9, 12, 12, 0))

    assert raised == 1
    alert = alerts.open_alerts()
    assert len(alert) == 1
    assert alert[0]["level"] == "critical"
    assert "Po termínu o 2 dny" in alerts.present(alert[0], "cs")["display_detail"]
