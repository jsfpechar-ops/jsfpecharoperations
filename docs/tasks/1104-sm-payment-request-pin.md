# 1104: Pin every writer of payment_request.status against the Python table

Status: todo
Depends on: none | Base commit: 5e034303 | Branch: task/1104-sm-payment-request-pin
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add one test file that reads every Python and Go writer of `payment_request.status` as text, pins each (file, from-states, to-state) move, and fails when a move is added, removed, changed, or not allowed by `payment_request._TRANSITIONS`. No runtime behaviour changes: this is brief 1104 of [explicit-state-machines](../plans/explicit-state-machines.md) round 1, and it protects the money path (Go writes the same column with its own SQL and has no table).

## 2. Context

Rules from the plan that bind this brief: derive, never design (the pins list what the code does today, even where a doc disagrees); writers are not edited; Go files are read, never changed; no migration, no dependency, no copy change.

The table already exists. Anchor, file `App/app/payment_request.py`:

```python
_TRANSITIONS = {
    "draft": {"sent", "cancelled"},
    "sent": {"awaiting_payment", "paid", "expired", "cancelled"},
    "awaiting_payment": {"paid", "expired", "cancelled"},
    "paid": set(),
```

with `expired` and `cancelled` each allowing `{"paid"}` (a guest can pay an old link; 0623). `set_status` in the same file is the only Python UPDATE of the column: `UPDATE payment_request SET status = ?, paid_at = COALESCE(?, paid_at), updated_at = ? WHERE id = ? AND status = ?`, with the from-state read from the row (`current`) and the to-state passed by the caller.

**All writers found (grep of `App/app` and `go/`, Python SQL, `db.insert/update` dict helpers, Go SQL; no other writer exists):**

| File | Statement | From | To |
|---|---|---|---|
| `App/app/payment_request.py` | `create()`: `db.insert("payment_request", {... "status": "draft" ...})` | none (new row) | draft |
| `App/app/payment_request.py` | `set_status` UPDATE, reached by the callers below | per caller | per caller |
| `App/app/routes/payments.py` (2 calls, in `payment_request_send` and the QR send path) | `payment_request.set_status(request_id, "sent", ...)`, guarded by `status == "draft"` or `not resend` (resend means status is `sent`) | draft | sent |
| `App/app/payment_links.py` (`on_paid`) | `model.set_status(..., "sent", ...)` only when the row is draft | draft | sent |
| `App/app/payment_links.py` (`on_paid`) | `model.mark_paid(...)`; returns early when status is already `paid` | sent, awaiting_payment, expired, cancelled | paid |
| `App/app/payment_request.py` | `expire_sweep`: SELECT `status IN ('sent', 'awaiting_payment')`, then `set_status(..., "expired")` (called from `scheduler.py`) | sent, awaiting_payment | expired |
| `go/internal/payments/requests.go` | `requestSentSQL`: `... SET status = 'sent' ... AND status = 'draft'`; also `INSERT ... 'draft'` | draft; none | sent; draft |
| `go/internal/payments/paylink_routes.go` | second caller of `requestSentSQL` (only when status is `draft`) | draft | sent |
| `go/internal/payments/sweep.go` | `expireSQL`, from-state `o.current` read by `selectOverdueSQL` (`status IN ('sent', 'awaiting_payment')`) | sent, awaiting_payment | expired |
| `go/internal/payments/webhook.go` | `transitionSQL` (`SET status = $1 ... WHERE id = $4 AND status = $5`), only reached through `setStatus(ctx, q, id, owner, from, to, paid, stamp)` | see below | see below |

**How the Go `transitionSQL` pairs were derived.** `transitionSQL` is executed in one place (`setStatus`, `webhook.go`), and `setStatus` has exactly two callers, both in `onPaid`:

1. `setStatus(ctx, q, id, owner, "draft", "sent", false, stamp)`: a literal pair, draft to sent.
2. `setStatus(ctx, q, id, owner, status, "paid", true, stamp)`: `status` is the value read from the row. The `switch status` above it lets only `"draft", "sent", "awaiting_payment", "expired", "cancelled"` through; a draft row is first moved to `sent` (call 1) and `status = "sent"` is assigned before call 2. So the from-states of call 2 are sent, awaiting_payment, expired, cancelled; the to-state is paid.

Every pinned pair is in `_TRANSITIONS`: **Go makes no move the Python table forbids**, so the test needs no exception entry.

**Open questions (do not fix, orchestrator decides after the PR):**

