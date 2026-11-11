# 1107: declare and pin the `door_code.state` machine

Status: todo
Depends on: none | Base commit: 5e034303 | Branch: task/1107-sm-door-code-state
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [explicit state machines](../plans/explicit-state-machines.md), round 1. Brief by Opus 5.5, 2026-11-11.

## 1. Objective

Add a `STATES` tuple and a `TRANSITIONS` table to `App/app/door_codes.py` that list exactly the moves the code makes today, and a new test that reads the source and fails when any write of `door_code.state` is added, removed or changed. No runtime behaviour changes: nothing reads the new table.

## 2. Context

Rules from the plan (binding):

1. Derive, never design. The table lists exactly the moves the code makes today. Disagreements go under "Open questions"; the brief pins what the code does.
2. The table lives in the owning module, next to the state constants, named `TRANSITIONS` (as in `App/app/billing.py`).
3. One new test file per machine: `App/tests/test_sm_door_code_state.py`.
4. Writers are not edited. Every `UPDATE door_code SET state = ?` stays exactly as it is.
5. No migration, no new dependency, no template or copy change.

The state constants, `App/app/door_codes.py` lines 13 to 25 (anchor for step 2):

```python
PENDING, ISSUING, RETRYING, ISSUED, FAILED, EXPIRED = (
    "pending",
    "issuing",
    "retrying",
    "issued",
    "failed",
    "expired",
)
REVOKE_PENDING = "revoke_pending"
REVOKED = "revoked"
REVOKE_FAILED = "revoke_failed"

BACKOFF_MINUTES = (1, 5, 15, 60, 240)
```

`PERIOD_TAKEN` and `PERIOD_SHARED` in the same file are TTLock error kinds and `last_error` prefixes, not states. They are not in `STATES`.

Every write of `door_code.state` today (all in `App/app/door_codes.py`; no writer exists in any other `App/app` file, in `go/`, or through the `db.update`/`db.insert` dict helpers). Line numbers are before step 2:

| Function | Line | SQL state guard | Row is in | New state |
|---|---|---|---|---|
| `ensure_row` | 202 | INSERT | (new row) | pending |
| `issue` | 401 | `state IN (pending, retrying)` + lease | pending, retrying | issuing |
| `_release_issue_claim` | 64, 70 | none | issuing (called only from `issue` after its claim) | pending |
| `issue` | 446 | none | issuing | expired |
| `issue` | 547 | none | issuing | retrying |
| `issue` | 562 | none | issuing | issued |
| `issue` | 615, 659, 691 | none | issuing | failed or retrying (`new_state`) |
| `_keep_issued` | 727 | none | revoke_pending (from `_revoke_one`), revoke_pending or revoke_failed (from `_handle_cancellations`) | issued |
| `_revoke_one` | 758, 794, 816 | none (the claim at 738 guards `state = revoke_pending` but does not change state) | revoke_pending | revoke_failed |
| `_revoke_one` | 772 | none | revoke_pending | revoked |
| `_handle_cancellations` | 839 | none (Python `if state in (PENDING, RETRYING)` after a SELECT) | pending, retrying | revoked |
| `_handle_cancellations` | 846 | none (Python `elif state == ISSUED`) | issued | revoke_pending |
| `reconcile` | 1219 | `state = issuing` + lease older than 2 min | issuing | retrying |
| `reconcile` | 1225 | `state = issued` + `valid_to < now` | issued | expired |

`failed`, `expired` and `revoked` have no outgoing move.

