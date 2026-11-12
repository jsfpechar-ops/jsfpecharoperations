# 1137: operator pause outside TRANSITIONS, and two door-code guard fixes

Status: review
Depends on: 1134, 1135 | Base commit: 116def7d | Branch: task/1137-billing-operator-move-and-door-guards
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

(A) Undo 1134's `"trial_pending": {"trialing", "paused"}` in `billing.TRANSITIONS`: the Go table has no such move, so `test_sm_go_parity.py::test_machine_matches_go[billing_account.status]` fails and the operator status form (`admin_customers.py` ~258) would accept trial_pending -> paused. `place_for_operator` gets its own guarded, audited move instead (owner decision 2026-11-12: trial_pending -> paused is allowed only for operator plan assignment). (B) Two door-code races: the revived-stay loop audits `door_code_revoke_aborted` even when its UPDATE touched 0 rows, and `_keep_issued` can overwrite a revoke that holds the lease.

## 2. Context

Rules: Go table untouched; TRANSITIONS must equal it again. SQL only through `db` helpers. No new dependency. Anchors are verbatim from the branch; if one is missing, STOP (§8).

Facts: `db.execute` returns the rowcount. `_revoke_one` claims with `claimed_at = now_iso` (lease, `LEASE_MINUTES`) and keeps state `revoke_pending` while inside `ttlock.delete_code`. `_keep_issued` is called from `_revoke_one` (after its own claim) and from the revived loop in `_handle_cancellations` (no claim). Pin tests parse the state guard as the FIRST `state = ?` / `state IN (...)` in WHERE and count `?` before it, so appending conditions after it leaves the pin unchanged.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/billing.py | edit | revert TRANSITIONS; add `operator_pause` |
| App/app/billing_order.py | edit | call `operator_pause` |
| App/tests/test_sm_billing_status.py | edit | pins: operator move is an explicit exception |
| App/app/door_codes.py | edit | `_keep_issued` returns bool + lease; loop audits on True; `_revoke_one` writes guarded |
| App/tests/test_sm_door_code_state.py | edit | 4 `_revoke_one` pins ANY -> `("revoke_pending",)` |
| App/tests/test_door_code_cancel_guard.py | edit | 3 new tests |
| docs/tasks/1137-report.md | create | report (§9) |

No other file may change.

## 4. Steps

**Step 1. billing.py: revert and add the operator move.** In `App/app/billing.py` replace

```
    # paused: place_for_operator (operator assigns a plan to a legacy host, no trial;
    # owner decision 2026-10-29)
    "trial_pending": {"trialing", "paused"},
```
with
```
    "trial_pending": {"trialing"},
```
Then insert this function directly above `def apartment_count(owner_user_id: int) -> int:`:
```python
def operator_pause(owner_user_id: int, *, actor: str) -> bool:
    """trial_pending/trialing -> paused, for place_for_operator ONLY.

    The one status move outside TRANSITIONS (owner decision 2026-11-12): an operator
    assigning a plan to a legacy host has no trial left to run, but the operator status
    form and every set_status caller must still refuse trial_pending -> paused, and the
    Go table has no such move. One guarded UPDATE, audited only when a row changed.
    False means already paused or another state (place() then decides).
    """
    with db.immediate() as cur:
        db.lock_key(cur, "billing_account", owner_user_id)
        cur.execute("SELECT status FROM billing_account WHERE owner_user_id = ?", (owner_user_id,))
        row = cur.fetchone()
        if row is None:
            return False
        old = row["status"]
        cur.execute(
            "UPDATE billing_account SET status = 'paused', updated_at = ? "
            "WHERE owner_user_id = ? AND status IN ('trial_pending', 'trialing')",
            (db.utcnow(), owner_user_id),
        )
        changed = cur.rowcount == 1
    if changed:
        db.audit("billing_status", f"{old}->paused", actor=actor, owner_user_id=owner_user_id)
    return changed
```
Command: `cd App && .venv/bin/python -m pytest tests/test_sm_go_parity.py -q --tb=short 2>&1 | tail -30` Expected: all passed (billing_account.status parity green). If `cur.rowcount` raises, STOP.