- Q1. The plan (rule 2) says the table is named `TRANSITIONS`; in this module it is `_TRANSITIONS` (`App/app/payment_request.py`, `billing.py` uses the public name). The test uses `_TRANSITIONS`. Renaming is a writer edit and is out of scope.
- Q2. The table allows `sent -> awaiting_payment` and `draft/sent/awaiting_payment -> cancelled`, but no writer in Python or Go makes those moves today (grep of `awaiting_payment`, `cancelled` in `routes/payments.py`, `payment_links.py`, `payment_request.py`, `go/internal/payments/*.go`: reads only). They are dead table entries; the test does not pin them.
- Q3. Go's `setStatus` has no table check; its only gate is the `switch` in `onPaid` plus the `AND status = $5` compare-and-swap. Python raises `ValueError` on an illegal jump. The test pins the Go pairs, so a changed `switch` fails only if its text changes.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_sm_payment_request.py` | create | the pin test, full text in step 2 |
| `docs/tasks/1104-report.md` | create | the report (section 9) |
| `docs/tasks/1104-sm-payment-request-pin.md` | edit | set `Status: review` at the end |

No other file may change.

## 4. Steps

Run every command from the repo root unless it says `cd App`.

**Step 1. Check the anchors exist (read-only).**

```
grep -nF 'ok = set_status(request_id, "paid", today=today, paid_at=db.utcnow())' App/app/payment_request.py | tail -30
grep -nF 'model.mark_paid(int(row["id"]), today=date.today(), via="stripe_webhook")' App/app/payment_links.py | tail -30
grep -nF 'payment_request.set_status(request_id, "sent", today=date.today())' App/app/routes/payments.py | tail -30
grep -nF 'setStatus(ctx, q, id, owner, status, "paid", true, stamp)' go/internal/payments/webhook.go | tail -30
grep -nF 'tx.Exec(ctx, expireSQL, now, o.id, o.current)' go/internal/payments/sweep.go | tail -30
grep -nF "pool.Exec(ctx, requestSentSQL, stamp, id)" go/internal/payments/requests.go go/internal/payments/paylink_routes.go | tail -30
```

Expected: each command prints exactly one matching line (the last prints two, one per file). Any command prints nothing: STOP.

**Step 2. Create `App/tests/test_sm_payment_request.py` with exactly this content.**

