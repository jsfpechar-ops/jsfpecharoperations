"""Write go/internal/web/onboarding/testdata/setup_golden.json from the real Python.

Run from App/ (create the venv first if missing:
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt):

    .venv/bin/python scripts/onboarding_setup_golden.py [OUT]

It runs app/property_setup.py (all but guest_city) over a fixed matrix of
states, apartments and facts, and app/security.py safe_local_path over a list
of inputs. The settings reads and writes of property_setup go to an in-memory
stub, so the file records the exact JSON text _save writes for every stored
value and operation. go/internal/web/onboarding/setup_test.go compares every
case. App/tests/test_go_onboarding_setup.py fails when this file is stale.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
OUT = APP.parent / "go" / "internal" / "web" / "onboarding" / "testdata" / "setup_golden.json"

APARTMENT_ID = 7

APARTMENTS = [
    {"id": 7, "internal_name": "Flat A", "legal_entity_id": 3, "addr_obec": "Praha",
     "addr_house_no": "12", "addr_zip": "11000", "stay_fee_rate_czk": 0, "lock_provider": None},
    {"id": 8, "internal_name": "", "legal_entity_id": None, "addr_obec": None,
     "addr_house_no": None, "addr_zip": None, "stay_fee_rate_czk": 0, "lock_provider": None},
    {"id": 9, "internal_name": "  ", "legal_entity_id": 2, "addr_obec": "Brno",
     "addr_house_no": "1", "addr_zip": "60200", "stay_fee_rate_czk": 50, "lock_provider": "ttlock"},
    {"id": 10, "internal_name": "\x1c", "legal_entity_id": 1, "addr_obec": "\u00a0Plze\u0148\u3000",
     "addr_house_no": "\x1f5", "addr_zip": "30100", "stay_fee_rate_czk": 1, "lock_provider": "nuki"},
    {"id": 11, "internal_name": " Loft ", "legal_entity_id": 4, "addr_obec": " Kolín ",
     "addr_house_no": " 3 ", "addr_zip": "\t28002\n", "stay_fee_rate_czk": 21, "lock_provider": ""},
    {"id": 12, "internal_name": "Flat B", "legal_entity_id": 0, "addr_obec": "Praha",
     "addr_house_no": "2", "addr_zip": "\u2028", "stay_fee_rate_czk": 0, "lock_provider": "ttlock"},
]


def _state(steps=None, **flags):
    out = {"steps": dict(steps or {}), "finished": False, "hidden": False, "legacy": False,
           "celebrated": False, "tested": False}
    out.update(flags)
    return out


STATES = [
    None,
    _state(),
    {"steps": {}, "finished": False, "hidden": False, "legacy": True},
    _state({"property": "done"}, finished=True, celebrated=True),
    _state(hidden=True),
    _state({"police": "waiting"}),
    _state({"calendar": "skipped"}, tested=True),
    _state({"property": "done", "calendar": "done", "guest_link": "done", "police": "done"}),
    _state({"calendar": "not_needed", "guest_link": "skipped"}),
    _state({"police": "skipped", "try_it": "done", "stay_fee": "done", "door_lock": "not_needed",
            "automation": "done"}),
    _state({"police": "waiting", "guest_link": "done"}, legacy=True, tested=True),
]

FACTS = [
    {"feeds": 0, "stays": 0, "guests_registered": False, "report_complete": False, "door_code": "off"},
    {"feeds": 2, "stays": 0, "guests_registered": False, "report_complete": False, "door_code": ""},
    {"feeds": 0, "stays": 1, "guests_registered": False, "report_complete": True, "door_code": "off"},
    {"feeds": 0, "stays": 0, "guests_registered": True, "report_complete": True, "door_code": "on"},
    {"feeds": 1, "stays": 3, "guests_registered": False, "report_complete": True, "door_code": "on"},
]

PROBE_STEPS = [
    "property", "calendar", "police", "guest_link", "automation", "stay_fee", "door_lock",
    "try_it", "guest_links", "pin", "try", "reporting", "fee", "lock", "done", "", "bogus",
]

SECTIONS = ["basics", "police", "calendars", "messages", "fee", "lock", "bogus"]

# Stored settings values for load() and the write operations. None is a missing row.
STORED = [
    None,
    "",
    "not json",
    "null",
    "[]",
    "\"text\"",
    "{}",
    '{"steps": {}, "finished": false}',
    '{"steps": [], "finished": 1, "hidden": "x", "legacy": 0, "celebrated": [], "tested": {}}',
    '{"steps": {"guest_links": "done", "pin": "skipped", "try": "done", "reporting": "waiting"}}',
    '{"steps": {"fee": "done", "lock": "not_needed", "calendar": "waiting", "property": "bogus"}}',
    '{"steps": {"police": "waiting", "unknown": "done", "calendar": 1, "try_it": null}}',
    '{"steps": {"pin": "done", "guest_link": "skipped"}}',
    '{"steps": {"guest_link": "skipped", "pin": "done"}}',
    '{"steps": {"pin": "done", "pin": "bogus"}}',
    '{"steps": {"automation": "done"}, "finished": true, "celebrated": false}',
    '{"steps": {"stay_fee": "done"}, "finished": true, "celebrated": true}',
    '{"steps": {}, "hidden": true, "legacy": true, "tested": 0.0, "finished": 0e5}',
    '{"steps": {}, "hidden": 1e-400, "legacy": 1e400, "tested": "0", "finished": -0}',
    '{"finished": false, "finished": true}',
    '{"steps": {"door_lock": "done"}, "celebrated": "", "tested": 2}',
    ' {"steps": {"police": "done"}} ',
    '{"steps": {"caf\\u00e9": "done", "police": "skipped"}}',
]

OPS = [
    ["start"],
    ["mark", "calendar", "done"],
    ["mark", "pin", "skipped"],
    ["mark", "police", "waiting"],
    ["mark", "calendar", "waiting"],
    ["mark", "bogus", "done"],
    ["mark", "property", "bogus"],
    ["mark", "door_lock", "not_needed"],
    ["set_hidden", True],
    ["set_hidden", False],
    ["finish"],
    ["celebrate_once"],
    ["mark_tested"],
    ["mark_tested_in_wizard"],
]

SAFE_PATH_DEFAULTS = ["/", "/onboarding", "/fallback"]

SAFE_PATHS = [
    None, "", "   ", "/", "/onboarding", "/a/b/../c", "/a/./b/", "/a/../../other", "/..",
    "/x?y=1", "/x?", "/x?a=1#frag", "/x#frag", "/x#a?b", "/?q", "  /pad  ",
    "https://other.example/path", "http:/x", "mailto:x", "a:/x", "a b:/x", "javascript:alert(1)",
    "//other.example/path", "///x", "////x", "//", "//?a", "//#a", "/%2f%2fother.example/path",
    "/%2F/x", "/\\other.example/path", "/%5cother.example/path", "/safe\r\nLocation: https://x",
    "/a%0d%0ab", "/a%1fb", "/a%20b", "/a b", "/caf\u00e9", "/caf%C3%A9", "/%ff", "/%zz",
    "/a\x7fb", "/a\tb", "\t/a", "x", "relative/path", "?only", "#only", "/a//b", "/a/%2e%2e/b",
    "/a?x=//evil", "/a?x=\\", "/\u00a0", "\u3000/a\u3000", "/a\"<>`{|}^", "/~user", "/a;b=c",
    "/[x]", "//[x", "/a?\u00e9=\u00e9",
]


class _Settings:
    """In-memory stand-in for db.get_setting and db.set_setting."""

    def __init__(self, stored):
        self.stored = stored
        self.writes = []

    def get_setting(self, key, default=None):
        return self.stored if self.stored is not None else default

    def set_setting(self, key, value):
        self.writes.append([key, value])
        self.stored = value


def _with_settings(ps, stored, fn):
    stub = _Settings(stored)
    real = ps.db
    ps.db = stub
    try:
        result = fn()
    finally:
        ps.db = real
    return result, stub.writes


def _constants(ps):
    return {
        "steps": list(ps.STEPS),
        "retired_steps": list(ps.RETIRED_STEPS),
        "known_steps": list(ps.KNOWN_STEPS),
        "total_steps": ps.TOTAL_STEPS,
        "optional": sorted(ps.OPTIONAL),
        "skippable": sorted(ps.SKIPPABLE),
        "teaching": sorted(ps.TEACHING),
        "marks": list(ps.MARKS),
        "step_fields": {k: list(v) for k, v in ps.STEP_FIELDS.items()},
        "legacy_aliases": dict(ps._LEGACY_STEP_ALIASES),
        "section_minutes": dict(ps.SECTION_MINUTES),
        "setup_order": list(ps.SETUP_ORDER),
        "legacy_state": ps.legacy_state(),
    }


def _per_step(ps):
    return [
        {
            "step": step,
            "normalise": ps._normalise_step(step),
            "next_step": ps.next_step(step),
            "prev_step": ps.prev_step(step),
            "wizard_url": ps.wizard_url(APARTMENT_ID, step),
        }
        for step in PROBE_STEPS
    ]


def _per_apartment(ps):
    out = []
    for ai, apartment in enumerate(APARTMENTS):
        for lock in (True, False):
            out.append({
                "apartment": ai,
                "lock_available": lock,
                "property_details_complete": ps.property_details_complete(apartment),
                "steps": [
                    {
                        "step": step,
                        "applicable": ps.step_applicable(step, apartment, lock_available=lock),
                        "next": ps.next_applicable_step(step, apartment, lock_available=lock),
                        "prev": ps.prev_applicable_step(step, apartment, lock_available=lock),
                    }
                    for step in PROBE_STEPS
                ],
            })
    return out


def _matrix(ps):
    out = []
    for ai, apartment in enumerate(APARTMENTS):
        for si, state in enumerate(STATES):
            for fi, facts in enumerate(FACTS):
                # Both lock values appear across the matrix; per_apartment has both for each.
                lock = (ai + si + fi) % 2 == 0
                case = {
                    "apartment": ai,
                    "state": si,
                    "facts": fi,
                    "lock_available": lock,
                    "section_done": [ps.section_done(k, apartment, facts, state) for k in SECTIONS],
                    "open_section": ps.open_section(apartment, facts, state),
                    "setup_complete": ps.setup_complete(apartment, facts, state),
                    "current": ps.current(
                        apartment, state, feeds=facts["feeds"],
                        report_complete=facts["report_complete"], lock_available=lock,
                        stays=facts["stays"], guests_registered=facts["guests_registered"],
                    ),
                }
                if state is not None:
                    guide = case["current"]
                    case["step_status"] = [ps.step_status(s, state, apartment, facts) for s in PROBE_STEPS]
                    case["done_count"] = ps.done_count(state, apartment, facts, lock_available=lock)
                    case["wizard_unresolved"] = ps.wizard_unresolved(apartment, state, facts, lock_available=lock)
                    case["checklist"] = ps.checklist(state, apartment, facts, lock_available=lock)
                    case["may_view"] = [
                        ps.may_view_step(s, guide, state, apartment, facts, lock_available=lock)
                        for s in PROBE_STEPS
                    ]
                    case["may_view_no_guide"] = [
                        ps.may_view_step(s, None, state, apartment, facts, lock_available=lock)
                        for s in PROBE_STEPS
                    ]
                out.append(case)
    return out


def _call(ps, op):
    name, args = op[0], op[1:]
    fn = getattr(ps, name)
    return fn(APARTMENT_ID, *args)


def _stored_cases(ps):
    out = []
    for raw in STORED:
        loaded, _ = _with_settings(ps, raw, lambda: ps.load(APARTMENT_ID))
        case = {"raw": raw, "load": loaded, "save": None, "ops": []}
        if loaded is not None:
            _, writes = _with_settings(ps, None, lambda: ps._save(APARTMENT_ID, loaded))
            case["save"] = writes[0][1]
        for op in OPS:
            returned, writes = _with_settings(ps, raw, lambda: _call(ps, op))
            case["ops"].append({"op": op, "returned": returned, "writes": writes})
        out.append(case)
    return out


def _save_states(ps):
    out = []
    for state in STATES:
        if state is None:
            continue
        _, writes = _with_settings(ps, None, lambda: ps._save(APARTMENT_ID, state))
        out.append(writes[0][1])
    return out


def _safe_paths(security):
    out = []
    for value in SAFE_PATHS:
        for default in SAFE_PATH_DEFAULTS:
            try:
                result = security.safe_local_path(value, default)
                raised = False
            except ValueError:
                result, raised = None, True
            out.append({"value": value, "default": default, "result": result, "raises": raised})
    return out


def render() -> str:
    from app import property_setup as ps
    from app import security

    golden = {
        "apartment_id": APARTMENT_ID,
        "constants": _constants(ps),
        "apartments": APARTMENTS,
        "states": STATES,
        "facts": FACTS,
        "probe_steps": PROBE_STEPS,
        "sections": SECTIONS,
        "per_step": _per_step(ps),
        "per_apartment": _per_apartment(ps),
        "matrix": _matrix(ps),
        "save_states": _save_states(ps),
        "stored": _stored_cases(ps),
        "safe_paths": _safe_paths(security),
    }
    return json.dumps(golden, ensure_ascii=True, indent=1, sort_keys=True) + "\n"


def main(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    tmp = Path(tempfile.mkdtemp(prefix="ubyhost-golden-"))
    os.environ.setdefault("UBYHOST_DATA_DIR", str(tmp))
    os.environ.setdefault("UBYHOST_DB", str(tmp / "onboarding_setup_golden.sqlite3"))
    os.environ.setdefault("UBYHOST_SECRET_KEY", "golden-secret-key-not-for-real-use")
    os.environ.setdefault("UBYHOST_ENABLE_SCHEDULER", "0")
    sys.path.insert(0, str(APP))
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
