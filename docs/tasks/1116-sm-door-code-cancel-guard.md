# 1116: `_handle_cancellations` overwrites a door code that `issue` has just claimed: guard both writes

Status: todo
Depends on: PR #920 merged to main (tables and pin tests present) | Base commit: main after PR #920 | Branch: task/1116-sm-door-code-cancel-guard
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## Open questions

The executor does nothing in this section. It is for the orchestrator, the reviewer and the next brief. Line numbers are in `App/app/door_codes.py` on PR #920's branch, before step 2 of this brief.

1. **The fault is real; the reported consequence is partly wrong.**
   - The two writers can run at the same time. `reconcile()` (and so `_handle_cancellations`) runs in the scheduler: the APScheduler job `door_codes`, `max_instances=1` (`App/app/scheduler.py:672-673`), or the job queue. `issue()` also runs from web requests: `on_registration_complete` (`door_codes.py:1293`) is called with `run_in_threadpool` from `App/app/routes/guest.py:2714` and `App/app/routes/admin.py:4187`, and directly from `App/app/headcount.py:255`. The scheduler holds `scheduler.lock`; the web workers do not. So the two are not serialised in one loop.
   - The race happens like this. `_handle_cancellations` reads a `pending` row of a cancelled stay (SELECT at `:875`). `issue` then claims it, setting `issuing` (`:446`). The unguarded write at `:884` then sets it to `revoked`. `issuing -> revoked` is not in `TRANSITIONS`.
   - What it does **not** do: leave a cancelled stay holding a live `issued` code. After its claim, `issue` checks the stay again (`still`, `:463`; it needs `r.status = 'active' AND r.archived_at IS NULL`). The SELECT only saw the row because the stay was already cancelled. So `issue` gives up and calls `_release_issue_claim` (`:469`), whose unguarded write (`:115`) puts `revoked` back to `pending`. The next run revokes it. That heals.
   - The harmful case needs the stay to come back (a calendar revival or an archive undo) between the SELECT and `issue`'s `still` check. Then `issue` goes on to create the TTLock code while the row is `revoked`. In the same run, `_handle_cancellations`' "reactivated" step (`:922-930`) deletes `revoked` rows of active stays. `issue`'s `issued` write (`:607`, `WHERE id = ?`) then updates zero rows. The PIN is live on the lock with no row, so UbyHost never deletes it. `ensure_row` creates a new row on the next run and issues a second code. Test 2 below reproduces the delete.
2. **Tried with system python3, outside both trees** (App/.venv does not exist here). I copied `door_codes.py` to the scratchpad with stub modules and an in-memory SQLite `db`, and drove the same interleaving as tests 1 and 2. Today's code: test 1 ends `revoked`, test 2 ends with the row deleted. With the step 2 and 3 diffs, both end `issuing`. I also ran the pin-test parser (`_writes_in`, `test_every_state_write_in_door_codes_is_pinned`, `test_transitions_list_exactly_the_pinned_moves` and the other in-file tests) against the patched file with the step 4 and 5 pins: all pass. I could not run the real pytest files below; the executor runs them.
3. **The `revoke_pending` guard (`:891`) is defensive.** I found no writer that can move an `issued` row while `_handle_cancellations` runs. `issue` cannot claim `issued`. The other `issued` movers (`_handle_moves`, the expiry UPDATE in `reconcile`) run in the same `reconcile()` call, one after another. There is no failing test for it, only its pin and a control test.
4. **Zero rows updated.** `_handle_cancellations` already ignores the return value of `db.execute`. The fix adds no branch. The row is skipped in this run, and later runs handle it as follows:
   - `issue` releases the claim (stay still cancelled): `pending`. The next `reconcile` revokes it through the guarded `:884` write (its `_issue_due` may first claim and release it once more).
   - `issue` writes `issued`: the next run's `issued` branch (`:889`) sets `revoke_pending`, and `_revoke_one` deletes the code from the lock.
   - `issue` writes `retrying`: revoked on the next run. `failed`: stays `failed`; no code was created.
   - The issuing worker dies and the row stays `issuing`: the stale-lease reset in `reconcile` (`:1263-1267`, `WHERE state = issuing AND claimed_at < now - LEASE_MINUTES`) sets `retrying`. It runs after `_handle_cancellations` in the same call. The run after that revokes the row.