```python
"""Pins every writer of payment_request.status, Python and Go, against
payment_request._TRANSITIONS (plan: docs/plans/explicit-state-machines.md,
brief 1104).

The test reads the writer sources as text. It fails when a statement that
writes payment_request.status is added, removed or changed, and when a pinned
move is not allowed by the table. Go has no table: its moves are pinned from
the arguments its callers pass (derivation: docs/tasks/1104-sm-payment-request-pin.md).
"""
import re
from collections import defaultdict
from pathlib import Path

import pytest

from app import payment_request

APP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = APP_DIR.parent

TABLE = payment_request._TRANSITIONS

LATE_PAID_FROM = ("sent", "awaiting_payment", "expired", "cancelled")
OVERDUE_FROM = ("sent", "awaiting_payment")

# (file, anchor that must appear verbatim in that file, from-states, to-state)
MOVES = [
    # Python: card or QR send, draft -> sent
    ("App/app/routes/payments.py",
     'payment_request.set_status(request_id, "sent", today=date.today())',
     ("draft",), "sent"),
    ("App/app/routes/payments.py",
     'payment_request.set_status(request_id, "sent", today=__import__("datetime").date.today())',
     ("draft",), "sent"),
    # Python: Stripe webhook (payment_links.on_paid)
    ("App/app/payment_links.py",
     'model.set_status(int(row["id"]), "sent", today=date.today())',
     ("draft",), "sent"),
    ("App/app/payment_links.py",
     'model.mark_paid(int(row["id"]), today=date.today(), via="stripe_webhook")',
     LATE_PAID_FROM, "paid"),
    # Python: inside payment_request.py
    ("App/app/payment_request.py",
     'ok = set_status(request_id, "paid", today=today, paid_at=db.utcnow())',
     LATE_PAID_FROM, "paid"),
    ("App/app/payment_request.py",
     'set_status(int(row["id"]), "expired", today=today)',
     OVERDUE_FROM, "expired"),
    # Go: expireSQL; the from-state is o.current, read by selectOverdueSQL
    ("go/internal/payments/sweep.go",
     "tx.Exec(ctx, expireSQL, now, o.id, o.current)",
     OVERDUE_FROM, "expired"),
    # Go: requestSentSQL has the from-state in its own WHERE
    ("go/internal/payments/requests.go",
     "pool.Exec(ctx, requestSentSQL, stamp, id)",
     ("draft",), "sent"),
    ("go/internal/payments/paylink_routes.go",
     "pool.Exec(ctx, requestSentSQL, stamp, id)",
     ("draft",), "sent"),
    # Go: transitionSQL, only reached through setStatus in onPaid
    ("go/internal/payments/webhook.go",
     'setStatus(ctx, q, id, owner, "draft", "sent", false, stamp)',
     ("draft",), "sent"),
    ("go/internal/payments/webhook.go",
     'setStatus(ctx, q, id, owner, status, "paid", true, stamp)',
     LATE_PAID_FROM, "paid"),
]

# Anchors that justify the from-states above. Moves cannot be derived without them.
ANCHORS = [
    ("App/app/payment_request.py",
     "\" WHERE status IN ('sent', 'awaiting_payment') AND expires_at < ?\","),
    ("go/internal/payments/sweep.go",
     "WHERE status IN ('sent', 'awaiting_payment') AND expires_at < $1 ORDER BY id"),
    ("go/internal/payments/requests.go",
     "SET status = 'sent', updated_at = $1 WHERE id = $2 AND status = 'draft'"),
    ("go/internal/payments/webhook.go",
     'case "draft", "sent", "awaiting_payment", "expired", "cancelled":'),
    ("go/internal/payments/webhook.go",
     "WHERE id = $4 AND status = $5"),
]

# Rows are born in 'draft': Python insert dict, Go INSERT.
INITIAL = [
    ("App/app/payment_request.py", '"status": "draft",'),
    ("go/internal/payments/requests.go",
     "VALUES ($1, NULL, $2, $3, $4, 'CZK', $5, $6, $7, 'draft', $8, $9, $9) RETURNING id"),
]

# Every file that writes the status column or inserts a row, and how many times.
PINNED_WRITERS = {
    "App/app/payment_request.py": {"status_updates": 1, "inserts": 1},
    "go/internal/payments/requests.go": {"status_updates": 1, "inserts": 1},
    "go/internal/payments/sweep.go": {"status_updates": 1},
    "go/internal/payments/webhook.go": {"status_updates": 1},
}

# Where the status-writing functions and SQL constants are used.
PINNED_PY_CALLERS = {
    "App/app/routes/payments.py": ["set_status", "set_status"],
    "App/app/payment_links.py": ["set_status", "mark_paid"],
    "App/app/scheduler.py": ["expire_sweep"],
}
PINNED_PY_INTERNAL = ["set_status", "set_status"]  # inside payment_request.py
PINNED_GO_EXEC = {
    "requestSentSQL": {"go/internal/payments/requests.go": 1, "go/internal/payments/paylink_routes.go": 1},
    "transitionSQL": {"go/internal/payments/webhook.go": 1},
    "expireSQL": {"go/internal/payments/sweep.go": 1},
}
PINNED_GO_SETSTATUS = {"go/internal/payments/webhook.go": 2}

UPDATE_RE = re.compile(r"UPDATE\s+payment_request\s+SET\b(.*?)\bWHERE\b", re.S | re.I)
STATUS_RE = re.compile(r"(?<![\w])status\s*=")
INSERT_SQL_RE = re.compile(r"INSERT\s+INTO\s+payment_request\s*\(", re.I)
INSERT_HELPER_RE = re.compile(r"\b(?:insert|insert_in)\(\s*(?:cur,\s*)?[\"']payment_request[\"']")
UPDATE_HELPER_RE = re.compile(r"\b(?:update|update_if|update_in)\(\s*(?:cur,\s*)?[\"']payment_request[\"']")
PY_CALL_RE = re.compile(r"\b(?:payment_request|model)\.(set_status|mark_paid|expire_sweep)\(")
PY_INTERNAL_RE = re.compile(r"(?<![.\w])(?<!def )(set_status)\(")


def _read(rel: str) -> str:
    return (REPO_DIR / rel).read_text(encoding="utf-8")


def _py_files():
    return sorted((APP_DIR / "app").rglob("*.py"))


def _go_files():
    return sorted(p for p in (REPO_DIR / "go").rglob("*.go") if not p.name.endswith("_test.go"))


def _rel(path: Path) -> str:
    return path.relative_to(REPO_DIR).as_posix()


def test_table_is_well_formed():
    assert set(TABLE) == set(payment_request.STATUSES)
    for source, targets in TABLE.items():
        assert targets <= set(payment_request.STATUSES), source


@pytest.mark.parametrize("rel,anchor", [(f, a) for f, a, _, _ in MOVES] + ANCHORS + INITIAL)
def test_anchor_is_in_file(rel, anchor):
    assert anchor in _read(rel), f"{rel} no longer contains: {anchor}"


@pytest.mark.parametrize(
    "rel,anchor,source,target",
    [(f, a, s, t) for f, a, froms, t in MOVES for s in froms],
)
def test_pinned_move_is_allowed_by_table(rel, anchor, source, target):
    assert target in TABLE[source], f"{rel}: {source} -> {target} is not in payment_request._TRANSITIONS"


def test_rows_are_born_draft_and_nothing_moves_back_to_draft():
    assert "draft" in TABLE
    assert all("draft" not in targets for targets in TABLE.values())


def test_status_writing_statements_match_the_pins():
    found = {}
    for path in _py_files() + _go_files():
        text = path.read_text(encoding="utf-8")
        counts = {
            "status_updates": sum(1 for m in UPDATE_RE.finditer(text) if STATUS_RE.search(m.group(1))),
            "inserts": len(INSERT_SQL_RE.findall(text)) + len(INSERT_HELPER_RE.findall(text)),
            "helper_updates": len(UPDATE_HELPER_RE.findall(text)),
        }
        counts = {k: v for k, v in counts.items() if v}
        if counts:
            found[_rel(path)] = counts
    assert found == PINNED_WRITERS


def test_python_callers_match_the_pins():
    found = {}
    for path in _py_files():
        if _rel(path) == "App/app/payment_request.py":
            continue
        names = PY_CALL_RE.findall(path.read_text(encoding="utf-8"))
        if names:
            found[_rel(path)] = names
    assert found == PINNED_PY_CALLERS
    internal = PY_INTERNAL_RE.findall(_read("App/app/payment_request.py"))
    assert internal == PINNED_PY_INTERNAL


def test_go_callers_match_the_pins():
    for name, expected in PINNED_GO_EXEC.items():
        pattern = re.compile(r"\bExec\(ctx,\s*" + name + r"\b")
        found = defaultdict(int)
        for path in _go_files():
            n = len(pattern.findall(path.read_text(encoding="utf-8")))
            if n:
                found[_rel(path)] = n
        assert dict(found) == expected, name
    found = {}
    for path in _go_files():
        n = len(re.findall(r"\bsetStatus\(ctx, ", path.read_text(encoding="utf-8")))
        if n:
            found[_rel(path)] = n
    assert found == PINNED_GO_SETSTATUS
```

