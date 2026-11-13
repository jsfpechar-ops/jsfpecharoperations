# 1180: Standing rule and catch-all test for state machines

Status: review
Depends on: none | Base commit: 748098d9 | Branch: claude/hopeful-ride-ovwq66
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add a test that fails when a new stored `state`/`status` column appears without a TRANSITIONS table and pin test (or a written exemption), and add the standing rule that explains it. This stops new implicit state machines; rounds 1 to 3 already pinned the existing ones.

## 2. Context

- Plans (history only, do not open): docs/plans/explicit-state-machines.md and docs/plans/explicit-state-machines-rounds-2-4.md.
- Pinned machines are the keys of `PYTHON_TABLES` in `App/tests/test_sm_go_parity.py` (12 today, "table.column"). Anchor, verbatim:

```python
PYTHON_TABLES = {
    "ad_click.send_state": meta_capi.SEND_TRANSITIONS,
```

- Columns come from the real schema: `db._expected_sqlite_columns()` in `App/app/db.py` (builds SCHEMA + ADDED_COLUMNS + `App/app/migrations/*.sql` in memory) plus a text scan of `App/migrations_pg/*.sql`. Verified: both sources give the same 26 columns today; 12 are pinned, 14 need an EXEMPT reason (in the file below).
- Anchors in docs, verbatim:
  - `docs/context/rules.md`: line `## Mail` (preceded by a blank line, after the `## Copy` bullets ending `- No em dashes in user-visible copy.`).
  - `AGENTS.md`: line `| Mail | [SES](docs/SES.md), [rules: mail](docs/context/rules.md#mail) |`.
  - `docs/context/test-map.md`: line starting `| Database, migrations | `.
  - `docs/context/decisions.md`: last line starts `- 2026-11-12 [door] 1149`.
- No em dashes anywhere in what you write. Never print guest data.
- This repo has no pre-built venv in some sandboxes; step 1 creates it if missing.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_sm_registry.py | create | the catch-all test |
| docs/context/rules.md | edit | new `## State machines` section |
| AGENTS.md | edit | one routing row |
| docs/context/test-map.md | edit | one row |
| docs/context/decisions.md | edit | one appended line |
| docs/tasks/1180-report.md | create | report |
| docs/tasks/1180-sm-standing-rule-and-catchall.md | edit | Status: review |

No other file may change. No App/app change, no migration, no dependency, no template.

## 4. Steps

### Step 1: Environment

Run from `App/`:

```
cd App && ls .venv/bin/python || (python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt) 2>&1 | tail -5; .venv/bin/python -m pytest tests/test_sm_go_parity.py -q --tb=short -x 2>&1 | tail -5
```

Expected: all green (`14 passed` at base), 0 failed. If it fails, STOP (§8).

### Step 2: Create `App/tests/test_sm_registry.py`

Write exactly this content:

```python
"""1180: every stored state/status column is pinned by a TRANSITIONS table or exempt with a reason.

The columns come from the real schema: the SQLite schema the app builds
(SCHEMA, ADDED_COLUMNS and the numbered migrations) plus a text scan of
App/migrations_pg/*.sql, so a column added to only one backend still shows up.
A new `state`, `status`, `*_state` or `*_status` column fails here until it has
a pin test (test_sm_<machine>.py) or an EXEMPT line with a reason.
"""
from __future__ import annotations

import re
from pathlib import Path

from app import db
from test_sm_go_parity import PYTHON_TABLES

APP = Path(__file__).resolve().parents[1]
COLUMN_RE = re.compile(r"(^|_)(state|status)$")
PG_TABLE_RE = re.compile(r"^CREATE TABLE (?:IF NOT EXISTS )?(?:public\.)?(\w+) \(", re.MULTILINE)
PG_COLUMN_RE = re.compile(r"^\s+(\w+)\s+(?:text|bigint|integer|boolean|smallint|numeric|character)", re.MULTILINE | re.IGNORECASE)
PG_ADD_RE = re.compile(r"ALTER TABLE\s+(?:ONLY\s+)?(?:public\.)?(\w+)\s+ADD COLUMN\s+(?:IF NOT EXISTS\s+)?(\w+)", re.IGNORECASE)

PINNED = set(PYTHON_TABLES)

# "table.column": why it has no TRANSITIONS table. Keep each reason to one line.
EXEMPT = {
    "bank_payment.status": "CHECK of 4 values, one writer (bank_import).",
    "billing_month_snapshot.status": "Copy of billing_account.status taken once a month; never updated.",
    "cleaning_event.state": "CHECK of 3 values, written by the calendar sync only.",
    "data_subject_request.status": "CHECK of 5 values, one writer (dsr).",
    "guest.manual_prev_state": "Stores the submit_state an undo restores; the machine is guest.submit_state.",
    "guest_question.status": "CHECK of 3 values, one writer.",
    "guide_item.state": "CHECK, one writer (guide facts).",
    "ical_feed.last_status": "Result of the last fetch, overwritten every poll; no transitions.",
    "invoice.vat_status": "Snapshot of the seller's VAT status at issue; never changes.",
    "legal_entity.vat_status": "Fact about the company set by the host, not a lifecycle.",
    "lock_account.status": "Connection health of a smart-lock account; set by the lock sync.",
    "push_outbox.last_status": "Last HTTP result text of a push attempt; the machine is push_outbox.state.",
    "reservation.status": "Two values (confirmed, cancelled).",
    "stripe_account.onboarding_state": "Mirrors Stripe; Stripe decides the transitions.",
}

HELP = (
    "New or unlisted state/status column(s): {names}.\n"
    "Either add a TRANSITIONS table in the owning module, a pin test "
    "App/tests/test_sm_<machine>.py and (if Go writes it) a twin in "
    "go/internal/statemachine/tables.go plus a PYTHON_TABLES entry in "
    "test_sm_go_parity.py, or add \"table.column\" to EXEMPT in "
    "App/tests/test_sm_registry.py with a one-line reason. "
    "Rules: docs/context/rules.md#state-machines"
)


def _sqlite_columns() -> set:
    found = set()
    for table, columns in db._expected_sqlite_columns().items():
        for column in columns:
            if COLUMN_RE.search(column[0]):
                found.add(f"{table}.{column[0]}")
    return found


def _postgres_columns() -> set:
    found = set()
    for path in sorted((APP / "migrations_pg").glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for block in re.split(r"(?m)^(?=CREATE TABLE )", text):
            head = PG_TABLE_RE.match(block)
            if not head:
                continue
            body = block.split("\n);", 1)[0]
            for column in PG_COLUMN_RE.findall(body):
                if COLUMN_RE.search(column):
                    found.add(f"{head.group(1)}.{column}")
        for table, column in PG_ADD_RE.findall(text):
            if COLUMN_RE.search(column):
                found.add(f"{table}.{column}")
    return found


def discovered() -> set:
    return _sqlite_columns() | _postgres_columns()


def test_every_state_column_is_pinned_or_exempt():
    missing = sorted(discovered() - PINNED - set(EXEMPT))
    assert not missing, HELP.format(names=", ".join(missing))


def test_exempt_entries_are_current():
    found = discovered()
    stale = sorted(set(EXEMPT) - found)
    assert not stale, f"EXEMPT lists columns that no longer exist: {', '.join(stale)}. Remove them."
    both = sorted(set(EXEMPT) & PINNED)
    assert not both, f"Pinned machines must not be in EXEMPT: {', '.join(both)}. Remove them."
    assert all(reason.strip() for reason in EXEMPT.values()), "Every EXEMPT entry needs a reason."


def test_pinned_columns_exist():
    gone = sorted(PINNED - discovered())
    assert not gone, f"PYTHON_TABLES names columns that do not exist: {', '.join(gone)}"
```

Run: `cd App && .venv/bin/python -m pytest tests/test_sm_registry.py -q --tb=short -x 2>&1 | tail -15`
Expected: `3 passed`. If `test_every_state_column_is_pinned_or_exempt` lists a column, the schema changed since this brief: STOP (§8), do not guess a reason.

### Step 3: Sabotage check (proves the message is helpful)

```
cd App && sed -i '/"reservation.status"/d' tests/test_sm_registry.py && .venv/bin/python -m pytest tests/test_sm_registry.py -q --tb=short -x 2>&1 | tail -12; git status --short | tail -5
```

Expected: 1 failed, message starts `New or unlisted state/status column(s): reservation.status.` and names `docs/context/rules.md#state-machines`. The file is untracked, so restore the deleted line by hand with Edit: in EXEMPT, after the `"push_outbox.last_status"` line, insert exactly
`    "reservation.status": "Two values (confirmed, cancelled).",`
Then run: `cd App && .venv/bin/python -m pytest tests/test_sm_registry.py -q --tb=short 2>&1 | tail -5`
Expected: `3 passed`.

### Step 4: Rule section in `docs/context/rules.md`

Insert before the line `## Mail` (keep one blank line before and after) this exact block:

