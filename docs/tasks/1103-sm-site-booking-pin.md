# 1103: Pin every write of site_booking.status against its transition table

Status: review
Depends on: none | Base commit: 70fe25b0 | Branch: task/1103-sm-site-booking-pin
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add one test file, `App/tests/test_sm_site_booking.py`, that reads the Python writers of `site_booking.status` as text, finds every statement that writes it, compares them with a pinned list of (file, from-states, to-state), and asserts every pinned move is allowed by `booking_site._TRANSITIONS`. CI then fails when a write is added, removed or changed without the table being looked at ([plan](../plans/explicit-state-machines.md), round 1: declare and pin, no runtime change).

## 2. Context

Rules from the plan that bind this brief: the table lists what the code does today (derive, never design); writers are not edited; no migration, no dependency, no template or copy change. Go files are read by the test, never changed.

Excerpts (each must exist verbatim; if one is not found, STOP, section 8).

`App/app/booking_site.py`:

```python
_TRANSITIONS = {
    "pending": {"paid", "expired", "clash_refunded"},
    "requested": {"paid", "expired", "cancelled"},
    "paid": {"cancelled", "refunded", "clash_refunded"},
    "cancelled": {"refunded"},
    "expired": {"paid", "clash_refunded", "cancelled"},
    "refunded": set(),
    "clash_refunded": set(),
}
```

and `set_status` builds `sql = "UPDATE site_booking SET status = ?, updated_at = ?"` and checks `if status not in _TRANSITIONS[row["status"]]`.

Direct writers that bypass `set_status` (all use `WHERE ... AND status IN (...)` as the atomic compare-and-swap):

- `App/app/booking_direct.py`, `confirm`: `"UPDATE site_booking SET status = 'paid', reservation_id = ?, paid_at = ?,"` ... `" updated_at = ? WHERE id = ? AND status IN ('requested', 'expired')"`.
- `App/app/booking_direct.py`, `decline`: `"UPDATE site_booking SET status = 'cancelled', cancelled_at = ?, updated_at = ?"` ... `" WHERE id = ? AND status IN ('requested', 'expired')"`.
- `App/app/booking_webhook.py`, `_confirm`: `"UPDATE site_booking SET status = 'paid', reservation_id = ?,"` ... `" WHERE id = ? AND status IN ('pending', 'expired')"`.

Callers of `booking_site.set_status` with a literal target (the table check runs at runtime there):

| File | To | From (read from the code around the call) |
|---|---|---|
| `App/app/booking_cancel.py` (line 49) | `cancelled` | `paid` |
| `App/app/booking_cancel.py` (line 70) | `refunded` | `cancelled` |
| `App/app/booking_checkout.py` (line 116) | `expired` | `pending` (a booking just created) |
| `App/app/booking_checkout.py` (line 167, `expire_requests`) | `expired` | `requested` |
| `App/app/booking_webhook.py` (line 47, `_expire`) | `expired` | `pending` |
| `App/app/booking_webhook.py` (line 117, `_refund_clash`) | `clash_refunded` | `pending` or `expired` (the `_confirm` guard) |

Row creation: `booking_site.create_pending` calls `db.insert("site_booking", {... "status": status ...})` after `if status not in ("pending", "requested"):`. It is the only use of the table name as a string for a db helper.

Other `UPDATE site_booking` statements (`attach_session` in `booking_site.py`, `booking_invoice.py`) do not write status and are ignored by the test. Go (`go/`) has no write to this table.

### Open questions (findings; this brief does not fix them)

