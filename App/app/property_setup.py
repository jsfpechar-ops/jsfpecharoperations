"""0096: the guided setup of a new property, one step at a time.

Calendar -> Guest links -> Police reporting -> Stay fee (optional) -> Door lock
(optional, only where door codes exist) -> Automation.

No schema change: the state is one key in the existing ``settings`` key/value
table per property, ``property_setup:<id>``, holding JSON
``{"steps": {"<step>": "done" | "skipped"}, "finished": false}``. It holds no
personal data. The key is written when a property is created, so a property
made before 0096 (no key) never shows the guide, and one that is finished
never shows it again, whatever is edited later.

Some steps finish themselves from the real record (a calendar exists, police
details are complete, a fee rate or a lock is set); the others need the host's
own click ("Done", "Skip", "Keep manual sending" or a Settings save on that
step).
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from . import db

STEPS = ("calendar", "guest_links", "reporting", "fee", "lock", "automation")
OPTIONAL = frozenset({"fee", "lock"})
# The calendar has no "Skip" button but a quiet "I'll add stays manually" link.
SKIPPABLE = frozenset({"calendar", "fee", "lock"})
# A Settings save marks these steps done when it was made from the step's own
# section (the form's return_to says which section was on screen).
SAVE_SECTIONS = {"fee": "reporting", "lock": "lock", "automation": "automation"}
# Where each step happens: (view, settings section, anchor).
LOCATIONS = {
    "calendar": ("bookings", None, "calendar-connect"),
    "guest_links": ("overview", None, "property-setup"),
    "reporting": ("settings", "reporting", "ubyport"),
    "fee": ("settings", "reporting", "stay-fee-settings"),
    "lock": ("settings", "lock", "door-code"),
    "automation": ("settings", "automation", "automation"),
}
MARKS = ("done", "skipped")


def _key(apartment_id: int) -> str:
    return f"property_setup:{int(apartment_id)}"


def load(apartment_id: int) -> Optional[Dict[str, Any]]:
    raw = db.get_setting(_key(apartment_id))
    if not raw:
        return None
    try:
        state = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(state, dict):
        return None
    steps = state.get("steps")
    state["steps"] = {
        key: value
        for key, value in (steps.items() if isinstance(steps, dict) else [])
        if key in STEPS and value in MARKS
    }
    state["finished"] = bool(state.get("finished"))
    return state


def _save(apartment_id: int, state: Dict[str, Any]) -> None:
    db.set_setting(
        _key(apartment_id),
        json.dumps({"steps": state["steps"], "finished": bool(state["finished"])}, sort_keys=True),
    )


def start(apartment_id: int) -> None:
    """A new property: the guide starts at the calendar."""
    _save(apartment_id, {"steps": {}, "finished": False})


def mark(apartment_id: int, step: str, value: str) -> None:
    state = load(apartment_id)
    if not state or state["finished"] or step not in STEPS or value not in MARKS:
        return
    state["steps"][step] = value
    _save(apartment_id, state)


def finish(apartment_id: int) -> None:
    state = load(apartment_id)
    if state and not state["finished"]:
        state["finished"] = True
        _save(apartment_id, state)


def url(apartment_id: int, step: str) -> str:
    view, section, anchor = LOCATIONS[step]
    query = f"view={view}" + (f"&section={section}" if section else "")
    return f"/apartments/{int(apartment_id)}?{query}#{anchor}"


def _resolved(step: str, marks: Dict[str, str], apartment, facts: Dict[str, Any]) -> bool:
    if step == "calendar":
        return facts["feeds"] > 0 or step in marks
    if step == "reporting":
        # Only complete police details finish it: there is no skip.
        return bool(facts["report_complete"])
    if step == "fee":
        return step in marks or int(apartment["stay_fee_rate_czk"] or 0) > 0
    if step == "lock":
        return step in marks or apartment["lock_provider"] == "ttlock"
    return step in marks


def current(
    apartment,
    state: Optional[Dict[str, Any]],
    *,
    feeds: int,
    report_complete: bool,
    lock_available: bool,
) -> Optional[Dict[str, Any]]:
    """The step the host is on, or ``None`` when there is no guide to show."""
    if not state or state["finished"]:
        return None
    steps = [step for step in STEPS if step != "lock" or lock_available]
    facts = {"feeds": feeds, "report_complete": report_complete}
    for number, step in enumerate(steps, start=1):
        if _resolved(step, state["steps"], apartment, facts):
            continue
        view, section, anchor = LOCATIONS[step]
        return {
            "key": step,
            "number": number,
            "total": len(steps),
            "optional": step in OPTIONAL,
            "skippable": step in SKIPPABLE,
            "view": view,
            "section": section,
            "anchor": anchor,
            "url": url(apartment["id"], step),
        }
    return None