5. **Pre-existing, not fixed here.** A worker can die after TTLock created the code but before the `issued` write. The row then goes `issuing -> retrying -> revoked` for a cancelled stay, and the code is never deleted from the lock. `_handle_cancellations` revokes `pending`/`retrying` rows without calling `ttlock.delete_code`. For a row with `attempts > 0`, revoking could look the code up by name first (as `issue` does at `:510`). That needs an owner decision; it is not a one-line guard.
6. **Next brief's scope: `issue`'s lease-dependent unguarded writes** (`WHERE id = ?` with no state condition; they trust the 2-minute claim lease from `:446`). If a TTLock call outlives the lease, the stale-lease reset (`:1264`) sets `retrying`, another worker may claim the row, and the late write overwrites that worker's state. The race above also reaches them: `_release_issue_claim` at `:115` writes `pending` over `revoked`. Each should gain `AND state = ?` (ISSUING):
   - `App/app/door_codes.py:109` and `:115` `_release_issue_claim` -> pending (called from `issue` at `:469`, `:474`, `:486`, `:554`)
   - `:491` -> expired (guards only `attempts > 0`)
   - `:592` -> retrying (period taken)
   - `:607` -> issued
   - `:660`, `:704`, `:736` -> failed or retrying
   - `:535`, `:649`, `:694` change `last_error` or `attempts` without a state guard; they are not state writes, but they have the same lease dependency.
7. No Go twin: `test_no_go_file_writes_door_code` in `App/tests/test_sm_door_code_state.py` asserts that no Go file writes `door_code`. The language rule keeps door codes in Python.

## 1. Objective

Add a state guard to both writes in `_handle_cancellations` so that a door code that `issue()` claimed after the cancellation SELECT is left alone, instead of being set to `revoked` (and, if the stay came back, deleted while its TTLock code is being created). One new test file shows the fault first, and the round 1 pin test is updated for the two guards.

## 2. Context

Rules that apply (AGENTS.md): SQL only through `App/app/db.py` helpers, Postgres-portable; no new dependency; never push to `main`. A fix keeps the atomic `UPDATE ... WHERE ... AND state = ?` form; it never adds a read-then-write.

`db.execute` returns the number of rows changed (`App/app/db.py`, `def execute(sql: str, params: Iterable[Any] = ()) -> int:`). `db.query` is `def query(sql: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:`; `door_codes` calls it as `db.query(...)`, so `monkeypatch.setattr(db, "query", ...)` intercepts its SELECT.

`App/app/door_codes.py`, the claim at the top of `issue` (the new test copies this SQL verbatim):

```python
    claimed = db.execute(
        "UPDATE door_code SET state = ?, claimed_at = ?, attempts = attempts + 1, updated_at = ? "
        "WHERE id = ? AND state IN (?, ?) AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
        "AND (claimed_at IS NULL OR claimed_at < ?)",
        (ISSUING, now_iso, now_iso, door_code_id, PENDING, RETRYING, now_iso, lease_cutoff),
    )
```

`App/app/door_codes.py`, `_handle_cancellations`, today (the two writes this brief changes):

```python
def _handle_cancellations(now_iso: str) -> None:
    rows = db.query(
        "SELECT dc.* FROM door_code dc "
        "JOIN reservation r ON r.id = dc.reservation_id "
        "WHERE (r.status != 'active' OR r.archived_at IS NOT NULL)"
    )
    for row in rows:
        state = row["state"]
        if state in (PENDING, RETRYING):
            db.execute(
                "UPDATE door_code SET state = ?, claimed_at = NULL, updated_at = ? WHERE id = ?",
                (REVOKED, now_iso, row["id"]),
            )
        elif state == ISSUED and row["valid_to"]:
            end_ms = _iso_to_ms(row["valid_to"])
            if end_ms > int(_now().timestamp() * 1000):
                db.execute(
                    "UPDATE door_code SET state = ?, attempts = 0, next_attempt_at = ?, "
                    "claimed_at = NULL, updated_at = ? WHERE id = ?",
                    (REVOKE_PENDING, now_iso, now_iso, row["id"]),
                )
```