1. Code versus table: none. Every direct SQL move and every `set_status` caller move is allowed by `_TRANSITIONS`.
2. Table versus code: `paid -> refunded` and `paid -> clash_refunded` are allowed by the table but no writer makes them today. The test pins them as `UNUSED_TABLE_MOVES` so any change to the table shows up. Whether to remove them is the orchestrator's decision, not this brief's.
3. Plan versus code: plan rule 2 says the table is named `TRANSITIONS`; in `booking_site.py` it is `_TRANSITIONS`. This brief keeps the name (renaming edits a writer module). The orchestrator decides whether a later brief renames it.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_sm_site_booking.py` | create | The pin test, full content in step 2 |

No other file may change.

## 4. Steps

1. Confirm the anchors. Run each command and compare with the expected output.

   ```
   grep -nF '"paid": {"cancelled", "refunded", "clash_refunded"},' App/app/booking_site.py | tail -30
   grep -nF "UPDATE site_booking SET status" App/app/booking_direct.py App/app/booking_webhook.py App/app/booking_site.py | tail -30
   grep -nF "booking_site.set_status(" App/app/booking_cancel.py App/app/booking_checkout.py App/app/booking_webhook.py | tail -30
   ```

   Expected: line 1 prints the `paid` row of the table (one line). Line 2 prints four lines: `booking_direct.py` twice (`'paid'`, `'cancelled'`), `booking_webhook.py` once (`'paid'`), `booking_site.py` once (`status = ?`). Line 3 prints six call lines (the table in section 2: two in `booking_cancel.py`, two in `booking_checkout.py`, two in `booking_webhook.py`). Any difference: STOP.

2. Create `App/tests/test_sm_site_booking.py` with exactly this content (nothing added, nothing removed):

```python
"""Pin every write of site_booking.status against booking_site._TRANSITIONS (brief 1103).

Reads the writer sources as text. Fails when a write is added, removed or
changed, and when a pinned move is not allowed by the table. Writers are not
edited by this test; the table lists only what the code does today.
"""
from __future__ import annotations

import re
from pathlib import Path

from app import booking_site

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
APP_PKG = APP / "app"

# Moves the code is known to make that the table does not allow:
# (from-state, to-state, reason). Empty: the code and the table agree.
KNOWN_EXCEPTIONS: set = set()

# 1. Direct SQL writers: (file, from-states in the WHERE ... status IN (...), to-state).
PINNED_SQL = [
    ("booking_direct.py", {"requested", "expired"}, "paid"),
    ("booking_direct.py", {"requested", "expired"}, "cancelled"),
    ("booking_webhook.py", {"pending", "expired"}, "paid"),
]

# 2. The one generic writer: set_status builds UPDATE ... SET status = ? itself.
PINNED_DYNAMIC = ["booking_site.py"]

# 3. Callers of booking_site.set_status with a literal target: (file, from-states, to-state).
#    The from-states are read from the code around the call by the brief author.
PINNED_CALLS = [
    ("booking_cancel.py", {"paid"}, "cancelled"),
    ("booking_cancel.py", {"cancelled"}, "refunded"),
    ("booking_checkout.py", {"pending"}, "expired"),
    ("booking_checkout.py", {"requested"}, "expired"),
    ("booking_webhook.py", {"pending"}, "expired"),
    ("booking_webhook.py", {"pending", "expired"}, "clash_refunded"),
]

# 3b. Moves the table allows that no writer makes today (see the brief's Open questions).
UNUSED_TABLE_MOVES = {("paid", "refunded"), ("paid", "clash_refunded")}

# 4. Row creation: the only place a status is first written.
PINNED_INSERT_FILES = ["booking_site.py"]
PINNED_INSERT_STATES = {"pending", "requested"}


def _py_files():
    return sorted(p for p in APP_PKG.rglob("*.py"))


def _joined(path: Path) -> str:
    """Source text with adjacent string literals on separate lines joined."""
    text = path.read_text(encoding="utf-8")
    return re.sub(r"\"\s*\n\s*\"", "", text)


def _update_statements(text: str):
    """Yield the SET part and the WHERE part of every UPDATE site_booking literal."""
    for m in re.finditer(r"UPDATE site_booking SET ([^\"]*)", text):
        parts = re.split(r"\bWHERE\b", m.group(1), maxsplit=1)
        yield parts[0], (parts[1] if len(parts) > 1 else "")


