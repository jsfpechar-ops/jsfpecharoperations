"""Pins every writer of cleaning_code.state against cleaning_codes.TRANSITIONS.

Round 1 of docs/plans/explicit-state-machines.md: the table lists the moves the
code makes today, nothing more. The test reads the writer source as text, finds
every statement that writes cleaning_code.state, and compares the list with the
pins below. Adding, removing or changing a write fails it. Pins use the enclosing
function name, never a line number.

Open questions (writes with no state guard in the SQL WHERE clause; pinned as
from-any; line numbers are in App/app/cleaning_codes.py after the brief 1108 edit):
- _activate, line 83: state = 'revoke_pending' WHERE id = ?
- _activate, line 92: state = 'active' WHERE id = ?
- _activate, line 108: state = 'detached' WHERE id = ? (guarded only by a Python read)
- _activate, line 113: CASE to 'revoke_pending' or 'revoked' WHERE id = ? (Python read guard)
- save_manual, line 139: state = 'revoke_pending' WHERE id = ? (Python guard skips issuing, revoking)
- _failure, line 213: db.update with state from the `revoking` flag, no compare-and-swap
- process_queue, line 284: db.update state 'revoked' after the provider delete, no compare-and-swap
- remove, line 315: state = ? WHERE id = ? (Python guard skips issuing, revoking)
Also: remove can re-queue a 'revoked' ttlock code that the property still points at.
The table still lists these writes by the states the Python code allows, so the
reachable moves are pinned below under "moves".
"""
import ast
import re
from collections import Counter
from pathlib import Path

from app import cleaning_codes

TESTS = Path(__file__).resolve().parent
APP = TESTS.parent / "app"
GO = TESTS.parent.parent / "go"
SOURCE = APP / "cleaning_codes.py"
KNOWN = set(cleaning_codes.STATES)

STATE_SET = re.compile(r"(?<![\w.])state = ")
GUARD_EQ = re.compile(r"(?<![\w.])state = '(\w+)'")
GUARD_IN = re.compile(r"(?<![\w.])state IN \(([^)]*)\)")
OTHER_WRITE = re.compile(
    r"(UPDATE|INSERT INTO|DELETE FROM)\s+cleaning_code\b"
    r"|(update|update_if|insert|insert_in)\(\s*(cur\s*,\s*)?[\"']cleaning_code[\"']"
)

# (function, kind, to-states, guard, moves).
# guard: tuple of from-states in the SQL WHERE, "PARAM" when the WHERE compares
# state to a variable, None when the SQL has no state guard (from-any).
# moves: for a guarded write, the exact (from, to) pairs. For a from-any write,
# the pairs the surrounding Python allows ("reach"). An insert has no moves.
PINS = [
    ("_activate", "sql", ("revoke_pending",), None, [("issuing", "revoke_pending")]),
    ("_activate", "sql", ("active",), None, [("issuing", "active"), ("active", "active")]),
    ("_activate", "sql", ("detached",), None, [("active", "detached")]),
    ("_activate", "sql", ("revoke_pending", "revoked"), None,
     [("active", "revoke_pending"), ("active", "revoked")]),
    ("save_manual", "sql", ("revoke_pending",), None,
     [("pending", "revoke_pending"), ("retrying", "revoke_pending"), ("failed", "revoke_pending")]),
    ("save_manual", "insert", ("active",), None, []),
    ("queue_permanent", "sql", ("retrying",), ("failed",), [("failed", "retrying")]),
    ("queue_permanent", "insert", ("pending",), None, []),
    ("_failure", "update", ("failed", "retrying", "revoke_failed", "revoke_pending"), None,
     [("issuing", "retrying"), ("issuing", "failed"),
      ("revoking", "revoke_pending"), ("revoking", "revoke_failed")]),
    ("process_queue", "sql", ("revoke_pending",), ("active",), [("active", "revoke_pending")]),
    ("process_queue", "sql", ("retrying",), ("issuing",), [("issuing", "retrying")]),
    ("process_queue", "sql", ("revoke_pending",), ("revoking",), [("revoking", "revoke_pending")]),
    ("process_queue", "update_if", ("revoke_pending", "revoked"), "PARAM",
     [("pending", "revoked"), ("retrying", "revoke_pending")]),
    ("process_queue", "update_if", ("issuing", "revoking"), "PARAM",
     [("pending", "issuing"), ("retrying", "issuing"), ("revoke_pending", "revoking")]),
    ("process_queue", "update", ("revoked",), None, [("revoking", "revoked")]),
    ("remove", "sql", ("revoke_pending", "revoked"), None,
     [("pending", "revoke_pending"), ("retrying", "revoke_pending"), ("failed", "revoke_pending"),
      ("active", "revoke_pending"), ("active", "revoked"), ("revoke_pending", "revoke_pending"),
      ("revoke_failed", "revoke_pending"), ("revoked", "revoke_pending")]),
]