Further down in the same function, the step that turns test 2's `revoked` row into a deleted row:

```python
    for item in reactivated:
        db.execute("DELETE FROM door_code WHERE id = ?", (item["id"],))
```

`App/tests/test_sm_door_code_state.py` parses each `UPDATE door_code SET state = ?` and reads the guard from `state = ?` or `state IN (?, ?)` in its WHERE clause. The parameters must be the named constants (`PENDING`, `RETRYING`, `ISSUED`) for the parser to resolve them. The `TRANSITIONS` table does not change: the moves stay `pending/retrying -> revoked` and `issued -> revoke_pending`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_door_code_cancel_guard.py` | create | 4 tests: 2 fail today, 2 controls pass |
| `App/app/door_codes.py` | edit | 2 guards in `_handle_cancellations` |
| `App/tests/test_sm_door_code_state.py` | edit | 2 `PINNED` lines |
| `docs/tasks/1116-report.md` | create | report |
| `docs/tasks/1116-sm-door-code-cancel-guard.md` | edit | `Status:` line only |

No other file may change.

## 4. Steps

Run every command from `App/` unless the step says otherwise.

### Step 1: add the failing test

Create `App/tests/test_door_code_cancel_guard.py` with exactly this content:

```python
"""1116: the cancellation pass must not overwrite a row that issue() has claimed.

_handle_cancellations reads the door codes of cancelled stays with one SELECT
and writes each row afterwards. issue() also runs outside the scheduler (the
guest registration request calls on_registration_complete), so it can claim a
pending row in between. These tests run issue()'s claim at that moment by
wrapping db.query: no threads, no sleeps.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import db, deadlines, door_codes

PREFIX = "dc-cguard-"
_counter = 0

CANCEL_SELECT = "SELECT dc.* FROM door_code dc"
# The claim UPDATE at the top of door_codes.issue, verbatim.
CLAIM_SQL = (
    "UPDATE door_code SET state = ?, claimed_at = ?, attempts = attempts + 1, updated_at = ? "
    "WHERE id = ? AND state IN (?, ?) AND (next_attempt_at IS NULL OR next_attempt_at <= ?) "
    "AND (claimed_at IS NULL OR claimed_at < ?)"
)


@pytest.fixture(autouse=True)
def _env():
    db.init_db()
    _purge()
    yield
    _purge()


def _purge():
    for owner in db.query("SELECT id FROM user_account WHERE username LIKE ?", (PREFIX + "%",)):
        oid = owner["id"]
        for apt in db.query("SELECT id FROM apartment WHERE owner_user_id = ?", (oid,)):
            db.execute("DELETE FROM alert WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM email_outbox WHERE owner_user_id = ?", (oid,))
            db.execute("DELETE FROM door_code WHERE apartment_id = ?", (apt["id"],))
            db.execute("DELETE FROM reservation WHERE apartment_id = ?", (apt["id"],))
        db.execute("DELETE FROM audit WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM lock_account WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM apartment WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM legal_entity WHERE owner_user_id = ?", (oid,))
        db.execute("DELETE FROM user_account WHERE id = ?", (oid,))


def _cancelled_stay() -> tuple[int, int]:
    """A registered manual stay on a property with a lock, then cancelled. Returns apartment, stay."""
    global _counter
    _counter += 1
    now = db.utcnow()
    owner = db.insert(
        "user_account",
        {
            "username": f"{PREFIX}{_counter}",
            "display_name": "Host",
            "password_hash": "x",
            "role": "host",
            "created_at": now,
        },
    )
    entity = db.insert(
        "legal_entity",
        {
            "name": "Guard",
            "seat": "Praha",
            "created_at": now,
            "owner_user_id": owner,
            "contact_email": "host@example.test",
        },
    )
    apartment = db.insert(
        "apartment",
        {
            "legal_entity_id": entity,
            "owner_user_id": owner,
            "internal_name": "Flat",
            "permalink_token": f"{PREFIX}tok-{_counter}",
            "automation_mode": "manual",
            "default_purpose": "10",
            "active": 1,
            "created_at": now,
            "lock_provider": "ttlock",
            "lock_id": "35662508",
            "checkin_hour": 10,
            "checkout_hour": 15,
        },
    )
    today = deadlines.local_now().date()
    stay = db.insert(
        "reservation",
        {
            "apartment_id": apartment,
            "source": "manual",
            "uid": f"{PREFIX}stay-{_counter}",
            "date_from": today.isoformat(),
            "date_to": (today + timedelta(days=1)).isoformat(),
            "status": "cancelled",
            "registration_completed_at": now,
            "created_at": now,
            "updated_at": now,
        },
    )
    return apartment, stay


def _code(apartment: int, stay: int, state: str, valid_to: str | None = None) -> int:
    now = db.utcnow()
    values = {
        "reservation_id": stay,
        "apartment_id": apartment,
        "lock_id": "35662508",
        "code_kind": "random",
        "state": state,
        "attempts": 0,
        "created_at": now,
        "updated_at": now,
    }
    if valid_to is not None:
        values["valid_to"] = valid_to
        values["pin_enc"] = db.encrypt_field("4821937")
        values["provider_code_id"] = "pid-1"
        values["issued_at"] = now
    return db.insert("door_code", values)


def _state(row_id: int):
    row = db.query_one("SELECT state FROM door_code WHERE id = ?", (row_id,))
    return row["state"] if row else None


def _claim(row_id: int) -> int:
    """Run issue()'s claim on the row, as a guest request would."""
    now = door_codes._now()
    now_iso = door_codes._iso(now)
    cutoff = door_codes._iso(now - timedelta(minutes=door_codes.LEASE_MINUTES))
    return db.execute(
        CLAIM_SQL,
        (
            door_codes.ISSUING,
            now_iso,
            now_iso,
            row_id,
            door_codes.PENDING,
            door_codes.RETRYING,
            now_iso,
            cutoff,
        ),
    )


