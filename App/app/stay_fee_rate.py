"""Dated stay-fee rates (brief 1027).

A counted night is priced at the rate with the latest ``effective_from`` on or
before that night. An apartment with no history rows uses its flat column rate.
Imports only ``db`` and the standard library: ``stay_fee`` imports this module.
"""
from __future__ import annotations

from datetime import date
from typing import Any, List, Optional, Tuple

from . import db

EPOCH = "2000-01-01"

Schedule = List[Tuple[date, int]]


def flat(rate: Any) -> Schedule:
    """A schedule with one rate for every night (host override or no history)."""
    return [(date.min, int(rate))]


def schedule_for(apartment: Any, today: Optional[date] = None) -> Schedule:
    """The apartment's rate schedule, sorted by effective date."""
    column = int(apartment["stay_fee_rate_czk"] or 0)
    try:
        apartment_id = apartment["id"]
    except (KeyError, IndexError):
        apartment_id = None
    if apartment_id is None:
        return flat(column)  # not saved yet: no history can exist
    rows = db.query(
        "SELECT effective_from, rate_czk FROM stay_fee_rate "
        "WHERE apartment_id = ? ORDER BY effective_from",
        (apartment_id,),
    )
    if not rows:
        return flat(column)
    schedule: Schedule = [
        (date.fromisoformat(row["effective_from"]), int(row["rate_czk"])) for row in rows
    ]
    if schedule[-1][1] != column:
        # The column moved without a history row (a save path forgot to record).
        schedule.append((today or date.today(), column))
    return schedule


def rate_on(schedule: Schedule, day: date) -> int:
    """The rate in force on ``day``: the last entry dated on or before it."""
    rate = schedule[0][1]
    for start, value in schedule:
        if start <= day:
            rate = value
        else:
            break
    return rate


def is_uniform(schedule: Schedule, first: date, last: date) -> bool:
    """True when every night from ``first`` to ``last`` has the same rate."""
    rates = {rate_on(schedule, first), rate_on(schedule, last)}
    for start, _ in schedule:
        if first < start <= last:
            rates.add(rate_on(schedule, start))
    return len(rates) == 1


def _rows_schedule(apartment_id: int) -> Schedule:
    rows = db.query(
        "SELECT effective_from, rate_czk FROM stay_fee_rate "
        "WHERE apartment_id = ? ORDER BY effective_from",
        (apartment_id,),
    )
    return [(date.fromisoformat(row["effective_from"]), int(row["rate_czk"])) for row in rows]


def record(apartment_id: int, rate: int, effective_from: date,
           *, previous: Optional[int] = None, today: Optional[date] = None) -> bool:
    """Store a rate effective from ``effective_from`` (never in the past).

    Returns True when a dated row was added or changed, False when the rate in
    force on that day already equals ``rate``. A same-date row with another
    rate is updated in place.

    An apartment with no history first gets a baseline row at EPOCH so earlier
    nights keep the rate they had: ``previous`` (the column value before the
    save), else the current column. A baseline of 0 means no fee was set up,
    so the first rate ever applies from the beginning, as the flat rate did.
    """
    today = today or date.today()
    if effective_from < today:
        raise ValueError("past")
    apartment = db.query_one(
        "SELECT id, stay_fee_rate_czk FROM apartment WHERE id = ?", (apartment_id,))
    if apartment is None:
        raise ValueError("no apartment")
    schedule = _rows_schedule(apartment_id)
    if not schedule:
        base = int(apartment["stay_fee_rate_czk"] or 0) if previous is None else int(previous)
        base = base if base > 0 else int(rate)
        if base <= 0:
            return False  # no fee set up and none being set: nothing to date
        db.execute(
            "INSERT INTO stay_fee_rate (apartment_id, rate_czk, effective_from, created_at) "
            "VALUES (?, ?, ?, ?)",
            (apartment_id, base, EPOCH, db.utcnow()),
        )
        schedule = [(date.fromisoformat(EPOCH), base)]
    if rate_on(schedule, effective_from) == int(rate):
        return False
    db.execute(
        "INSERT INTO stay_fee_rate (apartment_id, rate_czk, effective_from, created_at) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT (apartment_id, effective_from) DO UPDATE SET rate_czk = excluded.rate_czk",
        (apartment_id, int(rate), effective_from.isoformat(), db.utcnow()),
    )
    return True