**Step 2. billing_order.py.** Replace
```
    # trial_pending/trialing -> paused. False means already paused (fine) or a state
    # place() refuses with already_ordered; either way the result is not needed.
    billing.set_status(owner_user_id, "paused", actor=actor)
```
with
```
    # trial_pending/trialing -> paused through the operator-only move (not set_status).
    # False means already paused (fine) or a state place() refuses with already_ordered.
    billing.operator_pause(owner_user_id, actor=actor)
```
Command: `grep -n 'operator_pause' App/app/billing_order.py | tail -30` Expected: one line.

**Step 3. test_sm_billing_status.py.** (a) Replace the MOVES entry
```
    ("App/app/billing_order.py",
     'billing.set_status(owner_user_id, "paused", actor=actor)',
     ("trial_pending", "trialing"), "paused"),
]
```
with
```
]

# The one move outside TRANSITIONS: operator plan assignment (owner decision 2026-11-12).
OPERATOR_MOVES = [
    ("App/app/billing.py",
     "UPDATE billing_account SET status = 'paused', updated_at = ? ",
     ("trial_pending", "trialing"), "paused"),
    ("App/app/billing_order.py",
     "billing.operator_pause(owner_user_id, actor=actor)",
     ("trial_pending", "trialing"), "paused"),
]
```
(b) In `PINNED_WRITERS` replace `"App/app/billing.py": {"status_updates": 1, "inserts": 1},` with `"App/app/billing.py": {"status_updates": 2, "inserts": 1},`.
(c) Append at the end of the file:
```python
@pytest.mark.parametrize("rel,anchor", [(f, a) for f, a, _, _ in OPERATOR_MOVES])
def test_operator_move_anchor_is_in_file(rel, anchor):
    assert anchor in _read(rel), f"{rel} no longer contains: {anchor}"


def test_operator_move_is_not_in_transitions():
    # set_status and the operator status form must keep refusing it; the Go table has no such move.
    assert "paused" not in TABLE["trial_pending"]
    assert {s for _, _, froms, _ in OPERATOR_MOVES for s in froms} == {"trial_pending", "trialing"}
```
Command: `cd App && .venv/bin/python -m pytest tests/test_sm_billing_status.py tests/test_sm_go_parity.py tests/test_billing_core.py -q --tb=short 2>&1 | tail -30` Expected: all passed. Note `test_status_writing_statements_match_the_pins` still fails if any new unlisted writer appears.

**Step 4. door_codes.py `_keep_issued` and the loop.** Replace the whole function (anchor starts `def _keep_issued(row_id: int, now_iso: str) -> None:`, ends with `(ISSUED, now_iso, row_id, REVOKE_FAILED, REVOKE_PENDING),\n    )`) with:
```python
def _keep_issued(row_id: int, now_iso: str, held_claim: str | None = None) -> bool:
    """The stay is back; leave the PIN on the lock and show it again. True if a row changed."""
    # Guarded: _revoke_one may have deleted the lock code and set revoked since the caller read
    # the row, and it may hold the revoke lease right now (claimed_at inside LEASE_MINUTES).
    # _revoke_one passes its own claim stamp as held_claim; the revived loop passes none and
    # so skips a leased row. Zero rows updated leaves the row as it is.
    cutoff = _iso(_now() - timedelta(minutes=LEASE_MINUTES))
    return db.execute(
        "UPDATE door_code SET state = ?, claimed_at = NULL, attempts = 0, "
        "next_attempt_at = NULL, last_error = NULL, updated_at = ? "
        "WHERE id = ? AND state IN (?, ?) "
        "AND (claimed_at IS NULL OR claimed_at < ? OR claimed_at = ?)",
        (ISSUED, now_iso, row_id, REVOKE_FAILED, REVOKE_PENDING, cutoff, held_claim),
    ) == 1
```
Replace
```
        _keep_issued(row_id, now_iso)
        return
```
with
```
        _keep_issued(row_id, now_iso, held_claim=now_iso)
        return
```
Replace
```
        _keep_issued(int(item["id"]), now_iso)
        db.audit("door_code_revoke_aborted", f"door_code={item['id']}", actor="system")
```
with
```
        if _keep_issued(int(item["id"]), now_iso):
            db.audit("door_code_revoke_aborted", f"door_code={item['id']}", actor="system")
```
Command: `cd App && .venv/bin/python -m pytest tests/test_sm_door_code_state.py tests/test_door_code_cancel_guard.py -q --tb=short 2>&1 | tail -30` Expected: all passed (the `_keep_issued` pin is unchanged because the state guard comes first).

