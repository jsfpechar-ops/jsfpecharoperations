# 1105: Declare and pin the guest.submit_state transitions

Status: todo
Depends on: none | Base commit: 5e034303 | Branch: task/1105-sm-guest-submit-state
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**HIGH RISK: police filing.** This brief changes no runtime behaviour. You add one inert dict and one test file. You do not edit any writer, any Go file, or any line of `App/app/reporting.py` other than the one insertion in step 2.

## 1. Objective

Add a `TRANSITIONS` dict to `App/app/reporting.py` that lists every move of `guest.submit_state` the code makes today, and a test, `App/tests/test_sm_guest_submit_state.py`, that reads every Python and Go writer as text and fails when a write is added, removed or changed, or when the table and the writers disagree. Nobody can read the legal filing moves in one place today; after this, CI does ([plan](../plans/explicit-state-machines.md), round 1: declare and pin).

## 2. Context

Plan rules that bind this brief: the table lists exactly the moves the code makes today (derive, never design); it lives in the owning module next to the state constants, named `TRANSITIONS`; writers are not edited, Go files are read and never changed; no migration, no dependency, no template or copy change. Nothing may read `TRANSITIONS` at runtime.

Excerpts. Each must exist verbatim; if one is not found, STOP (section 8).

`App/app/reporting.py` (lines 46-51), the state constants:

```python
# guest.submit_state values
PENDING = "pending"
SENT = "sent"
ERROR = "error"
BLOCKED = "blocked"  # rejected in a way that resending cannot fix
NOT_REQUIRED = "not_required"  # Czech nationals: house book only
```

The writers. These are all of them in `App/app/` and `go/` (non-test files). The test finds them by text pattern; the from-states were read from the code around each write by the brief author.

| # | File:line | Writer | Pattern the test sees | From | To | WHERE guard |
|---|---|---|---|---|---|---|
| 1 | `App/app/reporting.py:1370` | `plan_outcome`, accepted | `"submit_state": SENT,` | any | sent | none (applied by `db.update_in(cur, "guest", write_id, write_values)`, line 1817) |
| 2 | `App/app/reporting.py:1411` | `plan_outcome`, refused or duplicate | `"submit_state": new_state,` | any | error, blocked, sent | none (same) |
| 3 | `App/app/reporting.py:1533` | `collect_sendable`, guest not reportable | `{"submit_state": NOT_REQUIRED, ...}` | pending, error, blocked (the `if` on line 1532) | not_required | none |
| 4 | `App/app/reporting.py:2442` | `mark_filed_by_hand` | `UPDATE guest SET submit_state = ?, ... WHERE id = ? AND submit_state = ?` | pending, error, blocked (`_HAND_FILABLE_STATES`) | sent | compare-and-set |
| 5 | `App/app/reporting.py:2482` | `undo_filed_by_hand` | `UPDATE guest SET submit_state = ?, ... WHERE id = ? AND submit_state = ? AND manual_marked_at = ?` | sent | `manual_prev_state` if in `_HAND_FILABLE_STATES`, else pending | compare-and-set |
| 6 | `App/app/routes/admin.py:4607` | `guest_create` (insert) | `"submit_state": (` | new row | pending or not_required | insert |
| 7 | `App/app/routes/admin.py:4727` | `guest_update`, nationality not reportable | `payload["submit_state"] = reporting.NOT_REQUIRED` | pending, error, blocked, not_required (sent is kept, line 4722) | not_required | `db.update_if(..., {"submit_state": guest["submit_state"]}, ...)` |
| 8 | `App/app/routes/admin.py:4730` | `guest_update`, rule 10.4(5) | `payload["submit_state"] = reporting.PENDING` | error, blocked, not_required | pending | same |
| 9 | `App/app/routes/guest.py:2523` | guest form save (insert, or edit) | `"submit_state": (` | new row; or pending, error, blocked, not_required (sent refused, line 2345) | pending or not_required | `db.update_if(..., {"submit_state": existing["submit_state"]}, ...)` on edit |
| 10 | `App/app/demo.py:169` | `_guest`, setup-guide demo stay (insert) | `submit_state=(` | new row | pending or not_required | insert |
| 11 | `go/internal/ubyport/outcome.go:81` | `PlanOutcome`, accepted | `"submit_state":          outcomeSent,` | any | sent | none (applied by `updateGuest`, `go/internal/ubyport/store.go:170`) |
| 12 | `go/internal/ubyport/outcome.go:111` | `PlanOutcome`, refused or duplicate | `"submit_state":    newState,` | any | error, blocked, sent | none (same) |
| 13 | `go/internal/ubyport/collect.go:198` | collect, guest not reportable | `` `UPDATE guest SET submit_state = $1, updated_at = $2 WHERE id = $3` `` | pending, error, blocked (the `if` on line 196) | not_required | none |