```
## State machines

- Every stored state/status column has one `TRANSITIONS` table in its owning module, next to the state constants.
- Each table has a pin test `App/tests/test_sm_<machine>.py`.
- If Go writes the column, the table has a twin in `go/internal/statemachine/tables.go`, covered by `test_sm_go_parity.py`.
- Writes are one atomic `UPDATE ... SET state = ? WHERE id = ? AND state IN (...)`, never read-then-write.
- A column written in both languages is changed in both in one PR.
- Code is the truth and docs describe it; a disagreement goes to the owner.
- Derived or computed labels have no stored state and need no table.
- `App/tests/test_sm_registry.py` enforces this: a new column needs a table and pin test, or an `EXEMPT` line with a reason. History: docs/plans/explicit-state-machines.md and docs/plans/explicit-state-machines-rounds-2-4.md.

```

Run: `grep -n -A3 '^## State machines' docs/context/rules.md | tail -6; grep -c '^## ' docs/context/rules.md`
Expected: the heading and first bullet shown; count is 10.

### Step 5: Routing row in `AGENTS.md`

Edit: after the line
`| Mail | [SES](docs/SES.md), [rules: mail](docs/context/rules.md#mail) |`
add the line
`| State or status column, transitions | [rules: state machines](docs/context/rules.md#state-machines) |`

Run: `git diff --stat AGENTS.md | tail -3`
Expected: `1 insertion(+)`.

### Step 6: Row in `docs/context/test-map.md`

After the line starting `| Database, migrations | ` add:
`| State or status columns, transitions | `test_sm_*.py` (includes `test_sm_registry.py` and `test_sm_go_parity.py`) |`

Run: `git diff --stat docs/context/test-map.md | tail -3`
Expected: `1 insertion(+)`.

### Step 7: Decision line

Append as a new last line of `docs/context/decisions.md` (same format as its last line):
`- 2026-11-13 [workflow] 1180: every stored state/status column gets a TRANSITIONS table and pin test, or an EXEMPT reason; enforced by test_sm_registry.py (owner).`

Run: `tail -2 docs/context/decisions.md | cut -c1-120`
Expected: the 1149 line, then the 1180 line.

### Step 8: Lint and tests

Run both from §6. Expected: tests `... passed`, lint no errors.

## 5. Do not touch

`App/app/`, `go/`, `App/migrations_pg/`, any other test, templates, CSS. Hard rules: 3 (public repo, no secrets), 4 (no dependency), 5 (no SQL change), 8 (never push to `main`).

## 6. Commands

```
cd App && .venv/bin/python -m pytest tests/test_sm_registry.py tests/test_sm_go_parity.py -q --tb=short -x 2>&1 | tail -30
```
Expected: `17 passed` (3 new plus 14 of go parity), 0 failed, 0 skipped.

```
python3 scripts/context_lint.py 2>&1 | tail -30
```
Expected: no errors (warnings that exist at base are fine).

```
git status --short | tail -10
```
Expected: only the files in §3 (plus the report).

## 7. Acceptance

- [ ] `test_sm_registry.py`: 3 tests pass (command in §6).
- [ ] Sabotage showed the failure message naming `docs/context/rules.md#state-machines`, and the line is restored (`grep -c reservation.status App/tests/test_sm_registry.py` prints 1).
- [ ] `grep -n 'state-machines' AGENTS.md docs/context/rules.md docs/context/test-map.md | tail -5` shows the AGENTS.md row and the rules anchor.
- [ ] `git status --short` lists only §3 files.
- [ ] Context lint clean.

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

Write `docs/tasks/1180-report.md` (600 tokens at most) and set `Status: review` there and in this brief. The report has: 1. files changed (`git diff --stat`, plus the new files); 2. each command with the last 5 lines of output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left.

Then commit on branch `claude/hopeful-ride-ovwq66` (`git add` the §3 files, message `1180: state machine standing rule and catch-all test`) and run `git push -u origin claude/hopeful-ride-ovwq66`. You have no gh or MCP: do not open a PR. The orchestrator opens the draft PR.

## Risk list (for the reviewer)

- `App/tests/test_sm_registry.py`: the discovery regexes (does a new column in `migrations_pg` or ADDED_COLUMNS get caught?) and each EXEMPT reason being true.
- `docs/context/rules.md`: the atomic-UPDATE bullet is a rule for future code, not a claim every writer already follows.

## Owner steps

1. Nothing to click. When the orchestrator opens the draft PR and CI is green, merge with `scripts/merge-pr-on-green.sh`.
