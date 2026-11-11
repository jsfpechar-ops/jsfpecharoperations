# 1109: declare and pin the `reservation_claim.state` machine

Status: review
Depends on: none | Base commit: 7aba5d5e | Branch: task/1109-sm-reservation-claim-state
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Plan: [explicit state machines](../plans/explicit-state-machines.md), round 1. Brief by Opus 5.5, 2026-11-11.

## 1. Objective

Add a `TRANSITIONS` table to `App/app/claim.py` that lists every move `reservation_claim.state` makes today, and a test that fails when a write of that column is added, removed or changed. The claim state decides which guest may see and edit a stay's guest data, so this is access control: **no runtime behaviour may change**, and nothing may read the new table.

## 2. Context

Plan rules that bind this brief (from `docs/plans/explicit-state-machines.md`, "Rules for every brief"):

1. Derive, never design. The table lists exactly the moves the code makes today.
2. The table lives in the owning module, next to the state constants, named `TRANSITIONS`.
3. One new test file: `App/tests/test_sm_reservation_claim_state.py`.
4. Writers are not edited. No read-then-write is introduced. Go files are read by the test, never changed.
5. No migration, no new dependency, no template or copy change.

The schema, `App/app/db.py` (do not edit):

```
CREATE TABLE IF NOT EXISTS reservation_claim (
    reservation_id          INTEGER PRIMARY KEY REFERENCES reservation(id) ON DELETE CASCADE,
    state                   TEXT NOT NULL DEFAULT 'unclaimed'
        CHECK (state IN ('unclaimed', 'provisional', 'claimed')),
```

The constants, `App/app/claim.py` lines 15 to 18 (the anchor for step 2):

```
UNCLAIMED = "unclaimed"
PROVISIONAL = "provisional"
CLAIMED = "claimed"
HOLD_MINUTES = 30
```

The five statements that write the state today, all in `App/app/claim.py` (line numbers before step 2; step 2 moves them down by 21). The orchestrator found them by grepping `reservation_claim` across `App/app` (including `routes/`, `guest_handoff.py`, `guest_draft.py`, `dsr.py`, `retention.py`, `icalsync.py`), `go/` and the SQL migrations. The other writers of the table (`fee_update.py`, `retention.py`, `lock_guest_access`, `reopen_guest_access`, `expire_on_cancel`, `maybe_notify_completion`, the `declared_guests` reset in `confirm`, and Go `go/internal/ical/reconcile.go` `expireOnCancel` and the reopen at line 406) do not touch `state`.

| Function | Line | Statement (shortened) | WHERE state guard | Move |
|---|---|---|---|---|
| `ensure_row` | 88 | `db.insert("reservation_claim", {"state": UNCLAIMED, ...})` | row is new | none to unclaimed |
| `expire_holds` | 115 | `UPDATE reservation_claim SET state = ? ... WHERE reservation_id = ? AND state = ?` with `(UNCLAIMED, ..., PROVISIONAL)` | `state = PROVISIONAL` | provisional to unclaimed |
| `start_claim` | 280 | `UPDATE reservation_claim SET state = ? ... WHERE reservation_id = ?` with `PROVISIONAL if claim["state"] != CLAIMED else CLAIMED` | none | unclaimed or provisional to provisional; claimed to claimed |
| `confirm` | 693 | `UPDATE reservation_claim SET state = ? ... AND state IN (?, ?)` with `(CLAIMED, ..., PROVISIONAL, CLAIMED)` | `state IN (PROVISIONAL, CLAIMED)` | provisional to claimed; claimed to claimed |
| `release` | 739 | `UPDATE reservation_claim SET state = ? ... WHERE reservation_id = ?` with `(UNCLAIMED, now, now, reservation_id)` | none | any to unclaimed |

### Open questions (for the reviewer and owner; the executor does nothing about them)

- `App/app/claim.py:280` (`start_claim`): the WHERE clause has no state condition, so it is pinned as from-any. The caller-side check is a read earlier in the same function (`claim = ensure_row(...)`, then the `claim["state"]` branches), not a lock: if `confirm` commits CLAIMED between that read and this write, the write can put a claimed row back to `provisional`. That race move (claimed to provisional) is not in the table because no code path intends it.
- `App/app/claim.py:739` (`release`): the WHERE clause has no state condition, pinned as from-any. Its only caller, `reservation_release_claim` in `App/app/routes/admin.py` (around line 4343), checks login and that the host owns the stay (`access.reservation`), but not the claim state; so release from `unclaimed` also happens (it bumps `token_version`).