How tests in this repo find files: `App/tests/test_0291_open_buttons.py` line 7: `APP = Path(__file__).resolve().parents[1]`. Tests import modules as `from app import door_codes` (`App/tests/test_door_codes_safeguards.py` line 9).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/door_codes.py` | edit | Add `STATES` and `TRANSITIONS` after `REVOKE_FAILED = "revoke_failed"` (step 2). Nothing else. |
| `App/tests/test_sm_door_code_state.py` | create | The pinning test (step 4). |
| `docs/tasks/1107-report.md` | create | The report (step 8). |

No other file may change.

## 4. Steps

1. Create the branch. From the repo root:
   `git checkout -b task/1107-sm-door-code-state 2>&1 | tail -30`
   Expected: `Switched to a new branch 'task/1107-sm-door-code-state'`.

2. Edit `App/app/door_codes.py`. Find the anchor with `grep -nF 'REVOKE_FAILED = "revoke_failed"' App/app/door_codes.py` (expected: `23:REVOKE_FAILED = "revoke_failed"`). If not found, STOP (section 8). Insert the block below on new lines directly after line 23 and before the existing blank line that precedes `BACKOFF_MINUTES = (1, 5, 15, 60, 240)`. Change nothing else in the file.

   Diff:

```diff
 REVOKE_PENDING = "revoke_pending"
 REVOKED = "revoked"
 REVOKE_FAILED = "revoke_failed"
+STATES = (
+    PENDING,
+    ISSUING,
+    RETRYING,
+    ISSUED,
+    FAILED,
+    EXPIRED,
+    REVOKE_PENDING,
+    REVOKED,
+    REVOKE_FAILED,
+)
+# Declared, not enforced: every move the code makes today (brief 1107).
+# App/tests/test_sm_door_code_state.py pins each writer against this table.
+TRANSITIONS = {
+    PENDING: {
+        ISSUING,  # issue: claim
+        REVOKED,  # _handle_cancellations: stay cancelled before a code exists
+    },
+    RETRYING: {
+        ISSUING,  # issue: claim
+        REVOKED,  # _handle_cancellations: stay cancelled before a code exists
+    },
+    ISSUING: {
+        PENDING,  # _release_issue_claim: not eligible, no account, bad window
+        EXPIRED,  # issue: the stay window has already ended
+        RETRYING,  # issue: gateway error or period taken; reconcile: lease expired
+        ISSUED,  # issue: code created on the lock
+        FAILED,  # issue: out of attempts or a permanent error
+    },
+    ISSUED: {
+        REVOKE_PENDING,  # _handle_cancellations: stay cancelled before valid_to
+        EXPIRED,  # reconcile: valid_to has passed
+    },
+    REVOKE_PENDING: {
+        ISSUED,  # _keep_issued: the stay is live again
+        REVOKED,  # _revoke_one: code deleted from the lock
+        REVOKE_FAILED,  # _revoke_one: no account, permanent error, or past valid_to
+    },
+    REVOKE_FAILED: {
+        ISSUED,  # _keep_issued: the stay is live again
+    },
+    FAILED: set(),
+    EXPIRED: set(),
+    REVOKED: set(),
+}
 
 BACKOFF_MINUTES = (1, 5, 15, 60, 240)
```

   The added lines, without diff markers, for copying:

```python
STATES = (
    PENDING,
    ISSUING,
    RETRYING,
    ISSUED,
    FAILED,
    EXPIRED,
    REVOKE_PENDING,
    REVOKED,
    REVOKE_FAILED,
)
# Declared, not enforced: every move the code makes today (brief 1107).
# App/tests/test_sm_door_code_state.py pins each writer against this table.
TRANSITIONS = {
    PENDING: {
        ISSUING,  # issue: claim
        REVOKED,  # _handle_cancellations: stay cancelled before a code exists
    },
    RETRYING: {
        ISSUING,  # issue: claim
        REVOKED,  # _handle_cancellations: stay cancelled before a code exists
    },
    ISSUING: {
        PENDING,  # _release_issue_claim: not eligible, no account, bad window
        EXPIRED,  # issue: the stay window has already ended
        RETRYING,  # issue: gateway error or period taken; reconcile: lease expired
        ISSUED,  # issue: code created on the lock
        FAILED,  # issue: out of attempts or a permanent error
    },
    ISSUED: {
        REVOKE_PENDING,  # _handle_cancellations: stay cancelled before valid_to
        EXPIRED,  # reconcile: valid_to has passed
    },
    REVOKE_PENDING: {
        ISSUED,  # _keep_issued: the stay is live again
        REVOKED,  # _revoke_one: code deleted from the lock
        REVOKE_FAILED,  # _revoke_one: no account, permanent error, or past valid_to
    },
    REVOKE_FAILED: {
        ISSUED,  # _keep_issued: the stay is live again
    },
    FAILED: set(),
    EXPIRED: set(),
    REVOKED: set(),
}
```

3. Check the module still imports. From `App/`:
   `.venv/bin/python -c "from app import door_codes; print(len(door_codes.STATES), len(door_codes.TRANSITIONS))" 2>&1 | tail -30`
   Expected: `9 9`. Then commit: `git add App/app/door_codes.py && git commit -m "1107 step 2" 2>&1 | tail -5`.

4. Create `App/tests/test_sm_door_code_state.py` with exactly this content:

```python
"""1107: door_code.state is pinned to door_codes.TRANSITIONS.

Reads every writer of door_code.state as source text and compares each write
with PINNED. A write that is added, removed or changed fails this test, and
so does a pinned move that door_codes.TRANSITIONS does not list. Writers are
located by enclosing function name, never by line number.
"""
from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