def _claim_after_select(monkeypatch, row_id: int, revive_stay: int | None = None) -> dict:
    """Claim the row right after _handle_cancellations' SELECT has read it."""
    real_query = db.query
    seen: dict = {}

    def query(sql, params=()):
        rows = real_query(sql, params)
        if not seen and sql.startswith(CANCEL_SELECT):
            if revive_stay is not None:
                db.execute(
                    "UPDATE reservation SET status = 'active' WHERE id = ?", (revive_stay,)
                )
            seen["claimed"] = _claim(row_id)
        return rows

    monkeypatch.setattr(db, "query", query)
    return seen


def test_a_row_claimed_after_the_select_is_not_revoked(monkeypatch):
    apartment, stay = _cancelled_stay()
    row_id = _code(apartment, stay, door_codes.PENDING)
    seen = _claim_after_select(monkeypatch, row_id)

    door_codes._handle_cancellations(db.utcnow())

    assert seen == {"claimed": 1}
    assert _state(row_id) == door_codes.ISSUING


def test_a_claimed_row_is_not_deleted_when_the_stay_comes_back(monkeypatch):
    # Revived between the SELECT and issue()'s eligibility check: issue() goes
    # on to create the TTLock code, so its row must still be there.
    apartment, stay = _cancelled_stay()
    row_id = _code(apartment, stay, door_codes.PENDING)
    seen = _claim_after_select(monkeypatch, row_id, revive_stay=stay)

    door_codes._handle_cancellations(db.utcnow())

    assert seen == {"claimed": 1}
    assert _state(row_id) == door_codes.ISSUING


def test_an_unclaimed_pending_row_of_a_cancelled_stay_is_revoked():
    apartment, stay = _cancelled_stay()
    row_id = _code(apartment, stay, door_codes.PENDING)

    door_codes._handle_cancellations(db.utcnow())

    assert _state(row_id) == door_codes.REVOKED


def test_an_issued_row_of_a_cancelled_stay_goes_to_revoke_pending(monkeypatch):
    monkeypatch.setattr(door_codes, "_revoke_one", lambda row_id: None)
    future = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0).isoformat()
    apartment, stay = _cancelled_stay()
    row_id = _code(apartment, stay, door_codes.ISSUED, valid_to=future)

    door_codes._handle_cancellations(db.utcnow())

    assert _state(row_id) == door_codes.REVOKE_PENDING