How existing source-reading tests find files (from `App/tests/test_wp07_cache_heartbeats.py`): `Path(__file__).resolve().parent.parent / "app" / ...`. The new test does the same; `go/` is one level above `App/`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/claim.py` | edit | add `TRANSITIONS` directly after `CLAIMED = "claimed"` (step 2) |
| `App/tests/test_sm_reservation_claim_state.py` | create | the pin test (step 4) |
| `docs/tasks/1109-report.md` | create | the report (step 8) |
| `docs/tasks/1109-sm-reservation-claim-state.md` | edit | `Status:` line only (step 8) |

No other file may change.

## 4. Steps

All commands run from `App/` unless the step says otherwise.

### Step 1. Branch

From the repo root:

```
git checkout -b task/1109-sm-reservation-claim-state 2>&1 | tail -30
```

Expected: `Switched to a new branch 'task/1109-sm-reservation-claim-state'`.

### Step 2. Add the table to `App/app/claim.py`

Find the anchor:

```
grep -nF 'CLAIMED = "claimed"' app/claim.py 2>&1 | tail -30
```

Expected: exactly one line, `17:CLAIMED = "claimed"`. If not exactly one line, STOP (§8).

Apply this diff. Insert the added lines directly after line 17 and before `HOLD_MINUTES = 30`. Change nothing else.

```diff
 UNCLAIMED = "unclaimed"
 PROVISIONAL = "provisional"
 CLAIMED = "claimed"
+# Every state move the code makes today (brief 1109), derived from the writers
+# and pinned by tests/test_sm_reservation_claim_state.py. Nothing reads this at
+# runtime. None means "no row yet".
+TRANSITIONS = {
+    None: {
+        UNCLAIMED,  # ensure_row: the first INSERT
+    },
+    UNCLAIMED: {
+        PROVISIONAL,  # start_claim: a link is sent
+        UNCLAIMED,  # release: no state check
+    },
+    PROVISIONAL: {
+        PROVISIONAL,  # start_claim: guest resend, or another address after the takeover window
+        CLAIMED,  # confirm
+        UNCLAIMED,  # expire_holds; release
+    },
+    CLAIMED: {
+        CLAIMED,  # start_claim: resend to the verified address; confirm of that link
+        UNCLAIMED,  # release
+    },
+}
 HOLD_MINUTES = 30
