"""0230: the five-step story of a stay, told the same way on every host page.

1 you paste the guest message (once), 2 the guest fills the form, 3 you get an
email, 4 the police report goes out (by the property's own option), 5 the guest
gets the confirmation email (and the door code when a lock is connected).
Also: when a stay appears on the property's guest link, and whether a real
guest has used the link yet. Reads only data the app already stores.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from . import claim, db, validation

TOTAL = 5

# reporting.reservation_progress()["status"] -> the step the stay is on.
_STATUS_STEP = {
    "awaiting_guest": 2,
    "incomplete": 2,
    "ready": 4,
    "awaiting_verification": 4,
    "failed": 4,
    "reported": 5,
}

_POLICE_KEYS = {
    "manual": "police_manual",
    "scheduled": "police_scheduled",
    "immediate": "police_immediate",
}


def _get(row, key: str, default=None):
    if row is None:
        return default
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _as_dict(row) -> Dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def has_door_code(apartment) -> bool:
    """Step 5 names the door code only when a TTLock lock is set for the property."""
    if _get(apartment, "lock_provider") != "ttlock":
        return False
    from . import ttlock  # local: ttlock pulls in the HTTP client

    return bool(ttlock.enabled())


def steps(apartment=None) -> List[Dict[str, Any]]:
    """The five steps, worded for this property's police option and lock.

    Without a property (the first wizard screen) step 4 stays generic.
    """
    police = _POLICE_KEYS.get(_get(apartment, "automation_mode", ""), "police") if apartment is not None else "police"
    finish = "finish_lock" if apartment is not None and has_door_code(apartment) else "finish"
    return [
        {"n": 1, "key": "paste", "who": "you_once"},
        {"n": 2, "key": "form", "who": "auto"},
        {"n": 3, "key": "email", "who": "auto"},
        {"n": 4, "key": police, "who": "you" if police == "police_manual" else "auto"},
        {"n": 5, "key": finish, "who": "auto"},
    ]


def step_number(status) -> Optional[int]:
    """The step a stay with this reporting status is on, or None (not reported)."""
    return _STATUS_STEP.get(status or "")


def journey(reservation, progress) -> Optional[Dict[str, Any]]:
    """Where one stay is in the five steps, for the tracker on the stay page."""
    status = _get(progress, "status")
    current = step_number(status)
    if current is None or _get(reservation, "status", "active") != "active" or _get(reservation, "archived_at"):
        return None
    view = _as_dict(
        db.query_one("SELECT * FROM apartment WHERE id = ?", (_get(reservation, "apartment_id"),))
    )
    mode = _get(reservation, "automation_mode")
    if mode:
        view["automation_mode"] = mode
    complete = status == "reported"
    rows = []
    for step in steps(view or None):
        if complete or step["n"] < current:
            state = "done"
        elif step["n"] == current:
            state = "current"
        else:
            state = "todo"
        rows.append({**step, "state": state})
    return {
        "current": current,
        "total": TOTAL,
        "complete": complete,
        "failed": status == "failed",
        "steps": rows,
    }


def _window_days(row) -> int:
    days = _get(row, "permalink_window_days")
    if days is None and _get(row, "apartment_id") is not None:
        apartment = db.query_one(
            "SELECT permalink_window_days FROM apartment WHERE id = ?", (row["apartment_id"],)
        )
        days = _get(apartment, "permalink_window_days")
    return int(days or 1)


def link_window(reservation, today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """When this stay is listed on the property's guest link.

    {"state": "now"} while it is listed, {"state": "from", "opens": date} before,
    None for past, inactive, archived or demo stays. Same rule as
    routes/guest.py _visible_reservations: check-in from today to today + window.
    """
    if _get(reservation, "status", "active") != "active" or _get(reservation, "archived_at"):
        return None
    if _get(reservation, "source", "") == "demo":
        return None
    start = validation.parse_iso_date(_get(reservation, "date_from", ""))
    if not start:
        return None
    today = today or claim.prague_today()
    if start < today:
        return None
    opens = start - timedelta(days=_window_days(reservation))
    if opens <= today:
        return {"state": "now", "opens": today}
    return {"state": "from", "opens": opens}


def next_stay_window(apartment, today: Optional[date] = None) -> Dict[str, Any]:
    """The property's next real stay and the day it appears on the guest link."""
    today = today or claim.prague_today()
    days = _window_days(apartment)
    row = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND status = 'active' "
        "AND archived_at IS NULL AND COALESCE(source, '') != 'demo' AND date_from >= ? "
        "ORDER BY date_from LIMIT 1",
        (apartment["id"], today.isoformat()),
    )
    if row is None:
        return {"stay": None, "days": days, "window": None}
    stay = _as_dict(row)
    stay["permalink_window_days"] = days
    return {"stay": row, "days": days, "window": link_window(stay, today)}


def guest_used_link(apartment_id: int) -> bool:
    """0232: a real guest claimed a stay of this property (the only proof we store)."""
    row = db.query_one(
        "SELECT 1 AS hit FROM reservation r "
        "JOIN reservation_claim c ON c.reservation_id = r.id "
        "WHERE r.apartment_id = ? AND COALESCE(r.source, '') != 'demo' "
        "AND (c.state IN ('provisional', 'claimed') OR c.claimed_at IS NOT NULL) "
        "LIMIT 1",
        (apartment_id,),
    )
    return row is not None


def link_unused(apartments, today: Optional[date] = None) -> List[Any]:
    """Properties whose link a guest could have used by now, but no guest has.

    A stay must have reached the guest link since the property was added, so a
    new host is not nagged before any guest could have seen the message.
    """
    from . import demo  # local: demo imports many modules

    today = today or claim.prague_today()
    found = []
    for apartment in apartments or []:
        if not _get(apartment, "active", 1) or _get(apartment, "archived_at"):
            continue
        if not _get(apartment, "permalink_token") or demo.is_demo_apartment(apartment):
            continue
        added = str(_get(apartment, "created_at", ""))[:10] or "0000-00-00"
        horizon = (today + timedelta(days=_window_days(apartment))).isoformat()
        due = db.query_one(
            "SELECT 1 AS hit FROM reservation WHERE apartment_id = ? AND status = 'active' "
            "AND archived_at IS NULL AND COALESCE(source, '') != 'demo' "
            "AND date_from >= ? AND date_from <= ? LIMIT 1",
            (apartment["id"], added, horizon),
        )
        if due and not guest_used_link(apartment["id"]):
            found.append(apartment)
    return found
