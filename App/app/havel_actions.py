"""Confirm cards for Havel's actions (plan 7 and 17d).

The model proposes; this module checks the proposal against the host's data and
builds what the card shows and posts. The post goes to the existing route, which
checks everything again, so a card is never the only guard. Nothing here writes.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from . import config, guest_slug

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DAYS_BACK = 365
DAYS_AHEAD = 730


class NotPrepared(Exception):
    """The card cannot be built; ``reason`` is the tail of a ``havel.reason.*`` key."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _iso(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _in_window(day: date, today: date) -> bool:
    return today - timedelta(days=DAYS_BACK) <= day <= today + timedelta(days=DAYS_AHEAD)


def _property(action: Dict[str, Any], properties: List[Any]) -> Dict[str, Any]:
    pid = action.get("property_id")
    for index, row in enumerate(properties):
        if int(row["id"]) == pid:
            if not row["active"] or row["archived_at"]:
                raise NotPrepared("archived")
            return {"id": int(row["id"]), "name": row["internal_name"] or f"#{row['id']}", "index": index + 1,
                    "row": row}
    raise NotPrepared("property")


def prepare(action: Dict[str, Any], properties: List[Any], today: date, *, return_to: str,
            overlaps: Callable[[int, str, str], int], feed_count: Callable[[int], int]) -> Dict[str, Any]:
    """Card data for a validated action, or NotPrepared.

    ``properties`` are the host's apartment rows (``access.apartments(request, "*")``),
    in the order the host sees them (the identity dot uses that index).
    """
    kind = action["type"]
    if kind == "sync_calendars":
        if not any(feed_count(int(p["id"])) for p in properties if p["active"] and not p["archived_at"]):
            raise NotPrepared("no_calendar")
        return {"type": kind, "title": "havel.card.title_sync", "confirm": "havel.card.confirm_sync",
                "action": "/sync", "hidden": {"return_to": return_to}, "fields": [], "facts": [], "property": None}

    prop = _property(action, properties)
    if kind == "show_guest_link":
        key = guest_slug.link_key(prop["row"])
        if not key:
            raise NotPrepared("no_link")
        return {"type": kind, "title": "havel.card.title_link", "property": prop,
                "link": f"{config.PUBLIC_BASE_URL}/l/{key}", "pin": prop["row"]["permalink_pin"] or "",
                "guests_url": f"/apartments/{prop['id']}?view=settings&section=guests#communication"}

    if kind == "new_pin":
        return {"type": kind, "title": "havel.card.title_pin", "confirm": "havel.card.confirm_pin", "danger": True,
                "action": f"/apartments/{prop['id']}/regenerate-pin", "hidden": {}, "fields": [], "facts": [],
                "warning": "havel.card.pin_warning", "property": prop}

    start = _iso(action.get("date_from"))
    if not start or not _in_window(start, today):
        raise NotPrepared("dates")

    if kind == "create_cleaning":
        for name in ("start_time", "end_time"):
            if action.get(name) and not _HHMM.match(str(action[name])):
                raise NotPrepared("dates")
        if action.get("start_time") and action.get("end_time") and action["end_time"] <= action["start_time"]:
            raise NotPrepared("dates")
        return {"type": kind, "title": "havel.card.title_cleaning", "confirm": "havel.card.confirm_cleaning",
                "action": "/cleaning/events", "hidden": {"apartment_id": prop["id"]}, "property": prop,
                "date_from": start.isoformat(), "start_time": action.get("start_time") or "",
                "end_time": action.get("end_time") or "", "note": (action.get("note") or "")[:500],
                "fields": [
                    {"name": "scheduled_date", "label": ("cleaning", "date"), "type": "date", "value": start.isoformat()},
                    {"name": "start_time", "label": ("cleaning", "start"), "type": "time", "value": action.get("start_time") or ""},
                    {"name": "end_time", "label": ("cleaning", "end"), "type": "time", "value": action.get("end_time") or ""},
                    {"name": "notes", "label": ("cleaning", "notes"), "type": "text", "value": (action.get("note") or "")[:500]},
                ], "facts": []}

    # create_stay
    end = _iso(action.get("date_to"))
    if not end or end <= start or (end - start).days > 365:
        raise NotPrepared("dates")
    guests = action.get("guests")
    if guests is not None and not 1 <= int(guests) <= 60:
        raise NotPrepared("dates")
    email = (action.get("guest_email") or "").strip()
    if email and not _EMAIL.match(email):
        email = ""
    return {"type": kind, "title": "havel.card.title_stay", "confirm": "havel.card.confirm_stay",
            "action": "/reservations", "hidden": {"host_note": (action.get("note") or "")[:500]}, "property": prop,
            "date_from": start.isoformat(), "date_to": end.isoformat(), "nights": (end - start).days,
            "guests": guests, "guest_email": email,
            "overlap": overlaps(prop["id"], start.isoformat(), end.isoformat()) > 0,
            "fields": [
                {"name": "apartment_id", "label": ("host", "stays.add_panel.apartment"), "type": "select",
                 "value": prop["id"], "options": [(int(p["id"]), p["internal_name"] or f"#{p['id']}")
                                                  for p in properties if p["active"] and not p["archived_at"]]},
                {"name": "date_from", "label": ("host", "stays.add_panel.arrival"), "type": "date", "value": start.isoformat()},
                {"name": "date_to", "label": ("host", "stays.add_panel.departure"), "type": "date", "value": end.isoformat()},
                {"name": "expected_guests", "label": ("host", "stays.add_panel.guests"), "type": "number",
                 "value": guests or "", "min": 1, "max": 60},
                {"name": "guest_email", "label": ("host", "stays.add_panel.email"), "type": "email", "value": email},
            ], "facts": []}