```

The word `TRANSITIONS` must appear exactly once in `app/claim.py` (the test checks this). Check:

```
grep -c "TRANSITIONS" app/claim.py 2>&1 | tail -30
.venv/bin/python -c "from app import claim; print(sorted((str(k), sorted(v)) for k, v in claim.TRANSITIONS.items()))" 2>&1 | tail -30
```

Expected: `1`, then
`[('None', ['unclaimed']), ('claimed', ['claimed', 'unclaimed']), ('provisional', ['claimed', 'provisional', 'unclaimed']), ('unclaimed', ['provisional', 'unclaimed'])]`.

Commit: `git add app/claim.py && git commit -m "1109 step 2" 2>&1 | tail -30`.

### Step 3. Confirm no writer changed

```
git diff HEAD~1 --stat 2>&1 | tail -30
```

Expected: one file, `App/app/claim.py | 21 +`, insertions only. Any deletion: STOP (§8).

### Step 4. Create `App/tests/test_sm_reservation_claim_state.py`

Create the file with exactly this content:

```python
"""Brief 1109: pin every write of ``reservation_claim.state``.

The claim state decides which guest may see and edit a stay's guest data, so
it is access control. This test reads every writer source (Python, Go and the
SQL migrations) as text, finds each statement that writes the column, and
compares them with the pinned lists below. It fails when a write is added,
removed or changed, and when a pinned move is missing from
``claim.TRANSITIONS``. It changes no runtime behaviour.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from app import claim

APP_DIR = Path(__file__).resolve().parent.parent  # App/
REPO = APP_DIR.parent
PY_ROOT = APP_DIR / "app"
GO_ROOT = REPO / "go"
SQL_ROOTS = (APP_DIR / "app" / "migrations", APP_DIR / "migrations_pg")

ANY = ("claimed", "provisional", "unclaimed")
INSERT = ("(insert)",)
STATE_NAMES = {"UNCLAIMED": "unclaimed", "PROVISIONAL": "provisional", "CLAIMED": "claimed"}

# One entry per statement that writes reservation_claim.state:
# (file, enclosing function, states its WHERE clause allows, states it writes).
# INSERT: the statement creates the row. ANY: the WHERE clause has no state
# condition (brief 1109, "Open questions").
PINNED_WRITES = [
    ("App/app/claim.py", "ensure_row", INSERT, ("unclaimed",)),
    ("App/app/claim.py", "expire_holds", ("provisional",), ("unclaimed",)),
    ("App/app/claim.py", "start_claim", ANY, ("claimed", "provisional")),
    ("App/app/claim.py", "confirm", ("claimed", "provisional"), ("claimed",)),
    ("App/app/claim.py", "release", ANY, ("unclaimed",)),
]

# The moves those writes make: (file, function, from-states, to-state).
# None as a from-state means "no row yet". start_claim has no state condition
# in its WHERE clause: its from-states are the ones its Python checks let
# through before the write.
PINNED_MOVES = [
    ("App/app/claim.py", "ensure_row", (None,), "unclaimed"),
    ("App/app/claim.py", "expire_holds", ("provisional",), "unclaimed"),
    ("App/app/claim.py", "start_claim", ("unclaimed", "provisional"), "provisional"),
    ("App/app/claim.py", "start_claim", ("claimed",), "claimed"),
    ("App/app/claim.py", "confirm", ("provisional", "claimed"), "claimed"),
    ("App/app/claim.py", "release", ("unclaimed", "provisional", "claimed"), "unclaimed"),
]

_WRITE_SQL = re.compile(
    r"\b(?:UPDATE\s+reservation_claim\s+SET|INSERT\s+INTO\s+reservation_claim)\b", re.I
)
_STATE_SET = re.compile(r"(?<![\w.])state\s*=", re.I)
_STATE_WHERE = re.compile(r"(?<![\w.])state\s*(?:=\s*\?|IN\s*\([^)]*\))", re.I)
_WHERE = re.compile(r"\bWHERE\b", re.I)


def _text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            v.value if isinstance(v, ast.Constant) else "{}" for v in node.values
        )
    return None


def _states(node) -> tuple:
    """The claim states an argument can carry: the constants named in it."""
    found = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in STATE_NAMES:
            found.add(STATE_NAMES[sub.id])
        elif isinstance(sub, ast.Attribute) and sub.attr in STATE_NAMES:
            found.add(STATE_NAMES[sub.attr])
        elif isinstance(sub, ast.Constant) and sub.value in ANY:
            found.add(sub.value)
    return tuple(sorted(found))


def _sets_state(sql: str) -> bool:
    if not _WRITE_SQL.search(sql):
        return False
    if re.search(r"\bINSERT\b", sql, re.I):
        return True
    return bool(_STATE_SET.search(_WHERE.split(sql, 1)[0]))


def _sql_write(call: ast.Call):
    """(guard, to-states) for ``execute(sql, params)`` writing the state, else None."""
    if not call.args:
        return None
    sql = _text(call.args[0])
    if sql is None or not _sets_state(sql):
        return None
    params = call.args[1] if len(call.args) > 1 else None
    elts = params.elts if isinstance(params, (ast.Tuple, ast.List)) else None
    if re.search(r"\bINSERT\b", sql, re.I):
        return INSERT, (_states(params) if params is not None else ("unclaimed",))
    set_part = _WHERE.split(sql, 1)[0]
    match = _STATE_SET.search(set_part)
    index = set_part[: match.start()].count("?")
    to = _states(elts[index]) if elts is not None and index < len(elts) else ("?",)
    where_at = len(set_part)
    guard = _STATE_WHERE.search(sql, where_at)
    if guard is None:
        return ANY, to
    first = sql[: guard.start()].count("?")
    count = guard.group(0).count("?")
    if elts is None:
        return ("?",), to
    allowed = set()
    for elt in elts[first:first + count]:
        allowed.update(_states(elt))
    return tuple(sorted(allowed)), to


def _helper_write(call: ast.Call):
    """(guard, to-states) for ``db.insert("reservation_claim", {...})`` and the
    other db.py dict helpers, else None."""
    if not any(_text(a) == "reservation_claim" for a in call.args[:2]):
        return None
    values = next((a for a in call.args if isinstance(a, ast.Dict)), None)
    state = None
    if values is not None:
        for key, value in zip(values.keys, values.values):
            if key is not None and _text(key) == "state":
                state = value
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if name.startswith("insert"):
        return INSERT, (_states(state) if state is not None else ("unclaimed",))
    if state is None:
        return None
    return ("(helper)",), _states(state)


def _scan(node, func, rel, found, consumed):
    for child in ast.iter_child_nodes(node):
        inner = func
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inner = child.name
        if isinstance(child, ast.Call):
            write = _sql_write(child)
            if write is not None:
                consumed.append(id(child.args[0]))
            else:
                write = _helper_write(child)
            if write is not None:
                found.append((rel, func, write[0], write[1]))
        _scan(child, inner, rel, found, consumed)


def _python_writes():
    found, strays = [], []
    for path in sorted(PY_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        consumed = []
        _scan(tree, "<module>", rel, found, consumed)
        for node in ast.walk(tree):
            sql = _text(node) if isinstance(node, (ast.Constant, ast.JoinedStr)) else None
            if sql and _sets_state(sql) and id(node) not in consumed:
                strays.append((rel, sql[:80]))
    return found, strays


def _python_claim_update_count() -> int:
    """How many UPDATE reservation_claim statements the Python sources hold."""
    n = 0
    for path in sorted(PY_ROOT.rglob("*.py")):
        n += len(re.findall(r"UPDATE reservation_claim SET", path.read_text(encoding="utf-8")))
    return n


_GO_FUNC = re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)", re.M)


def _go_writes():
    found, seen = [], 0
    for path in sorted(GO_ROOT.rglob("*.go")):
        if path.name.endswith("_test.go"):
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO).as_posix()
        for match in _WRITE_SQL.finditer(text):
            seen += 1
            end = text.find("`", match.start())
            sql = text[match.start(): end if end != -1 else match.start() + 600]
            if not _sets_state(sql):
                continue
            funcs = [m.group(1) for m in _GO_FUNC.finditer(text, 0, match.start())]
            found.append((rel, funcs[-1] if funcs else "<file>", sql[:80]))
    return found, seen


def _norm_writes(rows):
    return sorted((f, fn, tuple(sorted(g)), tuple(sorted(t))) for f, fn, g, t in rows)


def test_python_writes_match_pin():
    found, _ = _python_writes()
    assert _norm_writes(found) == _norm_writes(PINNED_WRITES)


def test_no_state_sql_outside_a_readable_call():
    # SQL held in a variable, or built where the scanner cannot see its
    # parameters, would escape the pin above.
    _, strays = _python_writes()
    assert strays == []


def test_scanner_sees_claim_updates():
    # Guard against a scanner that silently finds nothing: claim.py alone has
    # UPDATE statements that set the state and others that do not.
    assert _python_claim_update_count() > len(PINNED_WRITES)


def test_go_writes_no_claim_state():
    found, seen = _go_writes()
    assert seen >= 1, "the Go scan found no reservation_claim write at all"
    assert found == []


def test_sql_migrations_write_no_claim_state():
    hits = []
    for root in SQL_ROOTS:
        for path in sorted(root.glob("*.sql")):
            for stmt in path.read_text(encoding="utf-8").split(";"):
                if _sets_state(stmt):
                    hits.append(path.name)
    assert hits == []


def test_moves_match_writes():
    writes = {}
    for f, fn, guard, to in PINNED_WRITES:
        writes[(f, fn)] = (guard, set(to))
    moves = {}
    for f, fn, frm, to in PINNED_MOVES:
        moves.setdefault((f, fn), []).append((frm, to))
    assert set(moves) == set(writes)
    for key, (guard, to) in writes.items():
        assert {t for _, t in moves[key]} == to, key
        allowed = {None} if guard == INSERT else set(guard)
        for frm, _ in moves[key]:
            assert set(frm) <= allowed, key


def test_pinned_moves_are_in_transitions():
    for f, fn, frm, to in PINNED_MOVES:
        for state in frm:
            assert to in claim.TRANSITIONS.get(state, set()), (fn, state, to)


def test_transitions_list_only_pinned_moves():
    pinned = {(state, to) for _, _, frm, to in PINNED_MOVES for state in frm}
    table = {(state, to) for state, tos in claim.TRANSITIONS.items() for to in tos}
    assert table == pinned


def test_states_match_constants():
    assert {claim.UNCLAIMED, claim.PROVISIONAL, claim.CLAIMED} == set(ANY)
    states = {s for s in claim.TRANSITIONS if s is not None}
    for tos in claim.TRANSITIONS.values():
        states |= set(tos)
    assert states == set(ANY)
    schema = (PY_ROOT / "db.py").read_text(encoding="utf-8")
    assert "CHECK (state IN ('unclaimed', 'provisional', 'claimed'))" in schema


def test_transitions_not_used_at_runtime():
    # Round 1 declares the table only; nothing may read it yet.
    own = (PY_ROOT / "claim.py").read_text(encoding="utf-8")
    assert own.count("TRANSITIONS") == 1
    for path in sorted(PY_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"claim\.TRANSITIONS|from \.claim import[^\n]*TRANSITIONS", text), path
```

Commit: `git add tests/test_sm_reservation_claim_state.py && git commit -m "1109 step 4" 2>&1 | tail -30`.

### Step 5. Run the new test

```
.venv/bin/python -m pytest tests/test_sm_reservation_claim_state.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `10 passed`. If a test fails, read the assertion once. Do not change the pinned lists to make it pass, and do not edit any writer: a mismatch means the code differs from this brief, so STOP (§8) and paste the failing output in the report.

### Step 6. Run the existing claim tests

```
.venv/bin/python -m pytest tests/test_claim_*.py -q --tb=short -x 2>&1 | tail -30
```

Expected: all passed, 0 failed.

### Step 7. Context lint

From the repo root:

```
python3 scripts/context_lint.py 2>&1 | tail -30
```

Expected: no errors.

### Step 8. Report

Write `docs/tasks/1109-report.md` per §9, set this brief's line `Status: todo` to `Status: review`, commit with `1109 step 8`, and open one draft PR. Do not merge.

## 5. Do not touch

- Every writer: the SQL and the function bodies in `App/app/claim.py`, `App/app/routes/admin.py`, and all of `go/`. Only the 21 added lines in step 2 may change in `claim.py`.
- `App/app/db.py`, migrations, templates, copy, `docs/context/test-map.md` (the orchestrator adds the row at review).
- Hard rules from AGENTS.md: 3 (public repo, no guest data in output), 4 (no new dependency), 5 (no schema change), 8 (never push to `main`; no merge).

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_sm_reservation_claim_state.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `10 passed`.

```
.venv/bin/python -m pytest tests/test_claim_*.py -q --tb=short -x 2>&1 | tail -30
```

Expected: all passed (test-map row "Filing, UbyPort, worker, claim", the `test_claim_*.py` part).

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`, expected no errors.

## 7. Acceptance

- [ ] `git diff origin/main --stat` lists only `App/app/claim.py` (21 insertions, 0 deletions), `App/tests/test_sm_reservation_claim_state.py`, `docs/tasks/1109-report.md` and this brief.
- [ ] `grep -c TRANSITIONS App/app/claim.py` prints `1`.
- [ ] `grep -rn "claim.TRANSITIONS" App/app` prints nothing.
- [ ] `tests/test_sm_reservation_claim_state.py`: 10 passed.
- [ ] `tests/test_claim_*.py`: all passed (command in §6).
- [ ] Context lint: no errors.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice, or any test in step 5 fails at all (the pin must match the code as it is);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1109-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/claim.py`: the diff must be the 21 added lines only; any change to a writer is a behaviour change to guest-data access.
- `App/tests/test_sm_reservation_claim_state.py`: the pinned lists must match §2; the two "Open questions" stay open for the owner.

## Owner steps

1. Read the two "Open questions" in §2 and say whether either should become a later brief (a state guard in `start_claim`, a state check before `release`).
2. When the PR is green and the reviewer approves, merge it with `scripts/merge-pr-on-green.sh`.
