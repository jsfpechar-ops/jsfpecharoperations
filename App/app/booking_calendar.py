"""Booking site calendar grid (brief 0818, plan booking-site-v1).

Server-rendered month grids for the public page: no JavaScript. Every day is
a plain link that sets ?date_from= or ?date_to=; the page re-renders.
A "night" is the day it starts: 16 Dec taken means the night 16 to 17 Dec.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any, Dict, Optional, Set

from . import booking_site, db

HORIZON_MONTHS = 12


def parse_day(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def add_months(year: int, month: int, n: int) -> tuple:
    index = year * 12 + (month - 1) + n
    return index // 12, index % 12 + 1


def taken_nights(apartment_id: int, start: date, end: date) -> Set[str]:
    """ISO dates in [start, end) whose night is booked or held."""
    out: Set[str] = set()
    rows = list(db.query(
        "SELECT date_from, date_to FROM reservation WHERE apartment_id = ?"
        " AND status = 'active' AND date_from < ? AND date_to > ?",
        (apartment_id, end.isoformat(), start.isoformat()),
    )) + list(db.query(
        "SELECT date_from, date_to FROM booking_hold WHERE apartment_id = ?"
        " AND expires_at > ? AND date_from < ? AND date_to > ?",
        (apartment_id, db.utcnow(), end.isoformat(), start.isoformat()),
    ))
    for row in rows:
        day = max(date.fromisoformat(str(row["date_from"])[:10]), start)
        last = min(date.fromisoformat(str(row["date_to"])[:10]), end)
        while day < last:
            out.add(day.isoformat())
            day += timedelta(days=1)
    return out


def month_grid(apartment_id: int, year: int, month: int, *, date_from: str = "",
               date_to: str = "", today: Optional[date] = None) -> Dict[str, Any]:
    """{"year", "month", "weeks": [[cell] * 7], "prev": (y, m) | None, "next": ...}.

    cell = {"day": int, "iso": str, "state": pad | past | taken | free | start
    | range | end, "pick": (date_from, date_to) | None}. ``pick`` is what the
    link sets; None means the day is not clickable.
    """
    settings = booking_site.settings(apartment_id)
    today = today or booking_site._now(None).date()
    earliest = booking_site.earliest_check_in(settings)
    first = date(year, month, 1)
    sel_from = parse_day(date_from)
    sel_to = parse_day(date_to)
    if sel_from is None or (sel_to is not None and sel_to <= sel_from):
        sel_to = None
    if sel_from is None:
        sel_to = None
    low = min(first, sel_from) if sel_from else first
    taken = taken_nights(apartment_id, low, first + timedelta(days=62))

    def nights_free(a: date, b: date) -> bool:
        day = a
        while day < b:
            if day.isoformat() in taken:
                return False
            day += timedelta(days=1)
        return True

    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
        row = []
        for day in week:
            if day.month != month:
                row.append({"day": 0, "iso": "", "state": "pad", "pick": None})
                continue
            iso = day.isoformat()
            if day < earliest:
                state = "past"
            elif iso in taken:
                state = "taken"
            else:
                state = "free"
            pick = None
            if sel_from and sel_to is None and day > sel_from and nights_free(sel_from, day):
                pick = (sel_from.isoformat(), iso)
            elif state == "free":
                pick = (iso, "")
            if sel_from and iso == sel_from.isoformat():
                state = "start"
            elif sel_to and iso == sel_to.isoformat():
                state = "end"
            elif sel_from and sel_to and sel_from < day < sel_to:
                state = "range"
            row.append({"day": day.day, "iso": iso, "state": state, "pick": pick})
        weeks.append(row)
    this = (today.year, today.month)
    prev_ym = add_months(year, month, -1)
    next_ym = add_months(year, month, 1)
    last_ym = add_months(this[0], this[1], HORIZON_MONTHS)
    return {
        "year": year, "month": month, "weeks": weeks,
        "prev": prev_ym if prev_ym >= this else None,
        "next": next_ym if next_ym <= last_ym else None,
    }