**Step 5. door_codes.py `_revoke_one` result writes.** Guard each with `AND state = ?` and append `REVOKE_PENDING` to the params. Five edits, all inside `_revoke_one`:

5a. no_account: replace
```
            "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
            "WHERE id = ?",
            (REVOKE_FAILED, "no_account", now_iso, row_id),
```
with
```
            "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
            "WHERE id = ? AND state = ?",
            (REVOKE_FAILED, "no_account", now_iso, row_id, REVOKE_PENDING),
```
5b. revoked: replace
```
            "updated_at = ? WHERE id = ?",
            (REVOKED, now_iso, now_iso, row_id),
```
with
```
            "updated_at = ? WHERE id = ? AND state = ?",
            (REVOKED, now_iso, now_iso, row_id, REVOKE_PENDING),
```
5c. past_end (indent 20): replace
```
                    "WHERE id = ?",
                    (REVOKE_FAILED, kind[:40], now_iso, row_id),
```
with
```
                    "WHERE id = ? AND state = ?",
                    (REVOKE_FAILED, kind[:40], now_iso, row_id, REVOKE_PENDING),
```
5d. retry delay (no state set; not pinned): replace
```
                    "updated_at = ? WHERE id = ?",
                    (next_at, kind[:40], now_iso, row_id),
```
with
```
                    "updated_at = ? WHERE id = ? AND state = ?",
                    (next_at, kind[:40], now_iso, row_id, REVOKE_PENDING),
```
5e. else branch (indent 16): replace
```
                "WHERE id = ?",
                (REVOKE_FAILED, kind[:40], now_iso, row_id),
```
with
```
                "WHERE id = ? AND state = ?",
                (REVOKE_FAILED, kind[:40], now_iso, row_id, REVOKE_PENDING),
```
Each anchor differs by indentation; if one matches twice, use the indentation shown. Command: `grep -c 'AND state = ?' App/app/door_codes.py | tail -30` then proceed to step 6 (the pins fail until then).

**Step 6. test_sm_door_code_state.py pins.** Replace the four lines
```
    ("_revoke_one", ANY, ("revoke_pending",), ("revoke_failed",)),
    ("_revoke_one", ANY, ("revoke_pending",), ("revoked",)),
    ("_revoke_one", ANY, ("revoke_pending",), ("revoke_failed",)),
    ("_revoke_one", ANY, ("revoke_pending",), ("revoke_failed",)),
```
with
```
    ("_revoke_one", ("revoke_pending",), ("revoke_pending",), ("revoke_failed",)),
    ("_revoke_one", ("revoke_pending",), ("revoke_pending",), ("revoked",)),
    ("_revoke_one", ("revoke_pending",), ("revoke_pending",), ("revoke_failed",)),
    ("_revoke_one", ("revoke_pending",), ("revoke_pending",), ("revoke_failed",)),
```
Command: `cd App && .venv/bin/python -m pytest tests/test_sm_door_code_state.py -q --tb=short 2>&1 | tail -30` Expected: 11 passed.

