"""0096/0100/0102: guided property setup — wizard pages, one step at a time.

State lives in ``settings`` key ``property_setup:<id>`` as JSON
``{"steps": {"<step>": "done" | "skipped" | "waiting"}, "finished": false,
"hidden": false, "legacy": false}``. No personal data.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from . import db

STEPS = (
    "property",
    "calendar",
    "guest_link",
    "try_it",
    "police",
    "stay_fee",
    "door_lock",
    "automation",
)
TOTAL_STEPS = len(STEPS)
OPTIONAL = frozenset({"stay_fee", "door_lock"})
SKIPPABLE = frozenset({"calendar", "try_it", "stay_fee", "door_lock"})
TEACHING = frozenset({"guest_link", "try_it"})
MARKS = ("done", "skipped", "waiting")

# Columns each wizard save may write. Hidden passthrough fields on a step form are
# not listed here, so a partial post cannot blank another step's data.
STEP_FIELDS: Dict[str, tuple] = {
    "property": (
        "internal_name",
        "city_en",
        "legal_entity_id",
        "data_controller_entity_id",
        "default_purpose",
        "checkin_hour",
        "checkout_hour",
        "addr_okres",
        "addr_obec",
        "addr_obec_cast",
        "addr_street",
        "addr_house_no",
        "addr_orient_no",
        "addr_zip",
    ),
    "police": ("uby_idub", "uby_mark", "uby_name", "uby_contact", "uby_ws_user"),
    "stay_fee": (
        "stay_fee_rate_czk",
        "stay_fee_cadence",
        "stay_fee_vs",
        "stay_fee_authority_name",
        "stay_fee_authority_address",
        "stay_fee_authority_contact",
        "stay_fee_authority_databox",
        "stay_fee_payee",
        "stay_fee_instruction",
        "stay_fee_council_account",
    ),
    "door_lock": ("lock_provider", "lock_id"),
    "automation": ("automation_mode", "submit_after_hours"),
}

# Stored JSON from 0096/0100 used older step ids; map them on read.
_LEGACY_STEP_ALIASES = {
    "guest_links": "guest_link",
    "pin": "guest_link",
    "try": "try_it",
    "reporting": "police",
    "fee": "stay_fee",
    "lock": "door_lock",
}


def _key(apartment_id: int) -> str:
    return f"property_setup:{int(apartment_id)}"


def _normalise_step(step: str) -> str:
    return _LEGACY_STEP_ALIASES.get(step, step)


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
    normalised: Dict[str, str] = {}
    if isinstance(steps, dict):
        for key, value in steps.items():
            step = _normalise_step(key)
            if step not in STEPS or value not in MARKS:
                continue
            if value == "waiting" and step != "police":
                continue
            normalised[step] = value
    return {
        "steps": normalised,
        "finished": bool(state.get("finished")),
        "hidden": bool(state.get("hidden")),
        "legacy": bool(state.get("legacy")),
    }


def legacy_state() -> Dict[str, Any]:
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
    _save(apartment_id, {"steps": {}, "finished": False})


def mark(apartment_id: int, step: str, value: str) -> None:
    step = _normalise_step(step)
    state = load(apartment_id) or legacy_state()
    if state["finished"] or step not in STEPS or value not in MARKS:
        return
    if value == "waiting" and step != "police":
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


def wizard_url(apartment_id: int, step: str) -> str:
    return f"/apartments/{int(apartment_id)}/setup/{step}"


def next_step(step: str) -> Optional[str]:
    step = _normalise_step(step)
    if step not in STEPS:
        return None
    index = STEPS.index(step)
    if index + 1 >= len(STEPS):
        return "done"
    return STEPS[index + 1]


def prev_step(step: str) -> Optional[str]:
    step = _normalise_step(step)
    if step not in STEPS:
        return None
    index = STEPS.index(step)
    if index <= 0:
        return None
    return STEPS[index - 1]


def step_applicable(step: str, apartment, *, lock_available: bool) -> bool:
    step = _normalise_step(step)
    if step == "property" and property_details_complete(apartment):
        return False
    if step == "door_lock" and not lock_available:
        return False
    return step in STEPS


def next_applicable_step(
    step: str,
    apartment,
    *,
    lock_available: bool,
) -> Optional[str]:
    """Next wizard step that exists for this property, or ``done`` after the last."""
    step = _normalise_step(step)
    if step not in STEPS:
        return None
    index = STEPS.index(step)
    for nxt in STEPS[index + 1 :]:
        if step_applicable(nxt, apartment, lock_available=lock_available):
            return nxt
    return "done"


def prev_applicable_step(
    step: str,
    apartment,
    *,
    lock_available: bool,
) -> Optional[str]:
    """Previous wizard step that exists for this property (for Back links)."""
    step = _normalise_step(step)
    if step not in STEPS:
        return None
    index = STEPS.index(step)
    for prior in reversed(STEPS[:index]):
        if step_applicable(prior, apartment, lock_available=lock_available):
            return prior
    return None


def may_view_step(
    step: str,
    guide: Optional[Dict[str, Any]],
    state: Dict[str, Any],
    apartment,
    facts: Dict[str, Any],
    *,
    lock_available: bool,
) -> bool:
    """Whether GET /setup/{step} may render (Back, or revisiting a done step)."""
    step = _normalise_step(step)
    if step not in STEPS:
        return False
    if not step_applicable(step, apartment, lock_available=lock_available):
        return False
    if not guide:
        return True
    current = guide["key"]
    current_idx = STEPS.index(current)
    step_idx = STEPS.index(step)
    if step_idx < current_idx:
        return True
    if step_idx > current_idx:
        return False
    if step_status(step, state, apartment, facts) in ("done", "skipped", "waiting"):
        return True
    return step == current


def property_details_complete(apartment) -> bool:
    return bool(
        (apartment["internal_name"] or "").strip()
        and apartment["legal_entity_id"]
        and (apartment["addr_obec"] or "").strip()
        and (apartment["addr_house_no"] or "").strip()
        and (apartment["addr_zip"] or "").strip()
    )


def _resolved(step: str, state: Dict[str, Any], apartment, facts: Dict[str, Any]) -> bool:
    marks = state["steps"]
    if step == "property":
        return property_details_complete(apartment) or step in marks
    if step == "calendar":
        return facts["feeds"] > 0 or facts["stays"] > 0 or step in marks
    if step in TEACHING:
        if facts.get("guests_registered"):
            return True
        return step in marks
    if step == "police":
        return bool(facts["report_complete"])
    if step == "stay_fee":
        return step in marks or int(apartment["stay_fee_rate_czk"] or 0) > 0
    if step == "door_lock":
        return step in marks or apartment["lock_provider"] == "ttlock"
    if step == "automation":
        return step in marks or bool(state.get("legacy"))
    return step in marks


def step_status(
    step: str,
    state: Dict[str, Any],
    apartment,
    facts: Dict[str, Any],
) -> str:
    """done | skipped | waiting | todo | current — for checklist and progress."""
    marks = state["steps"]
    if step == "police" and marks.get("police") == "waiting" and not facts["report_complete"]:
        return "waiting"
    if marks.get(step) == "skipped":
        return "skipped"
    if _resolved(step, state, apartment, facts):
        return "done"
    return "todo"


def done_count(
    state: Dict[str, Any],
    apartment,
    facts: Dict[str, Any],
    *,
    lock_available: bool = True,
) -> int:
    total = 0
    for step in STEPS:
        if step == "door_lock" and not lock_available:
            total += 1
            continue
        if step_status(step, state, apartment, facts) in ("done", "skipped"):
            total += 1
    return total


def wizard_unresolved(
    apartment,
    state: Dict[str, Any],
    facts: Dict[str, Any],
    *,
    lock_available: bool,
) -> bool:
    """True while a setup step still needs an answer; police may be deferred."""
    for step in STEPS:
        if not step_applicable(step, apartment, lock_available=lock_available):
            continue
        status = step_status(step, state, apartment, facts)
        if status in ("todo", "current"):
            return True
    return False


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
    """The wizard step the host should see, or None when setup is complete."""
    if not state or state["finished"] or state.get("hidden"):
        return None
    facts = {
        "feeds": feeds,
        "stays": stays,
        "guests_registered": guests_registered,
        "report_complete": report_complete,
    }
    waiting = state["steps"].get("police") == "waiting" and not report_complete
    progress: List[Dict[str, str]] = []
    chosen: Optional[int] = None
    for index, step in enumerate(STEPS):
        if step == "door_lock" and not lock_available:
            progress.append({"key": step, "state": "done" if _resolved(step, state, apartment, facts) else "skipped"})
            continue
        status = step_status(step, state, apartment, facts)
        if status in ("done", "skipped"):
            progress.append({"key": step, "state": "done" if status == "done" else "skipped"})
        elif step == "police" and waiting:
            progress.append({"key": step, "state": "waiting"})
            continue
        elif chosen is None:
            chosen = index
            progress.append({"key": step, "state": "current"})
        else:
            progress.append({"key": step, "state": "todo"})
    if chosen is None:
        return None
    step = STEPS[chosen]
    return {
        "key": step,
        "number": chosen + 1,
        "total": TOTAL_STEPS,
        "optional": step in OPTIONAL,
        "skippable": step in SKIPPABLE,
        "url": wizard_url(apartment["id"], step),
        "progress": progress,
        "reporting_waiting": waiting,
        "police_url": wizard_url(apartment["id"], "police"),
        "legacy": bool(state.get("legacy")),
        "done_count": done_count(state, apartment, facts, lock_available=lock_available),
    }


def checklist(
    state: Dict[str, Any],
    apartment,
    facts: Dict[str, Any],
    *,
    lock_available: bool,
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for step in STEPS:
        if step == "door_lock" and not lock_available:
            rows.append({"key": step, "status": "skipped"})
            continue
        rows.append({"key": step, "status": step_status(step, state, apartment, facts)})
    return rows
