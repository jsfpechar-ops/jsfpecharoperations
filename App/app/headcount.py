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

from typing import Optional, Tuple

from . import db, reporting

MAX_GUESTS = 60

SAVED = "saved"
UNCHANGED = "unchanged"
HOST_SET = "host_set"
STAY_GONE = "stay_gone"
OUT_OF_RANGE = "out_of_range"
ABOVE_CEILING = "above_ceiling"
BELOW_FLOOR = "below_floor"

# The codes a guest request may treat as "nothing to complain about".
ACCEPTED = frozenset({SAVED, UNCHANGED, HOST_SET})


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
        "SELECT status, archived_at, expected_guests_override, declared_guests "
        "FROM reservation WHERE id = ?",
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
    if count < max(1, live_guest_rows(cur, reservation_id)):
        return BELOW_FLOOR, old
    db.update_in(
        cur,
        "reservation",
        reservation_id,
        {"declared_guests": count, "updated_at": db.utcnow()},
    )
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
