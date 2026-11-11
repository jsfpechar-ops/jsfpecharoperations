# 1108: Pin cleaning_code.state writers to an explicit TRANSITIONS table

Status: todo
Depends on: none | Base commit: 5e034303 | Branch: task/1108-sm-cleaning-code-state
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Declare the `cleaning_code.state` machine in code (`STATES` and `TRANSITIONS` in `App/app/cleaning_codes.py`) and add a test that fails when a write to that column appears, disappears or changes without the table being updated. No runtime behaviour changes: nothing reads the new names and no writer is edited. This is brief 1108 of [explicit-state-machines](../plans/explicit-state-machines.md).

## 2. Context

Rules that apply (plan, "Rules for every brief"): the table lists exactly the moves the code makes today (derive, never design); no writer is edited; no migration, no dependency, no template or copy change. A write with no state guard in its SQL WHERE clause is pinned as from-any by the test and listed under "Open questions" in the test docstring.

`cleaning_code.state` is `state TEXT NOT NULL`, no CHECK, no default (`App/app/migrations/0010_cleaning.sql`). The ten states: pending, issuing, active, retrying, failed, revoke_pending, revoking, revoked, revoke_failed, detached. A row is created as `pending` (`queue_permanent`, ttlock source) or `active` (`save_manual`, manual source).

Every writer is in `App/app/cleaning_codes.py`. Nothing else writes the column: `App/app/cleaning.py`, `App/app/routes/cleaning.py` and `App/app/scheduler.py` only read it or call this module, and `go/` has no reference. The last test in step 2 checks this.

Anchor for step 1, in `App/app/cleaning_codes.py` (line 13, verbatim):

```
from . import auth, cleaning, db, ttlock
```

Writers by function (the test pins them; do not edit them): `_activate` (4 writes), `save_manual` (UPDATE and INSERT), `queue_permanent` (UPDATE and INSERT), `_failure` (`db.update`), `process_queue` (3 UPDATEs, 2 `db.update_if`, 1 `db.update`), `remove` (1 UPDATE).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/cleaning_codes.py | edit | Add `STATES` and `TRANSITIONS` after the imports (step 1) |
| App/tests/test_sm_cleaning_code_state.py | create | The pinning test, full content in step 2 |

No other file may change.

## 4. Steps

### Step 1: add STATES and TRANSITIONS to cleaning_codes.py

1. Confirm the anchor, from the repo root: `grep -nF "from . import auth, cleaning, db, ttlock" App/app/cleaning_codes.py 2>&1 | tail -30`. Expected: one line, `13:from . import auth, cleaning, db, ttlock`. Not found: STOP.
2. In `App/app/cleaning_codes.py`, insert the block below directly after that line. The block starts with one blank line and ends with `}`; the file's existing blank lines before `def _activate` stay as they are. Change nothing else.

```python

# Declared state machine for cleaning_code.state. Derived from the writers in
# this module (round 1 of docs/plans/explicit-state-machines.md); nothing reads
# it at runtime. App/tests/test_sm_cleaning_code_state.py pins every writer to it.
# A new row is inserted as 'pending' (queue_permanent) or 'active' (save_manual).
STATES = (
    "pending", "issuing", "active", "retrying", "failed",
    "revoke_pending", "revoking", "revoked", "revoke_failed", "detached",
)
TRANSITIONS = {
    "pending": {
        "issuing",         # process_queue: claim
        "revoke_pending",  # save_manual, remove: replaced or removed before issuing
        "revoked",         # process_queue: lock no longer bound, nothing attempted yet
    },
    "retrying": {
        "issuing",         # process_queue: claim
        "revoke_pending",  # save_manual, remove, process_queue (lock no longer bound)
    },
    "issuing": {
        "active",          # _activate
        "revoke_pending",  # _activate: binding changed while issuing
        "retrying",        # _failure (transient), process_queue (stale claim)
        "failed",          # _failure
    },
    "active": {
        "active",          # _activate: save_manual inserts 'active', then activates it
        "revoke_pending",  # process_queue (binding lost), _activate (replaced), remove
        "revoked",         # _activate (replaced manual code), remove (manual code)
        "detached",        # _activate: same physical PIN taken over by a manual code
    },
    "failed": {
        "retrying",        # queue_permanent
        "revoke_pending",  # save_manual, remove
    },
    "revoke_pending": {
        "revoking",        # process_queue: claim
        "revoke_pending",  # remove on a code that is already queued
    },
    "revoking": {
        "revoked",         # process_queue
        "revoke_pending",  # _failure (transient), process_queue (stale claim)
        "revoke_failed",   # _failure
    },
    "revoke_failed": {
        "revoke_pending",  # remove
    },
    "revoked": {
        "revoke_pending",  # remove: the property can still point at a revoked ttlock code
    },
    "detached": set(),
}
```