from app import door_codes

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
SOURCE = APP / "app" / "door_codes.py"

ANY = "any"  # the SQL has no state guard in its WHERE clause
NEW = "new"  # INSERT: the row is created

# (function, SQL guard states or ANY/NEW, states the row is in when the write
# runs, new states). For a guarded write the third field equals the guard.
# For an unguarded write it is the state the function holds through its own
# earlier claim or SELECT; see brief 1107 "Open questions".
PINNED = [
    ("_release_issue_claim", ANY, ("issuing",), ("pending",)),
    ("_release_issue_claim", ANY, ("issuing",), ("pending",)),
    ("ensure_row", NEW, (), ("pending",)),
    ("issue", ("pending", "retrying"), ("pending", "retrying"), ("issuing",)),
    ("issue", ANY, ("issuing",), ("expired",)),
    ("issue", ANY, ("issuing",), ("retrying",)),
    ("issue", ANY, ("issuing",), ("issued",)),
    ("issue", ANY, ("issuing",), ("failed", "retrying")),
    ("issue", ANY, ("issuing",), ("failed", "retrying")),
    ("issue", ANY, ("issuing",), ("failed", "retrying")),
    ("_keep_issued", ANY, ("revoke_failed", "revoke_pending"), ("issued",)),
    ("_revoke_one", ANY, ("revoke_pending",), ("revoke_failed",)),
    ("_revoke_one", ANY, ("revoke_pending",), ("revoked",)),
    ("_revoke_one", ANY, ("revoke_pending",), ("revoke_failed",)),
    ("_revoke_one", ANY, ("revoke_pending",), ("revoke_failed",)),
    ("_handle_cancellations", ANY, ("pending", "retrying"), ("revoked",)),
    ("_handle_cancellations", ANY, ("issued",), ("revoke_pending",)),
    ("reconcile", ("issuing",), ("issuing",), ("retrying",)),
    ("reconcile", ("issued",), ("issued",), ("expired",)),
]

WRITE_RE = re.compile(r"\b(UPDATE\s+door_code\s+SET|INSERT\s+INTO\s+door_code\b)", re.I)
UPDATE_RE = re.compile(r"UPDATE\s+door_code\s+SET\s+(?P<set>.*?)(?:\s+WHERE\s+(?P<where>.*))?$", re.I | re.S)
SET_STATE_RE = re.compile(r"(?:^|,)\s*state\s*=\s*(?P<value>[^,]+)", re.I)
GUARD_RE = re.compile(r"\bstate\s*(?:=\s*(?P<one>\?|'[^']*')|IN\s*\((?P<many>[^)]*)\))", re.I)
INSERT_RE = re.compile(r"INSERT\s+INTO\s+door_code\s*\((?P<cols>[^)]*)\)", re.I)