**Step 7. new tests, then full target run.** Append to `App/tests/test_door_code_cancel_guard.py`:
```python
def _aborted_audits() -> int:
    return db.query_one(
        "SELECT COUNT(*) AS n FROM audit WHERE action = ?", ("door_code_revoke_aborted",)
    )["n"]


def _revive(stay: int) -> None:
    db.execute("UPDATE reservation SET status = 'active' WHERE id = ?", (stay,))


def test_zero_row_keep_writes_no_aborted_audit(monkeypatch):
    monkeypatch.setattr(door_codes, "_revoke_one", lambda row_id: None)
    apartment, stay = _cancelled_stay()
    _revive(stay)
    row = _code(apartment, stay, door_codes.REVOKE_PENDING, valid_to="2099-01-01T00:00:00+00:00")
    before = _aborted_audits()
    monkeypatch.setattr(door_codes, "_keep_issued", lambda *a, **k: False)
    door_codes._handle_cancellations(db.utcnow())
    assert _aborted_audits() == before
    assert _state(row) == door_codes.REVOKE_PENDING


def test_a_row_that_is_kept_writes_the_aborted_audit(monkeypatch):
    monkeypatch.setattr(door_codes, "_revoke_one", lambda row_id: None)
    apartment, stay = _cancelled_stay()
    _revive(stay)
    row = _code(apartment, stay, door_codes.REVOKE_PENDING, valid_to="2099-01-01T00:00:00+00:00")
    before = _aborted_audits()
    door_codes._handle_cancellations(db.utcnow())
    assert _state(row) == door_codes.ISSUED
    assert _aborted_audits() == before + 1


def test_leased_revoke_is_not_overwritten_by_the_revived_loop(monkeypatch):
    monkeypatch.setattr(door_codes, "_revoke_one", lambda row_id: None)
    apartment, stay = _cancelled_stay()
    _revive(stay)
    row = _code(apartment, stay, door_codes.REVOKE_PENDING, valid_to="2099-01-01T00:00:00+00:00")
    db.execute("UPDATE door_code SET claimed_at = ? WHERE id = ?", (door_codes._iso(door_codes._now()), row))
    before = _aborted_audits()
    door_codes._handle_cancellations(db.utcnow())
    assert _state(row) == door_codes.REVOKE_PENDING
    assert _aborted_audits() == before
    # An expired lease no longer protects the row.
    old = door_codes._iso(door_codes._now() - timedelta(minutes=door_codes.LEASE_MINUTES + 1))
    db.execute("UPDATE door_code SET claimed_at = ? WHERE id = ?", (old, row))
    door_codes._handle_cancellations(db.utcnow())
    assert _state(row) == door_codes.ISSUED
```
Command: the full §6 pytest line. Expected: all passed. If a test fails twice, STOP. Then `python3 scripts/context_lint.py 2>&1 | tail -3` Expected: says OK.

## 5. Do not touch

`go/`, `App/app/icalsync.py`, `App/app/routes/admin_customers.py`, `TRANSITIONS` in door_codes.py, any other file. Hard rules 4 and 5 (no dependency; SQL through `db` helpers).

## 6. Commands

From `App/`:
- `.venv/bin/python -m pytest tests/test_sm_billing_status.py tests/test_sm_go_parity.py tests/test_billing_core.py tests/test_door_code_cancel_guard.py tests/test_sm_door_code_state.py -q --tb=short 2>&1 | tail -30` Expected: all passed.
- Test-map rows: `.venv/bin/python -m pytest tests/test_billing_*.py -q --tb=short -x 2>&1 | tail -30` and `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py -q --tb=short -x -rs 2>&1 | tail -30` Expected: passed (skips only for missing playwright).
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` Expected: OK.

## 7. Acceptance

- [ ] `grep -n '"trial_pending"' App/app/billing.py | head -3` shows `{"trialing"}` only.
- [ ] `test_sm_go_parity.py` passes.
- [ ] `grep -n 'set_status(owner_user_id, "paused"' App/app/billing_order.py | tail -30` prints nothing.
- [ ] The three new tests pass; the §6 commands pass.
- [ ] Lint says OK.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found (or matches twice);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report as `blocked`, see executor.md);
- `cur.rowcount` is unavailable on the `db.immediate()` cursor;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1137-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/billing.py` `operator_pause` (the only status move outside TRANSITIONS) and its pins.
- `App/app/door_codes.py` `_keep_issued` lease condition (`held_claim` equals `_revoke_one`'s claim stamp) and the five guarded writes in `_revoke_one`.

## Owner steps

1. Review the PR diff for the two risk-list files.
2. Merge with `scripts/merge-pr-on-green.sh` when CI is green.
