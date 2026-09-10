from datetime import date, datetime

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
    # Thursday 10 Sep 2026 + 3 working days = Tuesday 15 Sep.
    assert d.add_working_days(date(2026, 9, 10), 3) == date(2026, 9, 15)


def test_working_day_arithmetic_skips_public_holiday():
    # 17 Nov 2026 is a public holiday (a Tuesday), so it does not count.
    assert d.add_working_days(date(2026, 11, 16), 3) == date(2026, 11, 20)


def test_deadline_is_end_of_the_third_working_day():
    deadline = d.reporting_deadline(date(2026, 9, 10))
    assert deadline == datetime(2026, 9, 15, 23, 59, 59)


def test_urgency_buckets():
    check_in = date(2026, 9, 10)
    assert d.urgency(check_in, datetime(2026, 9, 9, 12, 0)) == "future"
    assert d.urgency(check_in, datetime(2026, 9, 10, 12, 0)) == "ok"
    assert d.urgency(check_in, datetime(2026, 9, 14, 12, 0)) == "soon"
    assert d.urgency(check_in, datetime(2026, 9, 15, 12, 0)) == "urgent"
    assert d.urgency(check_in, datetime(2026, 9, 16, 12, 0)) == "overdue"


def test_urgency_order_puts_overdue_first():
    order = sorted(["ok", "overdue", "future", "urgent", "soon"], key=d.URGENCY_ORDER.get)
    assert order == ["overdue", "urgent", "soon", "ok", "future"]


def test_describe_time_left_reads_naturally():
    assert "left" in d.describe_time_left(date(2026, 9, 10), datetime(2026, 9, 15, 12, 0))
    assert "overdue" in d.describe_time_left(date(2026, 9, 10), datetime(2026, 9, 17, 12, 0))
    assert "arrives in" in d.describe_time_left(date(2026, 9, 20), datetime(2026, 9, 15, 12, 0))
