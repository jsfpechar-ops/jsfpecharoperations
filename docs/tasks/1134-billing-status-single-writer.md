# 1134: billing_account.status has one writer, place_for_operator goes through set_status

Status: todo
Depends on: none | Base commit: 7b8ff2ae | Branch: task/1134-billing-status-single-writer
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

`billing_order.place_for_operator` writes `billing_account.status = 'paused'` with a raw UPDATE (no lock, no state check, no audit) and the move trial_pending -> paused is not in `billing.TRANSITIONS`. Allow that move in the table, send the write through `billing.set_status`, and pin every writer of the column with a new test.

## 2. Context

Rule 5 (SQL only through db helpers) and the state-machine plan: one writer per status column, a pin test per column (style: `App/tests/test_sm_payment_request.py`).

`App/app/billing.py` lines 18-25:

```python
TRANSITIONS = {
    "trial_pending": {"trialing"},
    "trialing": {"active", "paused"},
```

`App/app/billing.py` `set_status` (line ~160) locks the row, returns False unless `new in TRANSITIONS[old]`, writes, then audits `billing_status old->new`.

`App/app/billing_order.py` lines 190-195 (inside `place_for_operator`, after `ensure_account` just created a `trial_pending` row, `acc["plan"] is None` checked):

```python
    db.execute(
        "UPDATE billing_account SET status = 'paused', updated_at = ? WHERE owner_user_id = ?",
        (db.utcnow(), owner_user_id),
    )
    result = place(owner_user_id, values, today=day)
```

`place()` accepts `ORDERABLE = ("trial_pending", "trialing", "paused")`, raises `already_ordered` otherwise, and only issues the first invoice and moves to active when status is `paused` (`if acc["status"] != "paused": return {"starts": "trial_end", ...}`).

Decision 2026-10-29: legacy hosts get no trial, so the operator flow pauses the account and `place()` starts the plan today.

What `set_status(owner, "paused")` returns after the change:
- trial_pending or trialing: moves, True (same end state as the raw UPDATE).
- already paused: False (paused -> paused is not a move); the account is already paused, `place()` behaves as before. Safe to ignore.
- active, overdue, canceling with `plan IS NULL`: not a reachable state; False, and `place()` then raises `already_ordered`. The raw UPDATE used to force these to paused; refusing is correct. Behaviour for every reachable state is unchanged.
So the return value needs no branch; a comment says why.

Every writer of `billing_account.status` (grep done by the orchestrator; Go has none, `go/internal/billing/snapshot.go` only writes `billing_month_snapshot`):
- `App/app/billing.py` `ensure_account`: INSERT as `trial_pending`.
- `App/app/billing.py` `set_status`: the one UPDATE.
- `App/app/billing_trial.py` line 82: UPDATE trial_pending -> trialing, with CAS guard `AND status = 'trial_pending'`. Fine, pinned.
- `App/app/signup.py` line 639: INSERT as `trialing`. Fine, pinned.
- `App/app/billing_order.py` line 192: the raw UPDATE this brief removes.

If an excerpt is not found verbatim, STOP (§8).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/billing.py | edit | add "paused" to trial_pending in TRANSITIONS, with comment |
| App/app/billing_order.py | edit | replace raw UPDATE with `billing.set_status` |
| App/tests/test_sm_billing_status.py | create | pin test for all writers |

No other file may change.

## 4. Steps

**Step 1. `App/app/billing.py`, widen the table.** Replace exactly:

```python
    "trial_pending": {"trialing"},
```

with:

```python
    # paused: place_for_operator (operator assigns a plan to a legacy host, no trial;
    # owner decision 2026-10-29)
    "trial_pending": {"trialing", "paused"},
```

Command: `cd App && .venv/bin/python -c "from app import billing; print(sorted(billing.TRANSITIONS['trial_pending']))" 2>&1 | tail -30`
Expected: `['paused', 'trialing']`

**Step 2. `App/app/billing_order.py`, use the single writer.** Replace exactly:

```python
    db.execute(
        "UPDATE billing_account SET status = 'paused', updated_at = ? WHERE owner_user_id = ?",
        (db.utcnow(), owner_user_id),
    )
    result = place(owner_user_id, values, today=day)
```

with:

```python
    # trial_pending/trialing -> paused. False means already paused (fine) or a state
    # place() refuses with already_ordered; either way the result is not needed.
    billing.set_status(owner_user_id, "paused", actor=actor)
    result = place(owner_user_id, values, today=day)
```

Command: `grep -n "SET status" App/app/billing_order.py | tail -30`
Expected: no output.

**Step 3. Create `App/tests/test_sm_billing_status.py`** with exactly:

```python
"""Pins every writer of billing_account.status against billing.TRANSITIONS
(plan: docs/plans/explicit-state-machines.md, brief 1134).

The test reads the writer sources as text. It fails when a statement that writes
billing_account.status is added, removed or moved to another file, and when a
pinned move is not allowed by the table. Go has no writer of this column.
"""
import re
from pathlib import Path

import pytest

from app import billing

APP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = APP_DIR.parent

TABLE = billing.TRANSITIONS

# (file, anchor that must appear verbatim, from-states, to-state)
MOVES = [
    ("App/app/billing_trial.py",
     "UPDATE billing_account SET status = 'trialing', trial_started_at = ?, ",
     ("trial_pending",), "trialing"),
    ("App/app/billing_order.py",
     'billing.set_status(owner_user_id, "paused", actor=actor)',
     ("trial_pending", "trialing"), "paused"),
]

# Rows are born in these states: ensure_account and signup verification.
INITIAL = [
    ("App/app/billing.py", "VALUES (?, 'trial_pending', ?) ON CONFLICT(owner_user_id) DO NOTHING", "trial_pending"),
    ("App/app/signup.py", "VALUES (?, 'trialing', ?, ?, ?) ON CONFLICT(owner_user_id) DO NOTHING", "trialing"),
]

# Every file that writes the status column, and how many times.
PINNED_WRITERS = {
    "App/app/billing.py": {"status_updates": 1, "inserts": 1},
    "App/app/billing_trial.py": {"status_updates": 1},
    "App/app/signup.py": {"inserts": 1},
}

UPDATE_RE = re.compile(r"UPDATE\s+billing_account\s+SET\b(.*?)\bWHERE\b", re.S | re.I)
STATUS_RE = re.compile(r"(?<![\w])status\s*=")
INSERT_RE = re.compile(r"INSERT\s+INTO\s+billing_account\b", re.I)


def _read(rel: str) -> str:
    return (REPO_DIR / rel).read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    return path.relative_to(REPO_DIR).as_posix()


def _files():
    go = (p for p in (REPO_DIR / "go").rglob("*.go") if not p.name.endswith("_test.go"))
    return sorted(list((APP_DIR / "app").rglob("*.py")) + list(go))


def test_table_is_well_formed():
    assert set(TABLE) == set(billing.STATUSES)
    for source, targets in TABLE.items():
        assert targets <= set(billing.STATUSES), source


@pytest.mark.parametrize("rel,anchor", [(f, a) for f, a, _, _ in MOVES] + [(f, a) for f, a, _ in INITIAL])
def test_anchor_is_in_file(rel, anchor):
    assert anchor in _read(rel), f"{rel} no longer contains: {anchor}"


@pytest.mark.parametrize(
    "rel,anchor,source,target",
    [(f, a, s, t) for f, a, froms, t in MOVES for s in froms],
)
def test_pinned_move_is_allowed_by_table(rel, anchor, source, target):
    assert target in TABLE[source], f"{rel}: {source} -> {target} is not in billing.TRANSITIONS"


@pytest.mark.parametrize("rel,anchor,state", INITIAL)
def test_birth_states_exist(rel, anchor, state):
    assert state in TABLE


def test_status_writing_statements_match_the_pins():
    found = {}
    for path in _files():
        text = path.read_text(encoding="utf-8")
        counts = {
            "status_updates": sum(1 for m in UPDATE_RE.finditer(text) if STATUS_RE.search(m.group(1))),
            "inserts": len(INSERT_RE.findall(text)),
        }
        counts = {k: v for k, v in counts.items() if v}
        if counts:
            found[_rel(path)] = counts
    assert found == PINNED_WRITERS
```

Command: `cd App && .venv/bin/python -m pytest tests/test_sm_billing_status.py -q --tb=short -x 2>&1 | tail -30`
Expected: all passed. If `test_status_writing_statements_match_the_pins` fails because `found` shows an extra file, STOP (§8); do not edit the pin to fit.

## 5. Do not touch

`App/app/billing_trial.py`, `App/app/signup.py`, any template, any other table in `TRANSITIONS`, `go/`. No new dependency (rule 4). No schema change (rule 5). No personal data added (rule 2).

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_sm_billing_status.py -q --tb=short -x 2>&1 | tail -30` expected: all passed.
2. `.venv/bin/python -m pytest tests/test_billing_*.py -q --tb=short -x 2>&1 | tail -30` expected: all passed (test-map row "Platform billing"). If a test counts audit rows for an operator assign and now sees an extra `billing_status trial_pending->paused` row, that is expected: STOP and report it (§8), do not edit the test.
3. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` expected: no new errors.

## 7. Acceptance

- [ ] `billing.TRANSITIONS["trial_pending"] == {"trialing", "paused"}`.
- [ ] `grep -n "SET status" App/app/billing_order.py` prints nothing.
- [ ] New test passes; billing tests pass.
- [ ] Only the three files in §3 changed (`git diff --stat`, plus the new file).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1134-report.md` (600 tokens at most) and set `Status: review`. The report has: 1. files changed (`git diff --stat`); 2. each command with the last 5 lines of output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left.

## Risk list (for the reviewer)

`App/app/billing_order.py` (the replaced write; check the audit row now written) and the `TRANSITIONS` diff in `App/app/billing.py`.

## Open questions

- Operator assign now writes an extra audit row `billing_status trial_pending->paused` (actor = the operator) before the existing `billing_order` row. Assumed wanted (it is the point of the audit rule); owner may object.
- The table now also allows trial_pending -> paused for other callers of `set_status` (none today pass it). Accepted by deriving from the 2026-10-29 decision; say if the owner wants a narrower path instead.

## Owner steps

1. Open the draft PR, read the two Risk-list diffs, and say "merge" in chat. The orchestrator runs `scripts/merge-pr-on-green.sh`.