```

Command (this one run is without `-x`, so that all four results show):

```
.venv/bin/python -m pytest tests/test_door_code_cancel_guard.py -q --tb=line 2>&1 | tail -30
```

Expected: `2 failed, 2 passed`. The failures are `test_a_row_claimed_after_the_select_is_not_revoked` (`assert 'revoked' == 'issuing'`) and `test_a_claimed_row_is_not_deleted_when_the_stay_comes_back` (`assert None == 'issuing'`). Any other result: STOP (§8). Commit: `1116 step 1`.

### Step 2: guard the revoke write

File `App/app/door_codes.py`, function `_handle_cancellations`. Anchor:

```
grep -nF '"UPDATE door_code SET state = ?, claimed_at = NULL, updated_at = ? WHERE id = ?",' app/door_codes.py
```

Expected: exactly one line (about line 884). Apply this diff:

```diff
         if state in (PENDING, RETRYING):
+            # Guarded: issue() may have claimed the row since the SELECT. Zero
+            # rows updated leaves it to issue(); the next run sees its new state.
             db.execute(
-                "UPDATE door_code SET state = ?, claimed_at = NULL, updated_at = ? WHERE id = ?",
-                (REVOKED, now_iso, row["id"]),
+                "UPDATE door_code SET state = ?, claimed_at = NULL, updated_at = ? "
+                "WHERE id = ? AND state IN (?, ?)",
+                (REVOKED, now_iso, row["id"], PENDING, RETRYING),
             )
```

Command:

```
.venv/bin/python -m pytest tests/test_door_code_cancel_guard.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `4 passed`. Commit: `1116 step 2`.

### Step 3: guard the revoke_pending write

File `App/app/door_codes.py`, same function. Anchor:

```
grep -nF '(REVOKE_PENDING, now_iso, now_iso, row["id"]),' app/door_codes.py
```

Expected: exactly one line (about line 894). Apply this diff:

```diff
                 db.execute(
                     "UPDATE door_code SET state = ?, attempts = 0, next_attempt_at = ?, "
-                    "claimed_at = NULL, updated_at = ? WHERE id = ?",
-                    (REVOKE_PENDING, now_iso, now_iso, row["id"]),
+                    "claimed_at = NULL, updated_at = ? WHERE id = ? AND state = ?",
+                    (REVOKE_PENDING, now_iso, now_iso, row["id"], ISSUED),
                 )
```

Command:

