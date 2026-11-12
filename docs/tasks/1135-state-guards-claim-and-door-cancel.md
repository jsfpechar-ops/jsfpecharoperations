# 1135: guard the last two unguarded writes in `_handle_cancellations` (K-SM1 remainder)

Status: review
Depends on: none | Base commit: main | Branch: task/1135-state-guards-claim-and-door-cancel
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## Open questions

The executor does nothing here. Owner decisions only.

1. **K-SM1 is mostly closed already.** Verified in code and reports:
   - `submission.state` recovery: closed by 1114 (`WHERE id = ? AND state = 'running'`, Python and Go).
   - `reservation_claim.state` in `start_claim`: closed by 1115 (`App/app/claim.py` ~306-308: `AND state = ? AND token_version = ?`, one re-read, then "held").
   - `door_code.state` in the two `_handle_cancellations` UPDATEs: closed by 1116 (`AND state IN (?, ?)` / `AND state = ?`).
   - `guide_import` stuck `running`: closed by 1117 (`process_queue` fails stale rows).
   - **Still open, and this brief's scope:** inside `_handle_cancellations`, the `revived` loop calls `_keep_issued` (`WHERE id = ?`, no state) and the `reactivated` loop runs `DELETE FROM door_code WHERE id = ?` (no state). Each acts on a row read by an earlier SELECT.
   - Decision for the owner: after this brief, edit K-SM1 in known-issues to "door writes outside `_handle_cancellations` (e.g. `issue()` result writes guarded only by the lease, `check_lock_clocks`, `_handle_moves`) are not audited" or close it. This brief does not edit docs.
2. **Go:** `go/internal/ical/reconcile.go` lines ~301 and ~406 write only `reservation_claim.token_hash` / `guest_access_locked_at`, not `state`; no Go writer of `door_code.state` exists. No Go change. (Go icalsync is owned by another brief.)
3. The brief's request named `claim.start_claim` and the two `_handle_cancellations` UPDATEs as open. They are not; this brief does not redo them.

## 1. Objective

Make the two remaining read-then-write steps of `_handle_cancellations` compare-and-swap: `_keep_issued` writes only over a row still in `revoke_failed` or `revoke_pending`, and the "reactivated" DELETE removes only a row still `revoked`. The set of possible moves does not change. Why: between the SELECT and the write, `_revoke_one` (scheduler or job queue) can delete the TTLock code and set `revoked` with `pin_enc = NULL`; the unguarded `_keep_issued` then writes `issued` over a row with no PIN, and the unguarded DELETE can remove a row that another writer has just moved on.

## 2. Context

Rules: SQL only through `db.py` helpers; no schema change; `TRANSITIONS` in `App/app/door_codes.py` stays as is (it already has `revoke_failed`/`revoke_pending` to `issued`, comment "_keep_issued: the stay is live again"). Door codes are the concurrency-sensitive area: minimal diff, one step per change.

Excerpt A, `App/app/door_codes.py` (`_keep_issued`):

```python
def _keep_issued(row_id: int, now_iso: str) -> None:
    """The stay is back; leave the PIN on the lock and show it again."""
    db.execute(
        "UPDATE door_code SET state = ?, claimed_at = NULL, attempts = 0, "
        "next_attempt_at = NULL, last_error = NULL, updated_at = ? WHERE id = ?",
        (ISSUED, now_iso, row_id),
    )
```

Callers: `_revoke_one` (the row is in `revoke_pending`, claimed by lease) and the `revived` loop (SELECT `dc.state IN (?, ?)` with `(REVOKE_PENDING, REVOKE_FAILED)`). Both are inside the guard set below, so behaviour on the happy path is the same. Zero rows updated means another writer moved the row; do nothing (the next reconcile run reads the new state), exactly like 1116.

Excerpt B, `App/app/door_codes.py` (end of `_handle_cancellations`):

```python
    for item in reactivated:
        db.execute("DELETE FROM door_code WHERE id = ?", (item["id"],))
        db.audit("door_code_reset", f"door_code={item['id']}", actor="system")
```

The `reactivated` SELECT is `WHERE dc.state = ? ... ` with `(REVOKED,)`. The audit line must run only when a row was deleted.

