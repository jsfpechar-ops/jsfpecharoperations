"""0096/0100: the guided setup of a property, one step at a time.

Calendar -> Guest link -> PIN -> Try it out (a demo stay) -> Police reporting
-> Stay fee (optional) -> Door lock (optional, only where door codes exist)
-> Automation.

No schema change: the state is one key in the existing ``settings`` key/value
table per property, ``property_setup:<id>``, holding JSON
``{"steps": {"<step>": "done" | "skipped" | "waiting"}, "finished": false,
"hidden": false, "legacy": false}``. It holds no personal data.

- A new property writes the key on create.
- 0100: a property without the key (made before 0096) gets the guide too,
  unless it is already set up (police details complete and stays on the way);
  the caller decides that from the record and passes ``legacy_state()``.
  ``legacy`` keeps such a property's Automation counted as done: its sending
  mode was chosen before the guide existed.
- A finished guide never returns. ``hidden`` is the host's "Hide setup guide".
- Police reporting can be marked ``waiting`` (the host is still waiting for the
  police login). The guide then moves on, but reporting stays unfinished and
  the guide cannot finish until the police details are complete.

Several steps finish themselves from the real record (a calendar or a stay
exists, a guest registered through the link, police details are complete, a
fee rate or a lock is set); the others need the host's own click.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from . import db

STEPS = ("calendar", "guest_links", "pin", "try", "reporting", "fee", "lock", "automation")
OPTIONAL = frozenset({"fee", "lock"})
# The calendar has no "Skip" button but a quiet "I'll add stays manually" link;
# "Try it out" has a quiet "Skip".
SKIPPABLE = frozenset({"calendar", "try", "fee", "lock"})
# Steps that teach how the app works. A guest who registered through the link
# proves the host already did each of them.
TEACHING = frozenset({"guest_links", "pin", "try"})
# A Settings save marks these steps done when it was made from the step's own
# section (the form's return_to says which section was on screen).
SAVE_SECTIONS = {"fee": "reporting", "lock": "lock", "automation": "automation"}
# Where each step happens: (view, settings section, anchor).
LOCATIONS = {
    "calendar": ("bookings", None, "calendar-connect"),
    "guest_links": ("overview", None, "property-setup"),
    "pin": ("overview", None, "property-setup"),
    "try": ("overview", None, "property-setup"),
    "reporting": ("settings", "reporting", "ubyport"),
    "fee": ("settings", "reporting", "stay-fee-settings"),
    "lock": ("settings", "lock", "door-code"),
    "automation": ("settings", "automation", "automation"),
}
MARKS = ("done", "skipped", "waiting")


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
    return {
        "steps": {
            key: value
            for key, value in (steps.items() if isinstance(steps, dict) else [])
            if key in STEPS and value in MARKS and (value != "waiting" or key == "reporting")
        },
        "finished": bool(state.get("finished")),
        "hidden": bool(state.get("hidden")),
        "legacy": bool(state.get("legacy")),
    }


def legacy_state() -> Dict[str, Any]:
    """The state of a property made before the guide, until it is first saved."""
    return {"steps": {}, "finished": False, "hidden": False, "legacy": True}


def _save(apartment_id: int, state: Dict[str, Any]) -> None:
    db.set_setting(
        _key(apartment_id),
        json.dumps(
            {
                "steps": state["steps"],
                "finished": bool(state["finished"]),
                "hidden": bool(state.get("hidden")),
                "legacy": bool(state.get("legacy")),
            },
            sort_keys=True,
        ),
    )


def start(apartment_id: int) -> None:
    """A new property: the guide starts at the calendar."""
    _save(apartment_id, {"steps": {}, "finished": False})


def mark(apartment_id: int, step: str, value: str) -> None:
    """Record a step. The caller has checked the guide is on that step."""
    state = load(apartment_id) or legacy_state()
    if state["finished"] or step not in STEPS or value not in MARKS:
        return
    if value == "waiting" and step != "reporting":
        return
    state["steps"][step] = value
    _save(apartment_id, state)


def set_hidden(apartment_id: int, hidden: bool) -> None:
    state = load(apartment_id) or legacy_state()
    if state["finished"]:
        return
    state["hidden"] = bool(hidden)
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


def _resolved(step: str, state: Dict[str, Any], apartment, facts: Dict[str, Any]) -> bool:
    marks = state["steps"]
    if step == "calendar":
        return facts["feeds"] > 0 or facts["stays"] > 0 or step in marks
    if step in TEACHING:
        return step in marks or bool(facts["guests_registered"])
    if step == "reporting":
        # Only complete police details finish it. "Waiting" moves the guide
        # on but never counts as done.
        return bool(facts["report_complete"])
    if step == "fee":
        return step in marks or int(apartment["stay_fee_rate_czk"] or 0) > 0
    if step == "lock":
        return step in marks or apartment["lock_provider"] == "ttlock"
    if step == "automation":
        return step in marks or bool(state.get("legacy"))
    return step in marks


def current(
    apartment,
    state: Optional[Dict[str, Any]],
    *,
    feeds: int,
    report_complete: bool,
    lock_available: bool,
    stays: int = 0,
    guests_registered: bool = False,
) -> Optional[Dict[str, Any]]:
    """The step the host is on, or ``None`` when there is no guide to show."""
    if not state or state["finished"] or state.get("hidden"):
        return None
    steps = [step for step in STEPS if step != "lock" or lock_available]
    facts = {
        "feeds": feeds,
        "stays": stays,
        "guests_registered": guests_registered,
        "report_complete": report_complete,
    }
    waiting = state["steps"].get("reporting") == "waiting" and not report_complete
    progress: List[Dict[str, str]] = []
    chosen: Optional[int] = None
    for index, step in enumerate(steps):
        if _resolved(step, state, apartment, facts):
            progress.append({"key": step, "state": "done"})
        elif step == "reporting" and waiting:
            progress.append({"key": step, "state": "waiting"})
        elif chosen is None:
            chosen = index
            progress.append({"key": step, "state": "current"})
        else:
            progress.append({"key": step, "state": "todo"})
    if chosen is None and waiting:
        # Everything else is done: the guide comes back to the police login.
        chosen = steps.index("reporting")
        progress[chosen]["state"] = "current"
    if chosen is None:
        return None
    step = steps[chosen]
    view, section, anchor = LOCATIONS[step]
    return {
        "key": step,
        "number": chosen + 1,
        "total": len(steps),
        "optional": step in OPTIONAL,
        "skippable": step in SKIPPABLE,
        "view": view,
        "section": section,
        "anchor": anchor,
        "url": url(apartment["id"], step),
        "progress": progress,
        # Police reporting was put off: shown at the top of the guide until done.
        "reporting_waiting": waiting,
        "reporting_url": url(apartment["id"], "reporting"),
        # A property from before the guide keeps opening on Overview, with its
        # checklist; only a new property opens on the step it is on.
        "legacy": bool(state.get("legacy")),
    }
