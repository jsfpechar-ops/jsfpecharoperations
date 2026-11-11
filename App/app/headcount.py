"""The one writer of ``reservation.declared_guests`` for guest requests (1092).

A guest may never set the count below the stay's live guest rows (registered
or started; never below 1) or above ``MAX_GUESTS``. Every write runs under
``db.lock_key(cur, "reservation", id)`` inside ``db.immediate()``, so a count
change and a new guest row (``/save``) cannot pass each other.

Inside the block every read and write uses the block's cursor: a ``db.*``
helper there would open a second connection (see ``db._helper_conn``). The
audit row and the submit call therefore run after the block has committed,
and no UbyPort call is ever made inside it (UBYPORT_CORE).
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from . import config, db, reporting

MAX_GUESTS = 60
MAX_LEAD_CHANGES = 6
PRAGUE = ZoneInfo("Europe/Prague")
# Cut-off hour (Europe/Prague) on arrival day when the flat has no check-in hour. 0 = midnight at the start of the day. Owner decision pending (15 is the other choice): change only this number.
NO_HOUR_CUTOFF_HOUR = 0

SAVED = "saved"
UNCHANGED = "unchanged"
HOST_SET = "host_set"
STAY_GONE = "stay_gone"
OUT_OF_RANGE = "out_of_range"
ABOVE_CEILING = "above_ceiling"
BELOW_FLOOR = "below_floor"
# 1095: the lead guest's reduction.
AFTER_CUTOFF = "after_cutoff"
LOWERED = "lowered"
RESTORED = "restored"
STALE = "stale"
TOO_MANY = "too_many"
FEATURE_OFF = "feature_off"

# The codes a guest request may treat as "nothing to complain about".
ACCEPTED = frozenset({SAVED, UNCHANGED, HOST_SET})


def _utcnow() -> datetime:
    """The one clock of the cut-off (tests replace it)."""
    return datetime.now(timezone.utc)


def lead_cutoff(date_from, checkin_hour) -> Optional[datetime]:
    """Until when a lead may lower the count: check-in time on arrival day, Prague.

    None when it cannot be worked out; the caller then refuses lowering.
    """
    try:
        hour = int(checkin_hour) if checkin_hour not in (None, "") else NO_HOUR_CUTOFF_HOUR
        return datetime.combine(date.fromisoformat(str(date_from)[:10]), time(hour), PRAGUE)
    except (ValueError, TypeError):
        return None


def _cutoff_passed(date_from, checkin_hour, now: datetime) -> bool:
    cutoff = lead_cutoff(date_from, checkin_hour)
    return cutoff is None or now >= cutoff


def live_guest_rows(cur, reservation_id: int) -> int:
    """The floor: guest rows not archived, started ones included (the admin rule)."""
    cur.execute(
        "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ? AND archived_at IS NULL",
        (reservation_id,),
    )
    return int(cur.fetchall()[0][0] or 0)


def apply_declared_in(cur, reservation_id: int, count: int) -> Tuple[str, Optional[int]]:
    """Set the declared count on an open ``db.immediate()`` cursor: (code, old).

    Takes the reservation key; the caller must take no other ``lock_key``.
    Anything but ``saved`` leaves the stored number as it was.
    """
    db.lock_key(cur, "reservation", reservation_id)
    cur.execute(
        "SELECT r.status, r.archived_at, r.expected_guests_override, r.declared_guests, "
        "r.date_from, r.lead_reduced_guests, a.checkin_hour "
        "FROM reservation r LEFT JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (reservation_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return STAY_GONE, None
    row = rows[0]
    old = row["declared_guests"]
    if row["status"] != "active" or row["archived_at"]:
        return STAY_GONE, old
    if row["expected_guests_override"]:
        return HOST_SET, old
    if count < 1:
        return OUT_OF_RANGE, old
    if count > MAX_GUESTS:
        return ABOVE_CEILING, old
    if old is not None and int(old) == count:
        return UNCHANGED, old
    if row["lead_reduced_guests"] and count == row["lead_reduced_guests"]:
        return UNCHANGED, old
    if count < max(1, live_guest_rows(cur, reservation_id)):
        return BELOW_FLOOR, old
    if (
        config.HEADCOUNT_LEAD_LIVE
        and old is not None
        and count < reporting.expected_guest_count(row)
        and _cutoff_passed(row["date_from"], row["checkin_hour"], _utcnow())
    ):
        return AFTER_CUTOFF, old
    payload = {"declared_guests": count, "updated_at": db.utcnow()}
    if row["lead_reduced_guests"] is not None:
        # The base changed, so the lead's reduction no longer describes it.
        payload["lead_reduced_guests"] = None
        payload["lead_reduced_from"] = None
        payload["lead_reduced_at"] = None
    db.update_in(cur, "reservation", reservation_id, payload)
    return SAVED, old


def record(
    reservation_id: int,
    code: str,
    old: Optional[int],
    count: int,
    *,
    source: str,
    owner_user_id: Optional[int],
) -> None:
    """The audit row of one write or one floor refusal. Call after the commit.

    Numbers and the fixed source word only: no personal data.
    """
    if code == SAVED:
        action = "reservation_declared_guests_set"
    elif code == BELOW_FLOOR:
        action = "reservation_declared_guests_refused"
    else:
        return
    db.audit(
        action,
        f"id={int(reservation_id)} from={old} to={int(count)} source={source}",
        actor="guest",
        owner_user_id=owner_user_id,
    )


def set_declared_guests(
    reservation_id: int, count: int, *, source: str, owner_user_id: Optional[int]
) -> str:
    """Write the count under the lock, then audit and (on ``saved``) try to file."""
    with db.immediate() as cur:
        code, old = apply_declared_in(cur, reservation_id, count)
        apartment_id = None
        if code == SAVED:
            cur.execute("SELECT apartment_id FROM reservation WHERE id = ?", (reservation_id,))
            apartment_id = cur.fetchall()[0][0]
    record(reservation_id, code, old, count, source=source, owner_user_id=owner_user_id)
    if code == SAVED:
        reporting.submit_stay_if_complete(apartment_id, reservation_id)
    return code


def change_by_lead_in(
    cur, reservation_id: int, count: int, shown: int, now: datetime
) -> Tuple[str, Optional[int]]:
    """Lower or restore the lead's reduction on an open block: (code, old expected).

    Takes the reservation key and no other. Writes only ``lead_reduced_*``:
    never the declared count, the host's count, a filing stamp or a guest row.
    A raise back towards the base passes the cut-off and the cap, so a real
    person can always be added back and registered.
    """
    db.lock_key(cur, "reservation", reservation_id)
    cur.execute(
        "SELECT r.status, r.archived_at, r.expected_guests_override, r.declared_guests, "
        "r.date_from, r.lead_reduced_guests, a.checkin_hour, "
        "r.apartment_id, r.lead_reduced_from, r.lead_reduced_changes "
        "FROM reservation r LEFT JOIN apartment a ON a.id = r.apartment_id WHERE r.id = ?",
        (reservation_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return STAY_GONE, None
    row = rows[0]
    current = reporting.expected_guest_count(row)
    if row["status"] != "active" or row["archived_at"]:
        return STAY_GONE, current
    if current is None or count < 1:
        return OUT_OF_RANGE, current
    current = int(current)
    if count == current:
        return UNCHANGED, current
    if shown != current:
        return STALE, current
    base = row["expected_guests_override"] or row["declared_guests"]
    base = int(base) if base is not None else current
    if count > base:
        return ABOVE_CEILING, current
    if count < max(1, live_guest_rows(cur, reservation_id)):
        return BELOW_FLOOR, current
    changes = int(row["lead_reduced_changes"] or 0)
    if count < current:
        if _cutoff_passed(row["date_from"], row["checkin_hour"], now):
            return AFTER_CUTOFF, current
        if changes >= MAX_LEAD_CHANGES:
            return TOO_MANY, current
    stamp = db.utcnow()
    if count == base:
        payload = {"lead_reduced_guests": None, "lead_reduced_from": None, "lead_reduced_at": None}
    else:
        payload = {"lead_reduced_guests": count, "lead_reduced_from": base, "lead_reduced_at": stamp}
    payload["lead_reduced_changes"] = changes + 1
    payload["updated_at"] = stamp
    db.update_in(cur, "reservation", reservation_id, payload)
    return (LOWERED if count < current else RESTORED), current


def change_by_lead(
    reservation_id: int,
    count: int,
    shown: int,
    *,
    owner_user_id: Optional[int],
    now: Optional[datetime] = None,
) -> str:
    """The one lead change: write under the lock, then audit and the completion calls."""
    if not config.HEADCOUNT_LEAD_LIVE:
        return FEATURE_OFF
    if now is None:
        now = _utcnow()
    with db.immediate() as cur:
        code, old = change_by_lead_in(cur, reservation_id, count, shown, now)
        apartment_id = None
        if code in (LOWERED, RESTORED):
            cur.execute("SELECT apartment_id FROM reservation WHERE id = ?", (reservation_id,))
            apartment_id = cur.fetchall()[0][0]
    if code not in (LOWERED, RESTORED):
        return code
    db.audit(
        "reservation_headcount_lowered" if code == LOWERED else "reservation_headcount_restored",
        f"id={int(reservation_id)} from={old} to={int(count)} source=lead",
        actor="guest",
        owner_user_id=owner_user_id,
    )
    # claim imports this module, so these two are imported here.
    from . import claim, door_codes

    reporting.submit_stay_if_complete(apartment_id, reservation_id)
    door_codes.on_registration_complete(reservation_id)
    fresh = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    apartment = db.query_one("SELECT * FROM apartment WHERE id = ?", (apartment_id,))
    if fresh and apartment:
        claim.maybe_notify_completion(fresh, apartment)
    return code