def _state_names() -> dict:
    return {
        name: value
        for name, value in vars(door_codes).items()
        if name.isupper() and isinstance(value, str) and value in door_codes.STATES
    }


def _sql_text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, False
    if isinstance(node, ast.JoinedStr):
        parts = [v.value if isinstance(v, ast.Constant) else "{}" for v in node.values]
        return "".join(parts), True
    return None, False


def _resolver(func: ast.AST, names: dict):
    assigned: dict = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            for target in node.targets:
                if isinstance(target, ast.Name) and node.value.id in names:
                    assigned.setdefault(target.id, set()).add(names[node.value.id])

    def resolve(node) -> set:
        if isinstance(node, ast.Name):
            if node.id in names:
                return {names[node.id]}
            if node.id in assigned:
                return set(assigned[node.id])
        return {"?"}

    return resolve


def _param(params, index: int, resolve) -> set:
    if params is None or index >= len(params):
        return {"?"}
    return resolve(params[index])


def _parse_update(sql: str, params, resolve):
    match = UPDATE_RE.search(sql)
    if not match:
        return None
    set_clause = match.group("set")
    state_set = SET_STATE_RE.search(set_clause)
    if not state_set:
        return None
    value = state_set.group("value").strip()
    if value == "?":
        index = sql[: match.start("set") + state_set.end("value")].count("?") - 1
        to = _param(params, index, resolve)
    else:
        to = {"literal:" + value}
    where = match.group("where")
    guard = GUARD_RE.search(where) if where else None
    if not guard:
        return ANY, to
    index = sql[: match.start("where") + guard.start()].count("?")
    raw = guard.group("one") or guard.group("many")
    states: set = set()
    for item in raw.split(","):
        item = item.strip()
        if item == "?":
            states |= _param(params, index, resolve)
            index += 1
        else:
            states.add(item.strip("'"))
    return tuple(sorted(states)), to


def _parse_insert(sql: str, params, resolve, names: dict):
    match = INSERT_RE.search(sql)
    if not match:
        return None
    if "DO UPDATE" in sql.upper():
        return NEW, {"?"}
    cols = [c.strip() for c in match.group("cols").split(",")]
    if "state" not in cols:
        return NEW, {"default"}
    found = set()
    for node in params or ():
        if isinstance(node, ast.Name) and node.id in names:
            found.add(names[node.id])
    return NEW, found or {"?"}


def _writes_in(path: Path) -> list:
    """Every statement in ``path`` that writes door_code.state."""
    names = _state_names()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for top in tree.body:
        func_name = top.name if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)) else "<module>"
        resolve = _resolver(top, names)
        for node in ast.walk(top):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            sql, is_fstring = _sql_text(node.args[0])
            if sql is None or not WRITE_RE.search(sql):
                continue
            params = None
            if len(node.args) > 1 and isinstance(node.args[1], (ast.Tuple, ast.List)):
                params = node.args[1].elts
            parsed = _parse_update(sql, params, resolve) or _parse_insert(sql, params, resolve, names)
            if parsed is None:
                continue
            guard, to = parsed
            if is_fstring:
                to = {"f-string"}
            out.append((func_name, guard, tuple(sorted(to))))
    return out


def _pinned_writes() -> Counter:
    return Counter(
        (func, guard if isinstance(guard, str) else tuple(sorted(guard)), tuple(sorted(to)))
        for func, guard, _held, to in PINNED
    )


def test_every_state_write_in_door_codes_is_pinned():
    found = Counter(_writes_in(SOURCE))
    expected = _pinned_writes()
    assert found - expected == Counter(), f"unpinned writes: {sorted((found - expected).elements())}"
    assert expected - found == Counter(), f"pinned writes not found: {sorted((expected - found).elements())}"


def test_no_update_statement_is_missed():
    text = SOURCE.read_text(encoding="utf-8")
    in_text = len(re.findall(r"UPDATE\s+door_code\s+SET", text))
    tree = ast.parse(text)
    in_ast = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and re.search(r"UPDATE\s+door_code\s+SET", node.args[0].value)
    )
    assert in_text == in_ast