def _consts(node):
    return {n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _str_arg(call, index):
    if len(call.args) > index and isinstance(call.args[index], ast.Constant):
        value = call.args[index].value
        return value if isinstance(value, str) else None
    return None


def _dict_value(node, key):
    if not isinstance(node, ast.Dict):
        return None
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and k.value == key:
            return v
    return None


def _assigned(fn, name):
    found = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            found |= _consts(node.value)
    return found


def _sql_guard(where):
    states = set(GUARD_EQ.findall(where))
    for group in GUARD_IN.findall(where):
        states |= set(re.findall(r"'(\w+)'", group))
    return tuple(sorted(states)) or None


def _found_writes():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    found = []
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        for call in ast.walk(fn):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
                continue
            method = call.func.attr
            sql = _str_arg(call, 0)
            if method == "execute" and sql:
                update = re.match(r"\s*UPDATE cleaning_code SET (.*)", sql, re.S)
                if update:
                    set_part, _, where = update.group(1).partition(" WHERE ")
                    if not STATE_SET.search(set_part):
                        continue
                    to = {w for w in re.findall(r"'(\w+)'", set_part) if w in KNOWN}
                    if not to and re.search(r"(?<![\w.])state = \?", set_part):
                        to = _consts(call.args[1]) & KNOWN
                    found.append((fn.name, "sql", tuple(sorted(to)), _sql_guard(where)))
                elif re.match(r"\s*INSERT INTO cleaning_code ", sql):
                    to = {w for w in re.findall(r"'(\w+)'", sql) if w in KNOWN}
                    found.append((fn.name, "insert", tuple(sorted(to)), None))
            elif method in ("update", "update_if") and sql == "cleaning_code":
                value = _dict_value(call.args[2], "state")
                if value is None:
                    continue
                to = _assigned(fn, value.id) if isinstance(value, ast.Name) else _consts(value)
                guard = None
                if method == "update_if":
                    expected = _dict_value(call.args[3], "state")
                    if isinstance(expected, ast.Constant):
                        guard = (expected.value,)
                    elif expected is not None:
                        guard = "PARAM"
                found.append((fn.name, method, tuple(sorted(to & KNOWN)), guard))
    return found


def _pinned():
    return [(f, k, tuple(sorted(to)), g) for f, k, to, g, _ in PINS]


def test_every_state_write_is_pinned():
    assert Counter(_found_writes()) == Counter(_pinned())


def test_pinned_moves_are_in_transitions():
    union = set()
    for targets in cleaning_codes.TRANSITIONS.values():
        union |= targets
    for function, kind, to, guard, moves in PINS:
        for move in moves:
            assert move[1] in cleaning_codes.TRANSITIONS[move[0]], (function, move)
            assert move[1] in to, (function, move)
        if kind != "insert":
            for state in to:
                assert state in union, (function, state)


def test_transitions_list_only_pinned_moves():
    pinned = {move for *_, moves in PINS for move in moves}
    declared = {(a, b) for a, targets in cleaning_codes.TRANSITIONS.items() for b in targets}
    assert declared == pinned


def test_states_and_transitions_are_consistent():
    assert len(set(cleaning_codes.STATES)) == len(cleaning_codes.STATES)
    assert set(cleaning_codes.TRANSITIONS) == set(cleaning_codes.STATES)
    for targets in cleaning_codes.TRANSITIONS.values():
        assert targets <= set(cleaning_codes.STATES)


def test_no_other_file_writes_cleaning_code():
    files = [p for p in APP.rglob("*.py") if p != SOURCE]
    if GO.is_dir():
        files += list(GO.rglob("*.go"))
    offenders = [str(p) for p in files if OTHER_WRITE.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