Excerpt C, `App/tests/test_sm_door_code_state.py` line 39 (the pin the writer SQL is checked against; a guarded write is pinned with its guard states, not `ANY`):

```python
    ("_keep_issued", ANY, ("revoke_failed", "revoke_pending"), ("issued",)),
```

Existing test helpers in `App/tests/test_door_code_cancel_guard.py`: `_cancelled_stay()` returns `(apartment, stay)`; `_code(apartment, stay, state, valid_to=None)`; `_state(row_id)`; fixture `_env` purges rows. A row with `valid_to` set also gets `pin_enc`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/door_codes.py` | edit | state guard on `_keep_issued` UPDATE; state guard and rowcount check on the reactivated DELETE |
| `App/tests/test_door_code_cancel_guard.py` | edit | append 3 tests (fault shown before the fix) |
| `App/tests/test_sm_door_code_state.py` | edit | line 39 pin: `ANY` becomes the guard states |
| `docs/tasks/1135-state-guards-claim-and-door-cancel.md` | edit | `Status:` line only |
| `docs/tasks/1135-report.md` | new | the report (§9) |

No other file may change.

## 4. Steps

1. Append these tests to the end of `App/tests/test_door_code_cancel_guard.py` (add `from datetime import datetime, timedelta, timezone` is already imported; nothing new to import):

```python
def test_keep_issued_does_not_overwrite_a_revoked_row():
    apartment, stay = _cancelled_stay()
    row = _code(apartment, stay, "revoked", valid_to="2099-01-01T00:00:00+00:00")
    door_codes._keep_issued(row, db.utcnow())
    assert _state(row) == "revoked"


def test_keep_issued_still_restores_a_revoke_pending_row():
    apartment, stay = _cancelled_stay()
    row = _code(apartment, stay, "revoke_pending", valid_to="2099-01-01T00:00:00+00:00")
    door_codes._keep_issued(row, db.utcnow())
    assert _state(row) == "issued"


def test_reactivated_delete_leaves_a_row_that_moved_on(monkeypatch):
    apartment, stay = _cancelled_stay()
    db.execute("UPDATE reservation SET status = 'active' WHERE id = ?", (stay,))
    row = _code(apartment, stay, "revoked")
    real_query = db.query
    seen: dict = {}

    def query(sql, params=()):
        rows = real_query(sql, params)
        if not seen and "r.status = 'active' AND r.archived_at IS NULL" in sql and params == ("revoked",):
            seen["moved"] = db.execute(
                "UPDATE door_code SET state = 'pending' WHERE id = ?", (row,)
            )
        return rows

    monkeypatch.setattr(db, "query", query)
    door_codes._handle_cancellations(db.utcnow())
    assert seen.get("moved") == 1
    assert _state(row) == "pending"
```

Command: `cd App && .venv/bin/python -m pytest tests/test_door_code_cancel_guard.py -q --tb=short 2>&1 | tail -30`
Expected: `1 failed` for `test_keep_issued_does_not_overwrite_a_revoked_row` (`assert 'issued' == 'revoked'`) and `1 failed` for `test_reactivated_delete_leaves_a_row_that_moved_on` (row is None). If the third test already passes or errors for another reason (the SELECT text differs), STOP (§8). The `revoke_pending` test passes.

2. In `App/app/door_codes.py`, replace this exact text:

```python
        "next_attempt_at = NULL, last_error = NULL, updated_at = ? WHERE id = ?",
        (ISSUED, now_iso, row_id),
    )
```

with:

```python
        "next_attempt_at = NULL, last_error = NULL, updated_at = ? "
        "WHERE id = ? AND state IN (?, ?)",
        (ISSUED, now_iso, row_id, REVOKE_FAILED, REVOKE_PENDING),
    )