3. Check import and sizes, from `App/`: `.venv/bin/python -c "from app import cleaning_codes as c; print(len(c.STATES), len(c.TRANSITIONS))" 2>&1 | tail -30`. Expected output: `10 10`.
4. Check the writers did not move relative to the block, from the repo root: `grep -n "^def _activate" App/app/cleaning_codes.py 2>&1 | tail -30`. Expected: `68:def _activate(cur, row: dict) -> None:`.
5. Commit: `git add App/app/cleaning_codes.py && git commit -m "1108 step 1" 2>&1 | tail -30`.

### Step 2: create the test

1. Create `App/tests/test_sm_cleaning_code_state.py` with exactly this content:

```python
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
```

2. Run, from `App/`: `.venv/bin/python -m pytest tests/test_sm_cleaning_code_state.py -q --tb=short -x 2>&1 | tail -30`. Expected: `5 passed`.
3. If `test_every_state_write_is_pinned` fails: read the assertion diff once, then run from the repo root `git diff HEAD~1 -- App/app/cleaning_codes.py 2>&1 | head -80` and confirm it shows only added lines. Fix once, rerun. Fails again: STOP and report. Do not edit `PINS` to make it pass unless a changed writer explains the failure.
4. Check the line numbers in the test docstring, from the repo root: `grep -nE "UPDATE cleaning_code SET state|INSERT INTO cleaning_code|db.update\(\"cleaning_code\"" App/app/cleaning_codes.py 2>&1 | tail -30`. The docstring lines (83, 92, 108, 113, 139, 213, 284, 315) must be the statement starts shown. If one is off, correct only that number in the docstring and say so under Deviations.
5. Commit: `git add App/tests/test_sm_cleaning_code_state.py && git commit -m "1108 step 2" 2>&1 | tail -30`.

### Step 3: run the existing cleaning tests

1. From `App/`: `.venv/bin/python -m pytest tests/test_cleaning.py -q --tb=short -x 2>&1 | tail -30`. Expected: all passed, 0 failed. On failure: read the last 30 lines, rerun once (only additive code changed); fails again: STOP and report.
2. `tests/test_cleaning_browser.py` is in the test-map row but no template or CSS changed; leave it to CI.

## 5. Do not touch

- Any writer in `App/app/cleaning_codes.py`: no edit inside any function, no reorder, no rename. Only the step 1 block is added.
- `App/app/migrations/`, `go/`, templates, CSS, `docs/context/test-map.md` (the orchestrator adds the row at review).
- Hard rules: 4 (no dependency) and 5 (no schema change; the test is Python only).

## 6. Commands

From `App/`, in this order:

1. `.venv/bin/python -c "from app import cleaning_codes as c; print(len(c.STATES), len(c.TRANSITIONS))" 2>&1 | tail -30` gives `10 10`.
2. `.venv/bin/python -m pytest tests/test_sm_cleaning_code_state.py -q --tb=short -x 2>&1 | tail -30` gives `5 passed`.
3. `.venv/bin/python -m pytest tests/test_cleaning.py -q --tb=short -x 2>&1 | tail -30` gives all passed.

From the repo root:

4. `python3 scripts/context_lint.py 2>&1 | tail -30` gives no new errors.

## 7. Acceptance

- [ ] `git diff --numstat main -- App/app/cleaning_codes.py 2>&1 | tail -30` shows `0` deletions (insertions only).
- [ ] `grep -n "TRANSITIONS\|STATES" App/app/cleaning_codes.py 2>&1 | tail -30` shows only the two definitions and comments (no use inside a function).
- [ ] The new test passes (`5 passed`).
- [ ] `tests/test_cleaning.py` passes (test-map row "Cleaning": `test_cleaning*.py`; the browser file is left to CI because nothing visual changed).
- [ ] `git diff --stat main 2>&1 | tail -30` lists only the two files in section 3.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1108-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/cleaning_codes.py`: confirm the diff is additions only.
- `App/tests/test_sm_cleaning_code_state.py`: read `PINS`. The table must match the code. For example `revoked -> revoke_pending` exists only because `remove` can re-queue a revoked ttlock code that the property still points at; the reviewer decides whether that goes to known-issues.
- Open questions to move to known-issues: eight state writes have no state guard in SQL (line numbers in the test docstring). Four rely on a Python read in the same transaction (`_activate` detach and replace, `save_manual`, `remove`); `_failure` and the final `revoked` write in `process_queue` rely on the claim made earlier by `update_if`.

## Owner steps

1. Open the pull request when the report says `review`. No deploy step, no secrets.
2. Merge it with `scripts/merge-pr-on-green.sh` once CI is green. It ships no runtime change.