def test_no_other_python_file_writes_door_code_state():
    others = []
    for path in sorted((APP / "app").rglob("*.py")):
        if path == SOURCE:
            continue
        for write in _writes_in(path):
            others.append((str(path.relative_to(REPO)), write))
    assert others == []


def test_no_dict_helper_writes_door_code():
    helper = re.compile(
        r"\b(?:update|update_if|update_in|insert|insert_in)\(\s*(?:cur\s*,\s*)?['\"]door_code['\"]"
    )
    hits = [
        str(path.relative_to(REPO))
        for path in sorted((APP / "app").rglob("*.py"))
        if helper.search(path.read_text(encoding="utf-8"))
    ]
    assert hits == []


def test_no_go_file_writes_door_code():
    pattern = re.compile(r"\b(UPDATE\s+door_code\s+SET|INSERT\s+INTO\s+door_code\b)", re.I)
    hits = [
        str(path.relative_to(REPO))
        for path in sorted((REPO / "go").rglob("*.go"))
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert hits == []


def test_every_pinned_move_is_in_transitions():
    for func, _guard, held, to in PINNED:
        for old in held:
            for new in to:
                assert new in door_codes.TRANSITIONS.get(old, set()), f"{func}: {old} -> {new}"


def test_transitions_list_exactly_the_pinned_moves():
    pinned = {(old, new) for _f, _g, held, to in PINNED for old in held for new in to}
    table = {(old, new) for old, targets in door_codes.TRANSITIONS.items() for new in targets}
    assert table == pinned


def test_states_match_the_constants_and_the_table():
    assert door_codes.STATES == (
        door_codes.PENDING,
        door_codes.ISSUING,
        door_codes.RETRYING,
        door_codes.ISSUED,
        door_codes.FAILED,
        door_codes.EXPIRED,
        door_codes.REVOKE_PENDING,
        door_codes.REVOKED,
        door_codes.REVOKE_FAILED,
    )
    assert set(door_codes.TRANSITIONS) == set(door_codes.STATES)
    for targets in door_codes.TRANSITIONS.values():
        assert set(targets) <= set(door_codes.STATES)
    for _f, _g, held, to in PINNED:
        assert set(held) <= set(door_codes.STATES)
        assert set(to) <= set(door_codes.STATES)


def test_every_state_is_reachable_from_pending():
    seen = {door_codes.PENDING}
    todo = [door_codes.PENDING]
    while todo:
        for new in door_codes.TRANSITIONS[todo.pop()]:
            if new not in seen:
                seen.add(new)
                todo.append(new)
    assert seen == set(door_codes.STATES)


def test_table_is_not_used_at_runtime():
    text = SOURCE.read_text(encoding="utf-8")
    assert len(re.findall(r"\bTRANSITIONS\b", text)) == 1
    assert len(re.findall(r"\bSTATES\b", text)) == 1
    users = [
        str(path.relative_to(REPO))
        for path in sorted((APP / "app").rglob("*.py"))
        if re.search(r"door_codes\.(?:TRANSITIONS|STATES)\b", path.read_text(encoding="utf-8"))
    ]
    assert users == []
```

5. Run the new test. From `App/`:
   `.venv/bin/python -m pytest tests/test_sm_door_code_state.py -q --tb=short -x 2>&1 | tail -30`
   Expected: `10 passed`. Then commit: `git add App/tests/test_sm_door_code_state.py && git commit -m "1107 step 4" 2>&1 | tail -5`.

6. Run the existing door-code tests (test-map row "Door codes, TTLock"). From `App/`:
   `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py -q --tb=short -x 2>&1 | tail -30`
   Expected: all pass, 0 failed. (Skips in `test_door_code_window_browser.py` are not caused by this brief; write them in the report, do not fix them.)

7. Run the context lint. From the repo root:
   `python3 scripts/context_lint.py 2>&1 | tail -30`
   Expected: no errors.

8. Write `docs/tasks/1107-report.md` (section 9), set this brief to `Status: review`, commit with message `1107 report`, and open one draft PR from `task/1107-sm-door-code-state`.

## 5. Do not touch

- Every `db.execute(...)` in `App/app/door_codes.py`: no writer, WHERE clause, lease or parameter may change (plan rule 4).
- Any other file under `App/app/`, `go/`, `App/app/migrations/`, `docs/context/test-map.md` (the orchestrator adds the test-map row at review).
- AGENTS.md hard rules 3 (no secrets), 4 (no new dependency), 5 (no schema change), 8 (never push to `main`).

## 6. Commands

From `App/`:

- `.venv/bin/python -c "from app import door_codes; print(len(door_codes.STATES), len(door_codes.TRANSITIONS))" 2>&1 | tail -30` prints `9 9`.
- `.venv/bin/python -m pytest tests/test_sm_door_code_state.py -q --tb=short -x 2>&1 | tail -30` prints `10 passed`.
- `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py -q --tb=short -x 2>&1 | tail -30` prints 0 failed.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` prints no errors.

## 7. Acceptance

- [ ] `git diff --stat 5e034303` lists only `App/app/door_codes.py` (insertions only, 0 deletions), `App/tests/test_sm_door_code_state.py`, `docs/tasks/1107-*.md`.
- [ ] `grep -c "door_code SET state = ?" App/app/door_codes.py` prints `18`, the same as before step 2.
- [ ] `tests/test_sm_door_code_state.py`: 10 passed.
- [ ] Test-map row "Door codes, TTLock": 0 failed.
- [ ] Context lint: no errors.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice (do not change `PINNED` or `TRANSITIONS` to make it pass: a mismatch means the source differs from this brief, so report the failing assertion);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1107-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Open questions (for the orchestrator and owner; the executor does nothing here)

Round 1 pins these as the code is. Each is an unguarded write: the SQL is `WHERE id = ?` with no state condition, so it moves the row from whatever state it is in at that moment. Line numbers are before step 2.

1. `App/app/door_codes.py:64` and `:70` `_release_issue_claim` -> pending. Relies on `issue`'s claim lease.
2. `App/app/door_codes.py:446` `issue` -> expired; `:547` -> retrying; `:562` -> issued; `:615`, `:659`, `:691` -> failed or retrying. All rely on the 2-minute claim lease from line 401. If a TTLock call outlives the lease, `reconcile` (line 1219) sets retrying and another worker may claim the row; the late write then overwrites that worker's state.
3. `App/app/door_codes.py:727` `_keep_issued` -> issued. Called after a SELECT of revoke_pending/revoke_failed (line 858) and inside `_revoke_one` after its claim.
4. `App/app/door_codes.py:758`, `:794`, `:816` `_revoke_one` -> revoke_failed; `:772` -> revoked. Rely on the claim at line 738, which guards `state = revoke_pending` but keeps the state.
5. `App/app/door_codes.py:839` `_handle_cancellations` -> revoked and `:846` -> revoke_pending. Read-then-write: the state check is in Python after a SELECT. A row that `issue` claims (issuing) between the SELECT and the UPDATE is set to revoked while `issue` continues; `issue`'s line-562 write can then set it back to issued (the next reconcile moves issued to revoke_pending, so it heals, one run later).
6. Not state writes, not pinned: `_handle_cancellations` deletes revoked rows whose stay is active again (line 884), and `ensure_row` later recreates them as pending; `App/app/retention.py:355` deletes rows on account deletion.
7. No doc describes this machine, so there is no doc disagreement to list.

## Risk list (for the reviewer)

- `App/app/door_codes.py`: the diff must be insertions only, between `REVOKE_FAILED = "revoke_failed"` and `BACKOFF_MINUTES`.
- `App/tests/test_sm_door_code_state.py`: `PINNED` must match the table in section 2.

## Owner steps

None. The orchestrator reviews the PR and merges with `scripts/merge-pr-on-green.sh` when it is green.