def _status_writers():
    """(file name, from-states or None, to-state or None) for every status UPDATE."""
    found = []
    for path in _py_files():
        for set_part, where_part in _update_statements(_joined(path)):
            if not re.search(r"\bstatus\s*=", set_part):
                continue
            to_match = re.search(r"\bstatus\s*=\s*'(\w+)'", set_part)
            from_match = re.search(r"\bstatus IN \(([^)]*)\)", where_part)
            froms = (frozenset(re.findall(r"'(\w+)'", from_match.group(1)))
                     if from_match else None)
            found.append((path.name, froms, to_match.group(1) if to_match else None))
    return found


def _set_status_calls():
    """(file name, to-state) for every booking_site.set_status call with a literal target."""
    found = []
    for path in _py_files():
        if path.name == "booking_site.py":
            continue
        text = _joined(path)
        for m in re.finditer(r"booking_site\.set_status\(\s*[^,]+,\s*\"(\w+)\"", text):
            found.append((path.name, m.group(1)))
        # a call whose target is not a literal would escape the pin
        calls = len(re.findall(r"booking_site\.set_status\(", text))
        literal = len(re.findall(r"booking_site\.set_status\(\s*[^,]+,\s*\"\w+\"", text))
        assert calls == literal, f"{path.name}: set_status with a non-literal target"
    return found


def test_scan_finds_something():
    """The scanners are not silently matching nothing."""
    assert len(_status_writers()) >= 4
    assert len(_set_status_calls()) >= 6


def test_direct_sql_writers_are_pinned():
    found = sorted(
        (f, tuple(sorted(froms)) if froms else None, to)
        for f, froms, to in _status_writers() if to is not None
    )
    pinned = sorted((f, tuple(sorted(froms)), to) for f, froms, to in PINNED_SQL)
    assert found == pinned, (
        "A direct UPDATE site_booking SET status = '...' changed. Update PINNED_SQL "
        "and make sure booking_site._TRANSITIONS allows the move."
    )


def test_dynamic_writer_is_pinned():
    found = sorted(f for f, froms, to in _status_writers() if to is None)
    assert found == sorted(PINNED_DYNAMIC), (
        "Only booking_site.set_status may write status = ? ; found " + repr(found)
    )


def test_set_status_callers_are_pinned():
    found = sorted(_set_status_calls())
    pinned = sorted((f, to) for f, froms, to in PINNED_CALLS)
    assert found == pinned, (
        "A booking_site.set_status caller changed. Update PINNED_CALLS."
    )


def test_no_other_code_touches_the_table_by_helper():
    """db.insert/update/update_in helpers take the table name as a string."""
    found = []
    for path in _py_files():
        text = path.read_text(encoding="utf-8")
        if re.search(r"""["']site_booking["']""", text):
            found.append(path.name)
    assert sorted(found) == sorted(PINNED_INSERT_FILES), found
    source = (APP_PKG / "booking_site.py").read_text(encoding="utf-8")
    assert len(re.findall(r"""db\.\w+\(\s*["']site_booking["']""", source)) == 1
    assert 'db.insert("site_booking"' in source
    assert 'if status not in ("pending", "requested"):' in source
    assert PINNED_INSERT_STATES == {"pending", "requested"}


def test_go_and_migrations_do_not_write_site_booking_status():
    go_dir = REPO / "go"
    for path in sorted(go_dir.rglob("*.go")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"UPDATE\s+site_booking", text, re.I), path
        assert not re.search(r"INSERT\s+INTO\s+site_booking", text, re.I), path
    for path in sorted((APP_PKG / "migrations").glob("*")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"UPDATE\s+site_booking", text, re.I), path