"from any" for rows 1, 2, 11, 12: the write has no state test in its WHERE clause, and `collect_sendable` (and Go `collect`) admits every state: a host resend carries a `sent` or `blocked` guest, and nothing excludes a reportable guest still marked `not_required`. Rows 3 and 13 also have no WHERE guard (from-any in SQL); the test pins the states the `if` just before the write admits, and records the guard as `none`.

Not writes, and the test must not count them (it does not):

- `App/app/routes/admin.py:4739`, `App/app/routes/guest.py:2564`, `App/app/icalsync.py:448`: `{"submit_state": guest["submit_state"]}` (or `existing[...]`) is the `expected` guard of `db.update_if`.
- `go/internal/ical/reconcile.go:240`: `WHERE id = $4 AND submit_state = $5` is a guard on a stay-dates update.
- `go/internal/ubyport/store.go:30`: `"submit_state":          true,` is the allow-list of columns `updateGuest` may write.
- Every `UPDATE guest SET submission_id = ...` in `reporting.py`, `sweep.go`, `recover.go`: `submit_state` appears only in the WHERE clause.

The schema default is `submit_state   TEXT NOT NULL DEFAULT 'pending',` (`App/app/db.py:248`); all three inserts set the column explicitly.

### Derived transition table (what the code does today)

| From | To | Writers (row numbers above) |
|---|---|---|
| new row | pending, not_required | 6, 9, 10 |
| pending | sent | 1, 2, 4, 11, 12 |
| pending | error, blocked | 2, 12 |
| pending | not_required | 3, 7, 9, 13 |
| error | sent | 1, 2, 4, 11, 12 |
| error | blocked | 2, 12 |
| error | pending | 8, 9 |
| error | not_required | 3, 7, 9, 13 |
| blocked | sent | 1, 2, 4, 11, 12 |
| blocked | error | 2, 12 |
| blocked | pending | 8, 9 |
| blocked | not_required | 3, 7, 9, 13 |
| sent | error, blocked | 2, 12 (host resend refused); 5 (undo) |
| sent | pending | 5 |
| not_required | sent, error, blocked | 1, 2, 11, 12 |
| not_required | pending | 8, 9 |

No writer moves `sent -> not_required`. Same-state writes (for example a guest re-saving a `pending` form) are not moves and are not listed.

### Open questions (findings; this brief does not fix them, the table pins the code)

