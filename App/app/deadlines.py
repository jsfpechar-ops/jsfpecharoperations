"""The statutory three-working-day reporting deadline.

Section 100(c) of Act 326/1999 requires the host to notify the police of a
foreigner's accommodation within three working days of that accommodation
starting. Sorting the dashboard by how much of that window is left is what
turns a list of bookings into a list of things that actually need attention.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from . import config

REPORTING_WORKING_DAYS = 3


def is_working_day(day: date) -> bool:
    """Monday to Friday. Public holidays count as working days (decision 2026-10-31)."""
    return day.weekday() < 5


def add_working_days(start: date, count: int) -> date:
    """The date the `count`th working day of a window opening on `start` falls on.

    The day accommodation starts is the first working day when it is one, per
    decision D3: a Monday check-in gives a Wednesday deadline, not a Thursday
    one. A check-in on a weekend opens the count on the next
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