def test_every_pinned_move_is_in_the_table():
    moves = set()
    for _f, froms, to in PINNED_SQL + PINNED_CALLS:
        for frm in froms:
            moves.add((frm, to))
    for frm, to in sorted(moves):
        if (frm, to) in KNOWN_EXCEPTIONS:
            continue
        assert to in booking_site._TRANSITIONS[frm], f"{frm} -> {to} is not in _TRANSITIONS"


def test_table_states_match_statuses():
    table = booking_site._TRANSITIONS
    assert set(table) == set(booking_site.STATUSES)
    for to_states in table.values():
        assert to_states <= set(booking_site.STATUSES)


def test_table_has_no_unpinned_moves():
    """The table lists the pinned moves plus the known unused ones, nothing else."""
    used = {(frm, to) for _f, froms, to in PINNED_SQL + PINNED_CALLS for frm in froms}
    table = {(frm, to) for frm, tos in booking_site._TRANSITIONS.items() for to in tos}
    assert table - used == UNUSED_TABLE_MOVES
```

   Then run: `ls -l App/tests/test_sm_site_booking.py | tail -30`. Expected: the file is listed.

3. Run the test. From `App/`:

   ```
   .venv/bin/python -m pytest tests/test_sm_site_booking.py -q --tb=short -x 2>&1 | tail -30
   ```

   Expected: `9 passed`. If one fails, read the last 30 lines, fix the test file once (never a writer), and rerun. A second failure: STOP and report.

4. Prove the pin bites (do not keep this change). From `App/`, temporarily change `"UPDATE site_booking SET status = 'cancelled', cancelled_at = ?, updated_at = ?"` in `app/booking_direct.py` to say `'refunded'` instead of `'cancelled'` with `sed -i "s/SET status = 'cancelled'/SET status = 'refunded'/" app/booking_direct.py`, run the command from step 3, and expect a failure in `test_direct_sql_writers_are_pinned`. Then undo with `git checkout app/booking_direct.py` and run `git status --short | tail -30`. Expected: only `?? tests/test_sm_site_booking.py` (or `A`) is listed. If `booking_direct.py` still shows as modified, run `git checkout App/app/booking_direct.py` from the repo root.

5. Commit with message `1103 step 1` (one commit is fine for this brief; the file is complete after step 2): `git add App/tests/test_sm_site_booking.py && git commit -m "1103 step 1" | tail -30`.

## 5. Do not touch

- Any file under `App/app/` (writers and table stay as they are; step 4's edit is reverted), `go/`, migrations, templates, other tests.
- `docs/context/test-map.md` (the orchestrator adds the row at review).
- AGENTS.md hard rules that apply: 3 (public repo: no guest data in the test, none used), 4 (no new dependency: the test uses only `re` and `pathlib`), 8 (never push to `main`).

## 6. Commands

From `App/`:

```
.venv/bin/python -m pytest tests/test_sm_site_booking.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `9 passed`. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` (expected: no new error from this brief).

## 7. Acceptance

- [ ] `App/tests/test_sm_site_booking.py` exists with the content from step 2.
- [ ] The step 3 command prints `9 passed`.
- [ ] In step 4 the test failed with the writer changed, and `git diff --stat -- App/app go | tail -30` prints nothing afterwards.
- [ ] `git diff --stat main...HEAD | tail -30` lists only the new test file (plus the report).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found (step 1 prints something different);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change (especially a writer: if the test says a direct writer makes a move the table forbids, report it, do not fix it);
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1103-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions (copy the three open questions from section 2 if still unanswered).
6. Owner steps left.

Then open one PR as a draft.

## Risk list (for the reviewer)

`App/tests/test_sm_site_booking.py` only. Check the three pinned lists against section 2, and that `KNOWN_EXCEPTIONS` is empty.

## Owner steps

1. Open the draft PR for branch `task/1103-sm-site-booking-pin` on GitHub and wait for the checks to go green.
2. Tell the orchestrator it is green. The orchestrator merges with `scripts/merge-pr-on-green.sh` and adds the test-map row.