Compared with [OPERATIONS.md, the `submit_state` state machine](../OPERATIONS.md#the-submit_state-state-machine) (lines 70-109):

1. **150 gives sent, not blocked.** The doc lists `pending -> blocked` for "a non-correctable code (150, ...)". The code makes a record-level duplicate `sent`: `App/app/reporting.py:1400-1402` (`duplicate = uby_errors.record_is_duplicate(...)`, `new_state = SENT`) and `go/internal/ubyport/outcome.go:99`. `blocked` comes only from another non-correctable code (`App/app/reporting.py:1391`). The doc contradicts its own duplicate bullet.
2. **Moves out of `sent` exist.** The doc lists none. A host resend of a `sent` record (allowed by `App/app/reporting.py:1538`) that comes back refused with a non-duplicate code becomes `error` or `blocked` (`App/app/reporting.py:1391`, `1411`; `go/internal/ubyport/outcome.go:111`).
3. **Hand filing is missing from the doc.** `pending/error/blocked -> sent` (`App/app/reporting.py:2442`, `mark_filed_by_hand`) and `sent -> pending/error/blocked` (`App/app/reporting.py:2482`, `undo_filed_by_hand`).
4. **`error <-> blocked`.** A later send can move `error -> blocked` or (host resend) `blocked -> error` (`App/app/reporting.py:1391`, `go/internal/ubyport/outcome.go:96-98`). Not in the doc.
5. **The guest's own form also resets.** The doc says `error/blocked/not_required -> pending` "when a host edits the guest". The guest form save does it too, and can also move `pending/error/blocked -> not_required` (`App/app/routes/guest.py:2523`).
6. **"anything -> not_required" is not what the code does.** `sent` never moves to `not_required`: host edit keeps `sent` (`App/app/routes/admin.py:4722`), the guest form refuses a `sent` row (`App/app/routes/guest.py:2345`), and collect skips it (`App/app/reporting.py:1532`, `go/internal/ubyport/collect.go:196`). The move also happens in the sweep's collect step, not only on an edit.
7. **A record blocked as a duplicate becomes sendable after an edit.** The doc says a duplicate-blocked record is refused even on a deliberate resend (enforced in `App/app/reporting.py:1546`). A host edit (`App/app/routes/admin.py:4728-4730`) or a guest form save (`App/app/routes/guest.py:2523`) moves it to `pending`, after which that refusal no longer applies.
8. **`not_required -> sent/error/blocked`.** Collect does not exclude a reportable guest whose state is `not_required` (`App/app/reporting.py:1531-1535`, `go/internal/ubyport/collect.go:195-203`), so the outcome writers can move it. Reachable only if a row is reportable but still marked `not_required` (for example a code-list change). The doc's duplicate bullet lists only `error/blocked/pending`.
9. **Not a move, noted for completeness.** The doc says `sent` rows refuse edit on the host surface. Host `guest_update` saves non-reported fields of a `sent` row and keeps its state (`App/app/routes/admin.py:4722-4724`).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/reporting.py` | edit | Insert the `TRANSITIONS` dict after line 51 (step 2). One insertion, nothing else |
| `App/tests/test_sm_guest_submit_state.py` | create | The pin test, full content in step 4 |
| `docs/tasks/1105-report.md` | create | Your report (section 9) |

No other file may change. In particular: no Go file, no other line of `reporting.py`, no route, no `docs/context/test-map.md` (the orchestrator adds the row).

## 4. Steps

Run every command from `App/` unless it says otherwise. Commit after each step with the message `1105 step k`.

1. Confirm the anchors. From the repo root run:

   ```
   grep -nF 'NOT_REQUIRED = "not_required"  # Czech nationals: house book only' App/app/reporting.py | tail -30
   grep -c "TRANSITIONS" App/app/reporting.py | tail -30
   grep -nF "UPDATE guest SET submit_state" App/app/reporting.py go/internal/ubyport/collect.go | tail -30
   grep -nE '"submit_state": (SENT|new_state|NOT_REQUIRED)|"submit_state":\s+(outcomeSent|newState)' App/app/reporting.py go/internal/ubyport/outcome.go | tail -30
   grep -nF 'payload["submit_state"] = reporting.' App/app/routes/admin.py | tail -30
   ```

   Expected, in order: one line `51:NOT_REQUIRED = ...`; `0`; three lines (`reporting.py:2442`, `reporting.py:2482`, `collect.go:198`); five lines (`reporting.py:1370`, `1411`, `1533`, `outcome.go:81`, `111`); two lines (`admin.py:4727` `NOT_REQUIRED`, `4730` `PENDING`). Any difference: STOP.

2. Edit `App/app/reporting.py`: insert the block below directly after line 51. The diff is exact; change nothing else.

   ```diff
    BLOCKED = "blocked"  # rejected in a way that resending cannot fix
    NOT_REQUIRED = "not_required"  # Czech nationals: house book only
   +
   +# Every move of guest.submit_state a writer makes today, derived from the code
   +# (brief 1105). Nothing reads this at runtime: test_sm_guest_submit_state.py
   +# pins each write against it, so a new move fails CI until it is listed here.
   +# "outcome" is plan_outcome here and PlanOutcome in go/internal/ubyport/outcome.go;
   +# its write has no state guard and collect admits every state. A new row starts
   +# PENDING or NOT_REQUIRED (guest_create, the guest form, demo._guest).
   +TRANSITIONS = {
   +    PENDING: {
   +        SENT,  # outcome (accepted, or duplicate 150); mark_filed_by_hand
   +        ERROR,  # outcome (correctable refusal)
   +        BLOCKED,  # outcome (not correctable)
   +        NOT_REQUIRED,  # collect_sendable and collect.go; host guest_update; guest form
   +    },
   +    ERROR: {
   +        SENT,  # outcome; mark_filed_by_hand
   +        BLOCKED,  # outcome
   +        PENDING,  # host guest_update (rule 10.4(5)); guest form
   +        NOT_REQUIRED,  # collect_sendable and collect.go; host guest_update; guest form
   +    },
   +    BLOCKED: {
   +        SENT,  # outcome, on a host resend; mark_filed_by_hand
   +        ERROR,  # outcome, on a host resend
   +        PENDING,  # host guest_update (rule 10.4(5)); guest form
   +        NOT_REQUIRED,  # collect_sendable and collect.go; host guest_update; guest form
   +    },
   +    SENT: {
   +        PENDING,  # undo_filed_by_hand (manual_prev_state, else pending)
   +        ERROR,  # undo_filed_by_hand; outcome, on a host resend refused
   +        BLOCKED,  # undo_filed_by_hand; outcome, on a host resend refused
   +    },
   +    NOT_REQUIRED: {
   +        PENDING,  # host guest_update; guest form (nationality now reportable)
   +        SENT,  # outcome, for a reportable guest still marked not_required
   +        ERROR,  # outcome, same
   +        BLOCKED,  # outcome, same
   +    },
   +}

    # A guest the host filed by hand in the UbyPort web application (WP23) is
   ```

   Command (from `App/`):

   ```
   .venv/bin/python -c "from app import reporting; print(sorted(reporting.TRANSITIONS), sorted(reporting.TRANSITIONS['sent']))" 2>&1 | tail -30
   ```

   Expected: `['blocked', 'error', 'not_required', 'pending', 'sent'] ['blocked', 'error', 'pending']`.

3. Check the edit is one insertion. From the repo root:

   ```
   git diff --stat App/app/reporting.py | tail -30
   git diff App/app/reporting.py | grep -c '^-[^-]' | tail -30
   ```

   Expected: `1 file changed, 38 insertions(+)` and `0` (no line removed). Any removed line: undo with `git checkout App/app/reporting.py` and redo step 2.

4. Create `App/tests/test_sm_guest_submit_state.py` with exactly this content (nothing added, nothing removed):

```python
"""Pin every write of guest.submit_state against reporting.TRANSITIONS (brief 1105).

guest.submit_state is the police-filing record of each guest. This test reads
the Python and Go writer sources as text, finds every statement that writes the
column, and compares them with a pinned list. It fails when a write is added,
removed or changed, when a pinned move is not in reporting.TRANSITIONS, and
when the table lists a move no pinned writer makes. It changes nothing at
runtime: no writer reads the table.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from app import reporting

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
APP_PKG = APP / "app"
GO_DIR = REPO / "go"

PENDING = reporting.PENDING
SENT = reporting.SENT
ERROR = reporting.ERROR
BLOCKED = reporting.BLOCKED
NOT_REQUIRED = reporting.NOT_REQUIRED
STATES = {PENDING, SENT, ERROR, BLOCKED, NOT_REQUIRED}
NEW = "<new row>"  # an INSERT: the row has no state yet
# From-any: the write has no submit_state test in its WHERE clause, and collect
# admits every state (a host resend carries sent or blocked guests; nothing
# excludes a reportable guest still marked not_required).
ANY = frozenset(STATES)

# (file from the repo root, kind, token, from-states, to-states, guard, writer)
#   kind "dict":      a "submit_state": <token> key in a values dict or Go map
#   kind "subscript": payload["submit_state"] = <token>
#   kind "kwarg":     submit_state=<token> keyword argument
#   kind "sql":       UPDATE guest SET submit_state = ...; the token is "cas" when
#                     the WHERE clause also tests submit_state, "none" when not
#   guard: "cas" compare-and-set on the old state, "none" no state test in the
#   WHERE clause (from-any in SQL; the from-states are what the code just before
#   the write admits), "insert" a new row.
PINNED = [
    ("App/app/reporting.py", "dict", "SENT", ANY, {SENT}, "none",
     "plan_outcome: accepted"),
    ("App/app/reporting.py", "dict", "new_state", ANY, {ERROR, BLOCKED, SENT}, "none",
     "plan_outcome: refused, or record-level duplicate (150) = sent"),
    ("App/app/reporting.py", "dict", "NOT_REQUIRED", {PENDING, ERROR, BLOCKED}, {NOT_REQUIRED}, "none",
     "collect_sendable: guest not reportable"),
    ("App/app/reporting.py", "sql", "cas", {PENDING, ERROR, BLOCKED}, {SENT}, "cas",
     "mark_filed_by_hand"),
    ("App/app/reporting.py", "sql", "cas", {SENT}, {PENDING, ERROR, BLOCKED}, "cas",
     "undo_filed_by_hand: back to manual_prev_state, else pending"),
    ("App/app/routes/admin.py", "dict", "(", {NEW}, {PENDING, NOT_REQUIRED}, "insert",
     "guest_create"),
    ("App/app/routes/admin.py", "subscript", "reporting.NOT_REQUIRED",
     {PENDING, ERROR, BLOCKED, NOT_REQUIRED}, {NOT_REQUIRED}, "cas",
     "guest_update: nationality not reportable (sent is kept)"),
    ("App/app/routes/admin.py", "subscript", "reporting.PENDING",
     {ERROR, BLOCKED, NOT_REQUIRED}, {PENDING}, "cas",
     "guest_update: rule 10.4(5)"),
    ("App/app/routes/guest.py", "dict", "(",
     {NEW, PENDING, ERROR, BLOCKED, NOT_REQUIRED}, {PENDING, NOT_REQUIRED}, "cas",
     "guest form save: insert, or edit of a row that is not sent"),
    ("App/app/demo.py", "kwarg", "(", {NEW}, {PENDING, NOT_REQUIRED}, "insert",
     "_guest: setup-guide demo stay"),
    ("go/internal/ubyport/outcome.go", "dict", "outcomeSent", ANY, {SENT}, "none",
     "PlanOutcome: accepted (applied by updateGuest in store.go)"),
    ("go/internal/ubyport/outcome.go", "dict", "newState", ANY, {ERROR, BLOCKED, SENT}, "none",
     "PlanOutcome: refused, or duplicate = sent (applied by updateGuest in store.go)"),
    ("go/internal/ubyport/collect.go", "sql", "none", {PENDING, ERROR, BLOCKED}, {NOT_REQUIRED}, "none",
     "collect: guest not reportable"),
]

# "submit_state": <value>, but not the update_if guard {"submit_state": guest["submit_state"]}
# and not the Go allow-list entry "submit_state": true.
DICT_RE = re.compile(r'"submit_state"\s*:\s*(?!\w+\[\s*"submit_state"\s*\])(?!true\b)([\w.]+|\()')
SUBSCRIPT_RE = re.compile(r'\[\s*"submit_state"\s*\]\s*=(?!=)\s*([\w.]+|\()')
KWARG_RE = re.compile(r'(?<![\w"\'.])submit_state=(?!=)\s*([\w.]+|\()')
UPDATE_RE = re.compile(r'UPDATE guest SET ([^"`]*)')
ASSIGN_RE = re.compile(r"\bsubmit_state\s*=")


def _sources():
    py = sorted(APP_PKG.rglob("*.py"))
    go = sorted(p for p in GO_DIR.rglob("*.go") if not p.name.endswith("_test.go"))
    return py + go


def _found():
    """(file, kind, token) for every write of submit_state in the writer sources."""
    found = []
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO).as_posix()
        for m in DICT_RE.finditer(text):
            found.append((rel, "dict", m.group(1)))
        for m in SUBSCRIPT_RE.finditer(text):
            found.append((rel, "subscript", m.group(1)))
        for m in KWARG_RE.finditer(text):
            found.append((rel, "kwarg", m.group(1)))
        # Join adjacent Python string literals split over lines.
        joined = re.sub(r'"\s*\n\s*f?"', "", text)
        for m in UPDATE_RE.finditer(joined):
            parts = re.split(r"\bWHERE\b", m.group(1), maxsplit=1)
            if not ASSIGN_RE.search(parts[0]):
                continue
            where = parts[1] if len(parts) > 1 else ""
            found.append((rel, "sql", "cas" if ASSIGN_RE.search(where) else "none"))
    return found


def _pinned_moves():
    moves = set()
    for _file, _kind, _token, froms, tos, _guard, _writer in PINNED:
        for old in froms:
            if old == NEW:
                continue
            for new in tos:
                if old != new:
                    moves.add((old, new))
    return moves


def test_scan_finds_the_known_writers():
    """The scanners are not silently matching nothing."""
    assert len(_found()) >= len(PINNED)


def test_every_write_is_pinned():
    found = Counter(_found())
    pinned = Counter(entry[:3] for entry in PINNED)
    assert found == pinned, (
        "A write of guest.submit_state was added, removed or changed. "
        f"Only in the code: {sorted((found - pinned).elements())}. "
        f"Only in PINNED: {sorted((pinned - found).elements())}. "
        "Update PINNED and reporting.TRANSITIONS to what the code does."
    )


def test_pinned_states_are_real():
    for entry in PINNED:
        assert set(entry[3]) <= STATES | {NEW}, entry
        assert set(entry[4]) <= STATES, entry


def test_sql_pins_name_their_guard():
    for _file, kind, token, _froms, _tos, guard, writer in PINNED:
        if kind == "sql":
            assert token == guard, writer


def test_every_pinned_move_is_in_transitions():
    for old, new in sorted(_pinned_moves()):
        assert new in reporting.TRANSITIONS.get(old, set()), (
            f"{old} -> {new} is made by a writer but missing from reporting.TRANSITIONS"
        )


def test_transitions_lists_no_move_the_code_does_not_make():
    table = {(old, new) for old, targets in reporting.TRANSITIONS.items() for new in targets}
    assert table == _pinned_moves()


def test_transitions_covers_every_state():
    assert set(reporting.TRANSITIONS) == STATES
    for old, targets in reporting.TRANSITIONS.items():
        assert targets <= STATES
        assert old not in targets


def test_new_rows_start_pending_or_not_required():
    starts = set()
    for entry in PINNED:
        if NEW in entry[3]:
            starts |= set(entry[4])
    assert starts == {PENDING, NOT_REQUIRED}


def test_go_batch_writes_go_through_the_generic_writer():
    store = (GO_DIR / "internal" / "ubyport" / "store.go").read_text(encoding="utf-8")
    assert re.search(r'"submit_state":\s+true,', store)
    assert '"UPDATE guest SET " + strings.Join(sets, ", ")' in store


def test_nothing_reads_transitions_at_runtime():
    own = (APP_PKG / "reporting.py").read_text(encoding="utf-8")
    assert len(re.findall(r"\bTRANSITIONS\b", own)) == 1
    for path in APP_PKG.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "reporting.TRANSITIONS" not in text, path
        assert not re.search(r"from \.?reporting import[^\n]*\bTRANSITIONS\b", text), path
```

   Command (from `App/`):

   ```
   .venv/bin/python -m pytest tests/test_sm_guest_submit_state.py -q --tb=short -x 2>&1 | tail -30
   ```

   Expected: `10 passed`. A failure in `test_every_write_is_pinned` prints the difference: STOP and report it (do not change `PINNED` to make it pass; the brief author checked the scan against base commit 5e034303).

5. Run the existing filing tests (test-map row "Filing, UbyPort, worker, claim"). From `App/`:

   ```
   .venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_endtoend.py -q --tb=short -x 2>&1 | tail -30
   ```

   Expected: all pass, `0 failed`. These prove step 2 changed no behaviour.

6. Run the context lint. From the repo root:

   ```
   python3 scripts/context_lint.py 2>&1 | tail -30
   ```

   Expected: no error (warnings about other open briefs are fine; copy them into the report).

7. Check the whole diff. From the repo root:

   ```
   git diff --stat 5e034303 -- App go | tail -30
   ```

   Expected: exactly `App/app/reporting.py` (38 insertions) and `App/tests/test_sm_guest_submit_state.py` (new). No `go/` file. Anything else: STOP.

8. Write `docs/tasks/1105-report.md` (section 9), set `Status: review` at the top of this brief, commit `1105 step 8`, and open one draft PR from `task/1105-sm-guest-submit-state`.

## 5. Do not touch

- Every writer: `App/app/reporting.py` outside the step 2 insertion, `App/app/routes/admin.py`, `App/app/routes/guest.py`, `App/app/demo.py`, `App/app/icalsync.py`, `App/app/db.py`.
- Everything under `go/`. The test reads Go files; it never changes them.
- `docs/OPERATIONS.md` (the disagreements in section 2 are for the orchestrator), `docs/context/test-map.md`.
- AGENTS.md hard rules that apply: 1 (UbyPort filing correctness beats every other feature: zero runtime change), 4 (no new dependency), 5 (no migration), 8 (never push to `main`; keep the PR a draft).

## 6. Commands

| Step | Command (from `App/` unless noted) | Expected |
|---|---|---|
| 2 | `.venv/bin/python -c "from app import reporting; print(sorted(reporting.TRANSITIONS), sorted(reporting.TRANSITIONS['sent']))" 2>&1 \| tail -30` | `['blocked', 'error', 'not_required', 'pending', 'sent'] ['blocked', 'error', 'pending']` |
| 4 | `.venv/bin/python -m pytest tests/test_sm_guest_submit_state.py -q --tb=short -x 2>&1 \| tail -30` | `10 passed` |
| 5 | the filing row command in step 5 | `0 failed` |
| 6 | (repo root) `python3 scripts/context_lint.py 2>&1 \| tail -30` | no error |

Never the full suite.

## 7. Acceptance

- [ ] `git diff 5e034303 -- App/app/reporting.py | grep -c '^-[^-]'` prints `0`, and the only added block is `TRANSITIONS` directly after `NOT_REQUIRED = ...`.
- [ ] `git diff --stat 5e034303 -- go` prints nothing.
- [ ] `tests/test_sm_guest_submit_state.py`: `10 passed`.
- [ ] Filing tests (test-map row "Filing, UbyPort, worker, claim", step 5): `0 failed`.
- [ ] `grep -rn "reporting.TRANSITIONS" App/app | tail -30` prints nothing.
- [ ] Context lint: no error.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor in section 2 or step 1 is not found;
- `test_every_write_is_pinned` fails (the code has moved since the brief: report the printed difference, do not edit `PINNED`);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push to `main`, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1105-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/reporting.py`: the diff must be the 38-line insertion only. Confirm no writer line moved or changed.
- `App/tests/test_sm_guest_submit_state.py`: compare `PINNED` with the writer table in section 2; the orchestrator decides the open questions and adds the test-map row.

## Owner steps

1. Nothing to deploy: the change is inert. When the draft PR is green and the orchestrator has reviewed it, the orchestrator merges with `scripts/merge-pr-on-green.sh`.
2. Read the "Open questions" in section 2 and tell the orchestrator, for each, whether the doc or the code is right. Any code change is a later brief.