```

(Anchor must be unique; if it matches twice or zero times, STOP.) Add above the `db.execute(` line this comment:
`    # Guarded: _revoke_one may have deleted the lock code and set revoked since the caller read the row. Zero rows updated leaves the row as it is.`
Command: `cd App && .venv/bin/python -m pytest tests/test_door_code_cancel_guard.py -q --tb=short -k keep_issued 2>&1 | tail -30`. Expected: `2 passed`.

3. In `App/app/door_codes.py`, replace this exact text:

```python
        db.execute("DELETE FROM door_code WHERE id = ?", (item["id"],))
        db.audit("door_code_reset", f"door_code={item['id']}", actor="system")
```

with:

```python
        # Guarded: only a row that is still revoked is reset; one that moved on is left.
        removed = db.execute(
            "DELETE FROM door_code WHERE id = ? AND state = ?", (item["id"], REVOKED)
        )
        if removed:
            db.audit("door_code_reset", f"door_code={item['id']}", actor="system")
```

Command: `cd App && .venv/bin/python -m pytest tests/test_door_code_cancel_guard.py -q --tb=short 2>&1 | tail -30`. Expected: `7 passed`.

4. In `App/tests/test_sm_door_code_state.py`, replace this exact line:

```python
    ("_keep_issued", ANY, ("revoke_failed", "revoke_pending"), ("issued",)),
```

with:

```python
    ("_keep_issued", ("revoke_failed", "revoke_pending"), ("revoke_failed", "revoke_pending"), ("issued",)),
```

Command: `cd App && .venv/bin/python -m pytest tests/test_sm_door_code_state.py -q --tb=short 2>&1 | tail -30`. Expected: all pass. If a failure says the pin disagrees with the writer, STOP and report the message (do not change the `TRANSITIONS` table).

5. Set `Status: review` in this brief, write `docs/tasks/1135-report.md` (§9), commit `1135: guard _keep_issued and the reactivated delete on the state read`, push, open one draft PR from `task/1135-state-guards-claim-and-door-cancel`. If `gh` is read-only, hand the push to the owner.

## 5. Do not touch

`TRANSITIONS` in `App/app/door_codes.py` and `App/app/claim.py`; `App/app/claim.py` entirely; `App/app/icalsync.py`; `go/` (all of it, including `go/internal/ical/`); `App/app/billing*.py`; migrations; templates and CSS (no UX gate). Hard rules 3, 4, 5, 8.

## 6. Commands

- Step 1, 2, 3: `cd App && .venv/bin/python -m pytest tests/test_door_code_cancel_guard.py -q --tb=short 2>&1 | tail -30`
- Step 4: `cd App && .venv/bin/python -m pytest tests/test_sm_door_code_state.py -q --tb=short 2>&1 | tail -30`
- Test-map row "Door codes, TTLock": `cd App && .venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py -q --tb=short -x 2>&1 | tail -30` (expect 0 failed; the `*_browser.py` files may fail to launch webkit locally, note it, do not fix).
- Claim row (only to confirm nothing moved): `cd App && .venv/bin/python -m pytest tests/test_sm_reservation_claim_state.py tests/test_claim_*.py -q --tb=short 2>&1 | tail -30` (expect 0 failed; no claim file changed).
- Root: `python3 scripts/context_lint.py 2>&1 | tail -30` (expect `context lint: OK`).

## 7. Acceptance

- [ ] Step 1 shows the two named tests failing before step 2 and 3.
- [ ] `grep -n 'WHERE id = ? AND state IN (?, ?)' App/app/door_codes.py` lists the `_keep_issued` write; `grep -n 'DELETE FROM door_code WHERE id = ? AND state = ?' App/app/door_codes.py` finds one line.
- [ ] Steps 3 and 4 pass; door-code and claim test-map rows pass.
- [ ] `git diff --stat` shows only §3 files.
- [ ] `TRANSITIONS` unchanged (`git diff App/app/door_codes.py | grep TRANSITIONS` prints nothing).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found verbatim, or an anchor matches more than once;
- a test fails twice, or the step 1 tests do not fail as stated;
- you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change, or §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand to the owner with the exact command).

## 9. Report

Write `docs/tasks/1135-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with the last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Risk list (for the reviewer)

`App/app/door_codes.py`: the diff is the `_keep_issued` WHERE clause and parameter tuple, and the DELETE with its rowcount check. Check the guard states equal `(REVOKE_FAILED, REVOKE_PENDING)` and match the `TRANSITIONS` rows that end in `issued`. Check `_revoke_one`'s call (row is `revoke_pending`) still restores.

## Owner steps

1. When the PR is green, mark it ready and merge with `scripts/merge-pr-on-green.sh`.
2. Decide Open question 1 (what to do with K-SM1 in known-issues).