```
.venv/bin/python -m pytest tests/test_door_code_cancel_guard.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `4 passed`. Commit: `1116 step 3`.

### Step 4: pin the guarded revoke write

File `App/tests/test_sm_door_code_state.py`, list `PINNED`. Anchor:

```
grep -nF '("_handle_cancellations", ANY, ("pending", "retrying"), ("revoked",)),' tests/test_sm_door_code_state.py
```

Expected: one line. Diff:

```diff
-    ("_handle_cancellations", ANY, ("pending", "retrying"), ("revoked",)),
+    ("_handle_cancellations", ("pending", "retrying"), ("pending", "retrying"), ("revoked",)),
```

No command yet (the pin test still fails until step 5). Commit: `1116 step 4`.

### Step 5: pin the guarded revoke_pending write

Same file. Anchor:

```
grep -nF '("_handle_cancellations", ANY, ("issued",), ("revoke_pending",)),' tests/test_sm_door_code_state.py
```

Expected: one line. Diff:

```diff
-    ("_handle_cancellations", ANY, ("issued",), ("revoke_pending",)),
+    ("_handle_cancellations", ("issued",), ("issued",), ("revoke_pending",)),
```

Command:

```
.venv/bin/python -m pytest tests/test_sm_door_code_state.py -q --tb=short -x 2>&1 | tail -30
```

Expected: all passed, 0 failed. `TRANSITIONS` in `door_codes.py` is not changed: the moves are the same. Commit: `1116 step 5`.

### Step 6: test-map row for door codes

```
.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_sm_door_code_state.py -q --tb=short -x -rs 2>&1 | tail -30
```

Expected: 0 failed. This brief changes no template, so skips are allowed only in `tests/test_door_code_window_browser.py`; list them in the report under Deviations and do not try to fix them. Any other skip or a failure: fix once per §8, else STOP.

### Step 7: context lint

From the repo root:

```
python3 scripts/context_lint.py 2>&1 | tail -30
```

Expected: last line `context lint: OK`, and no ERROR or WARN line naming `1116`. If the only ERROR is `docs/context/decisions.md: ... > cap` (it was already failing on 2026-11-11, before this brief), record it under Deviations and go on. Do not edit `decisions.md`.

### Step 8: report

Write `docs/tasks/1116-report.md` (§9), set this brief's `Status:` line to `Status: review`, commit `1116 step 8`, open one draft PR from `task/1116-sm-door-code-cancel-guard`.

## 5. Do not touch

- `issue`, `_release_issue_claim`, `_revoke_one`, `_keep_issued`, `_handle_moves`, `reconcile` and the `TRANSITIONS`/`STATES` block in `App/app/door_codes.py`. Only the two writes in `_handle_cancellations` change.
- Every other file in `App/tests/`, including `test_door_codes_safeguards.py`.
- `go/`, `.github/`, migrations. No schema change, no new dependency.
- Hard rules: SQL through `db` helpers only; never push to `main`; merge only with `scripts/merge-pr-on-green.sh` (the orchestrator does that, not you).

## 6. Commands

| Step | Command (from `App/` unless noted) | Expected |
|---|---|---|
| 1 | `.venv/bin/python -m pytest tests/test_door_code_cancel_guard.py -q --tb=line 2>&1 \| tail -30` | `2 failed, 2 passed` |
| 2, 3 | `.venv/bin/python -m pytest tests/test_door_code_cancel_guard.py -q --tb=short -x 2>&1 \| tail -30` | `4 passed` |
| 5 | `.venv/bin/python -m pytest tests/test_sm_door_code_state.py -q --tb=short -x 2>&1 \| tail -30` | all passed |
| 6 | `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_sm_door_code_state.py -q --tb=short -x -rs 2>&1 \| tail -30` | 0 failed |
| 7 | repo root: `python3 scripts/context_lint.py 2>&1 \| tail -30` | `context lint: OK` |

## 7. Acceptance

- [ ] Step 1 output shows `2 failed, 2 passed` on the unchanged `door_codes.py` (pasted in the report).
- [ ] `grep -nF 'row["id"], PENDING, RETRYING)' App/app/door_codes.py` and `grep -nF 'row["id"], ISSUED)' App/app/door_codes.py` each find exactly one line.
- [ ] `tests/test_door_code_cancel_guard.py`: 4 passed.
- [ ] `tests/test_sm_door_code_state.py`: all passed; the only change in it is the two `PINNED` lines.
- [ ] `git diff main --stat` lists only the files in §3.
- [ ] The step 6 row has 0 failed.
- [ ] Context lint OK.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found, or found more than once;
- step 1 does not give `2 failed, 2 passed`;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push to `main`, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1116-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output (step 1 in full: the two failing assertions).
3. §7 ticked.
4. Deviations (including any skips in step 6).
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read these in full:

- `App/app/door_codes.py` `_handle_cancellations`: the diff is the two WHERE clauses, their parameter tuples and one two-line comment. Check that the guard states equal the Python branch (`PENDING, RETRYING` and `ISSUED`). Check that nothing reads the row count (zero rows means skip this run; see Open questions 4).
- `App/tests/test_door_code_cancel_guard.py`: `CLAIM_SQL` must match `issue`'s claim verbatim. The `db.query` wrapper must act once, only on the `SELECT dc.* FROM door_code dc` query, and test 1 and 2 must assert `seen == {"claimed": 1}`, so that the interleaving actually ran.
- `App/tests/test_sm_door_code_state.py`: only the two `_handle_cancellations` entries in `PINNED` change, from `ANY` to the guard tuples; `TRANSITIONS` does not change.

## Owner steps

None. The orchestrator reviews the PR and merges it with `scripts/merge-pr-on-green.sh` when it is green.
