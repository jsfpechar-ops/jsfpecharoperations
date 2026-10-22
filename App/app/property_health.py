"""0244 (idea O): the property's health check on its overview.

One row per thing that can break today: calendar, guest link, police
reports, business details, and door codes when a lock is connected. A row
that is fine says so in a few words; a row that is not gets one button to
the exact setting. It reads only facts the property page already loads,
plus open alerts.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from . import db, needs_you, workflow

_LOGIN_KINDS = {"ubyport_auth_failed"}
_FEED_KINDS = {"feed_error", "feed_incomplete", "feed_duplicate_uid", "feed_recurring_event"}


def _row(key: str, icon: str, state: str, text_key: str, action_key: str = "", href: str = "") -> Dict[str, str]:
    return {
        "key": key,
        "icon": icon,
        "state": state,  # ok | warn | bad | off
        "label_key": f"health.{key}",
        "text_key": text_key,
        "action_key": action_key,
        "href": href,
    }


def _open_kinds(apartment_id: int) -> set:
    rows = db.query(
        "SELECT kind FROM alert WHERE apartment_id = ? AND resolved_at IS NULL",
        (apartment_id,),
    )
    return {row["kind"] for row in rows}


def checks(
    apartment,
    feeds: Iterable[Any],
    readiness: Optional[Dict[str, Any]],
    door_code: Optional[Dict[str, Any]],
    *,
    open_kinds: Optional[set] = None,
    guest_used: Optional[bool] = None,
    link_due: Optional[bool] = None,
) -> List[Dict[str, str]]:
    """The rows, in a fixed order. The keyword arguments let tests skip the database."""
    apartment_id = apartment["id"]
    base = f"/apartments/{apartment_id}"
    if open_kinds is None:
        open_kinds = _open_kinds(apartment_id)
    rows = []

    active = [feed for feed in feeds or [] if feed["active"]]
    calendar_href = f"{base}?view=bookings#calendars"
    if any(feed["last_status"] == "error" for feed in active) or open_kinds & _FEED_KINDS:
        rows.append(_row("calendar", "calendar-days", "bad", "health.calendar.error", "health.calendar.fix", calendar_href))
    elif not active:
        rows.append(_row("calendar", "calendar-days", "warn", "health.calendar.none", "health.calendar.connect", calendar_href))
    else:
        rows.append(_row("calendar", "calendar-days", "ok", "health.calendar.ok"))

    if guest_used is None:
        guest_used = workflow.guest_used_link(apartment_id)
    if guest_used:
        rows.append(_row("guest_link", "external-link", "ok", "health.guest_link.ok"))
    else:
        if link_due is None:
            link_due = bool(workflow.link_unused([apartment]))
        if link_due:
            rows.append(_row(
                "guest_link", "external-link", "warn", "health.guest_link.unused", "health.guest_link.fix",
                f"{base}?view=settings&section=guests#communication",
            ))
        else:
            rows.append(_row("guest_link", "external-link", "off", "health.guest_link.waiting"))

    missing = [item for item in (readiness or {}).get("report", []) if not item["done"]]
    if open_kinds & _LOGIN_KINDS:
        rows.append(_row(
            "police", "send", "bad", "health.police.login", "health.police.fix_login",
            f"{base}?view=settings&section=reporting#ubyport",
        ))
    elif missing:
        anchor = missing[0]["anchor"]
        query = needs_you._SETUP_QUERY.get(anchor, "view=settings")
        rows.append(_row("police", "send", "bad", "health.police.missing", "health.police.fix", f"{base}?{query}#{anchor}"))
    else:
        rows.append(_row("police", "send", "ok", "health.police.ok"))

    business = [
        item for item in (readiness or {}).get("invite", [])
        if item["key"] in ("operator", "controller") and not item["done"]
    ]
    if business or "controller_missing" in open_kinds:
        rows.append(_row(
            "business", "receipt", "bad", "health.business.missing", "health.business.fix",
            f"{base}?view=settings&section=property#operator-picker",
        ))
    else:
        rows.append(_row("business", "receipt", "ok", "health.business.ok"))

    if door_code is not None:
        if door_code.get("enabled"):
            rows.append(_row("door", "key-round", "ok", "health.door.ok"))
        else:
            rows.append(_row("door", "key-round", "off", "health.door.off"))
    return rows


def to_fix(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    """Rows that need the host: a red or amber row with a button."""
    return [row for row in rows if row["state"] in ("bad", "warn")]