Command: `ls -l App/tests/test_sm_payment_request.py | tail -30`
Expected: the file is listed. Commit: `git add App/tests/test_sm_payment_request.py && git commit -m "1104 step 2" | tail -30`

**Step 3. Run the test.**

Command: `cd App && .venv/bin/python -m pytest tests/test_sm_payment_request.py -q --tb=short -x 2>&1 | tail -30`
Expected: `45 passed` with 0 failed and 0 skipped. Any other number: STOP.

**Step 4. Confirm only the allowed files changed.**

Command: `git status --short | tail -30`
Expected: only `App/tests/test_sm_payment_request.py` committed; the working tree is otherwise clean apart from the report you write next.

**Step 5. Write the report and set the status.** Create `docs/tasks/1104-report.md` per section 9, then change the line `Status: todo` in this brief to `Status: review`. Commit: `git add docs/tasks/1104-report.md docs/tasks/1104-sm-payment-request-pin.md && git commit -m "1104 step 5" | tail -30`. Open one draft PR (hand the push to the owner if `gh` is read-only).

## 5. Do not touch

- Everything under `App/app/` and `go/`: no writer, no Go file, no table, no rename of `_TRANSITIONS` (Q1).
- `docs/context/test-map.md` (the orchestrator adds the row at review), the plan, other briefs (1103 and 1105 to 1111).
- Hard rules: no new dependency, no migration, no secrets, never push to `main`, no full test suite.

## 6. Commands

Test (only this one): `cd App && .venv/bin/python -m pytest tests/test_sm_payment_request.py -q --tb=short -x 2>&1 | tail -30` expects all tests passed, 0 skipped. Lint from the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` expects no new warning for this brief.

## 7. Acceptance

- [ ] `App/tests/test_sm_payment_request.py` exists and is identical to step 2 (`git diff --stat` shows one new test file, plus the report and the status line).
- [ ] The test command in section 6 passes, 0 skipped.
- [ ] `git diff --stat main -- App/app go | tail -30` prints nothing.
- [ ] `docs/tasks/1104-report.md` lists Q1 to Q3 under Questions without changing code.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in step 1 is not found, or the test in step 3 fails twice (a failure may mean the code changed after this brief; do not edit the test to make it pass, report the failing line);
- `App/.venv/bin/python` is missing;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a file outside section 3 needs a change;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1104-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines of its output, section 7 ticked, deviations, questions (copy Q1 to Q3), owner steps left.

## Risk list (for the reviewer)

`App/tests/test_sm_payment_request.py`: confirm that the MOVES list matches the table in section 2, that every Go pair is justified by an ANCHORS entry, and that `PINNED_WRITERS` names all four writer files. A passing run proves the pins match today's code; it does not prove Q2 (dead table entries) is intended.

## Owner steps

1. Open the pull request on GitHub and read the Questions section of the report.
2. When CI is green, run `scripts/merge-pr-on-green.sh` for this PR from the repo root. Nothing is deployed behaviour-wise; only a test file is added.
