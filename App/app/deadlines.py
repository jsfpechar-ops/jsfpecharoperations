"""Czech public holidays and the statutory three-working-day reporting deadline.

Section 100(c) of Act 326/1999 requires the host to notify the police of a
foreigner's accommodation within three working days of that accommodation
starting. Sorting the dashboard by how much of that window is left is what
turns a list of bookings into a list of things that actually need attention.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Dict, Optional, Set
from zoneinfo import ZoneInfo

from . import config

REPORTING_WORKING_DAYS = 3


def easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def public_holidays(year: int) -> Dict[date, str]:
    """Czech public holidays (statni svatky and other days of rest)."""
    easter = easter_sunday(year)
    days = {
        date(year, 1, 1): "Den obnovy samostatného českého státu",
        easter - timedelta(days=2): "Velký pátek",
        easter + timedelta(days=1): "Velikonoční pondělí",
        date(year, 5, 1): "Svátek práce",
        date(year, 5, 8): "Den vítězství",
        date(year, 7, 5): "Den slovanských věrozvěstů Cyrila a Metoděje",
        date(year, 7, 6): "Den upálení mistra Jana Husa",
        date(year, 9, 28): "Den české státnosti",
        date(year, 10, 28): "Den vzniku samostatného československého státu",
        date(year, 11, 17): "Den boje za svobodu a demokracii",
        date(year, 12, 24): "Štědrý den",
        date(year, 12, 25): "1. svátek vánoční",
        date(year, 12, 26): "2. svátek vánoční",
    }
    # Good Friday only became a public holiday in 2016.
    if year < 2016:
        days.pop(easter - timedelta(days=2), None)
    return days


_HOLIDAY_CACHE: Dict[int, Set[date]] = {}


def holiday_set(year: int) -> Set[date]:
    if year not in _HOLIDAY_CACHE:
        _HOLIDAY_CACHE[year] = set(public_holidays(year))
    return _HOLIDAY_CACHE[year]


def is_working_day(day: date) -> bool:
    return day.weekday() < 5 and day not in holiday_set(day.year)


def add_working_days(start: date, count: int) -> date:
    """The date the `count`th working day of a window opening on `start` falls on.

    The day accommodation starts is the first working day when it is one, per
    decision D3: a Monday check-in gives a Wednesday deadline, not a Thursday
    one. A check-in on a weekend or a public holiday opens the count on the next
    working day, since a day that is not a working day cannot be counted.
    """
    current = start
    remaining = count - 1 if is_working_day(current) else count
    while remaining > 0:
        current += timedelta(days=1)
        if is_working_day(current):
            remaining -= 1
    return current


def reporting_deadline(check_in: date) -> datetime:
    """End of the third working day of the window that opens on arrival."""
    return datetime.combine(add_working_days(check_in, REPORTING_WORKING_DAYS), time(23, 59, 59))


def local_now(now: Optional[datetime] = None) -> datetime:
    """Return a naive Czech civil time for comparisons with stored stay dates."""
    if now is None:
        return datetime.now(ZoneInfo(config.TIMEZONE)).replace(tzinfo=None)
    if now.tzinfo is not None:
        return now.astimezone(ZoneInfo(config.TIMEZONE)).replace(tzinfo=None)
    return now


def hours_left(check_in: date, now: Optional[datetime] = None) -> float:
    now = local_now(now)
    return (reporting_deadline(check_in) - now).total_seconds() / 3600.0


def urgency(check_in: date, now: Optional[datetime] = None) -> str:
    """Bucket used for dashboard ordering and colour.

    "future"   - the stay has not started, nothing is due yet
    "ok"       - more than two days of the window remain
    "soon"     - inside the last two days
    "urgent"   - inside the last 24 hours
    "overdue"  - the deadline has passed
    """
    now = local_now(now)
    if check_in > now.date():
        return "future"
    left = hours_left(check_in, now)
    if left < 0:
        return "overdue"
    if left <= 24:
        return "urgent"
    if left <= 48:
        return "soon"
    return "ok"


URGENCY_ORDER = {"overdue": 0, "urgent": 1, "soon": 2, "ok": 3, "future": 4}


def time_left_parts(check_in: date, now: Optional[datetime] = None) -> tuple:
    """(kind, amount) for the deadline countdown, ready to be translated.

    The wording lives with the other UI strings; this module stays a pure
    calculation so the legal arithmetic can be read on its own.
    """
    now = local_now(now)
    if check_in > now.date():
        return "arrives_days", (check_in - now.date()).days
    left = hours_left(check_in, now)
    if left < 0:
        over = abs(left)
        if over < 48:
            return "overdue_hours", int(over)
        return "overdue_days", int(over // 24)
    if left < 48:
        return "hours_left", int(left)
    return "days_left", int(left // 24)


def describe_time_left(check_in: date, now: Optional[datetime] = None) -> str:
    """English countdown, for logs and stored alert text."""
    kind, amount = time_left_parts(check_in, now)
    if kind == "arrives_days":
        return f"arrives in {amount} day{'s' if amount != 1 else ''}"
    if kind == "overdue_hours":
        return f"overdue by {amount} h"
    if kind == "overdue_days":
        return f"overdue by {amount} days"
    if kind == "hours_left":
        return f"{amount} h left"
    return f"{amount} days left"
