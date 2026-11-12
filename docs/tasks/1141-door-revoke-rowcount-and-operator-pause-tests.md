# 1141: door revoke result rowcount, and operator_pause tests

Status: review
Depends on: 1137 | Base commit: HEAD of PR #933 | Branch: task/1141-door-revoke-rowcount-and-operator-pause-tests
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

(A) `door_codes._revoke_one` writes its result with a state-guarded UPDATE but ignores the rowcount: if `ttlock.delete_code` outlasts `LEASE_MINUTES` and the revived loop restores `issued`, the UPDATE changes 0 rows, yet the `door_code_revoked` audit and the `cancelled_deleted` mail still go out. Check every result write; on 0 rows skip audit and mail. (B) `billing.operator_pause` and `place_for_operator` have no behavioural test; add them and fix the comment that calls `operator_pause` the "one move outside TRANSITIONS" (only trial_pending -> paused is outside).

## 2. Context

Rules: SQL only through `db` helpers; no new dependency; `door_codes.TRANSITIONS` gets NO new move. `db.execute` returns the rowcount. Anchors are verbatim from HEAD; if one is missing, STOP (§8).

Convergence decision (A): the code is deleted on the lock but the row is `issued` with a live stay. The only table move from `issued` is `issued -> revoke_pending`, but the revived loop (`_keep_issued`) flips it straight back to `issued` while the stay is live, and `revoked -> pending` does not exist. So no move in TRANSITIONS converges the lock and the DB. This brief therefore does NOT re-queue: it writes the audit `door_code_revoke_lost_race`, sends no mail and leaves the state. The owner decides the real fix (see "Owner steps").

SQL strings do not change, so `test_sm_door_code_state.py` PINNED needs no edit (the step 5 command proves it). Existing excerpt of the failing write, `App/app/door_codes.py` in `_revoke_one`:
```python
        db.execute(
            "UPDATE door_code SET state = ?, revoked_at = ?, pin_enc = NULL, claimed_at = NULL, "
            "updated_at = ? WHERE id = ? AND state = ?",
            (REVOKED, now_iso, now_iso, row_id, REVOKE_PENDING),
        )
        db.audit(
            "door_code_revoked",
```
(B) billing facts: `ORDERABLE = ("trial_pending", "trialing", "paused")` in `billing_order.py`; `place()` raises `ValueError("already_ordered")` for any other status. `operator_pause` audits `billing_status` with detail `f"{old}->paused"`. Fixtures: `host` in `App/tests/test_billing_order.py` (creates owner + billing row, `_set(owner, **fields)` sets columns, `_values()` builds the form).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | `_revoke_one`: check rowcount on all 5 result writes |
| App/tests/test_door_code_cancel_guard.py | edit | 2 new tests |
| App/app/billing.py | edit | docstring wording |
| App/tests/test_sm_billing_status.py | edit | comment wording |
| App/tests/test_billing_operator_pause.py | create | operator_pause + place_for_operator tests |
| docs/tasks/1141-report.md | create | report (§9) |

No other file may change.

## 4. Steps

**Step 1. door_codes.py: no_account write.** Replace
```python
        db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
            "WHERE id = ? AND state = ?",
            (REVOKE_FAILED, "no_account", now_iso, row_id, REVOKE_PENDING),
        )
        mail_notify.door_code_notice(row_id, "cancelled_not_deleted")
        return
```
with
```python
        if db.execute(
            "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
            "WHERE id = ? AND state = ?",
            (REVOKE_FAILED, "no_account", now_iso, row_id, REVOKE_PENDING),
        ) == 1:
            mail_notify.door_code_notice(row_id, "cancelled_not_deleted")
        return
```
Command: `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -3` → no output.

**Step 2. door_codes.py: success write.** Replace
```python
        db.execute(
            "UPDATE door_code SET state = ?, revoked_at = ?, pin_enc = NULL, claimed_at = NULL, "
            "updated_at = ? WHERE id = ? AND state = ?",
            (REVOKED, now_iso, now_iso, row_id, REVOKE_PENDING),
        )
        db.audit(
            "door_code_revoked",
```
with
```python
        if db.execute(
            "UPDATE door_code SET state = ?, revoked_at = ?, pin_enc = NULL, claimed_at = NULL, "
            "updated_at = ? WHERE id = ? AND state = ?",
            (REVOKED, now_iso, now_iso, row_id, REVOKE_PENDING),
        ) != 1:
            # The lock code is gone but the row moved on (the stay came back during the
            # delete). No audit "revoked", no mail; leave the state and flag it.
            db.audit(
                "door_code_revoke_lost_race",
                f"door_code={row_id}",
                actor="system",
                owner_user_id=apartment["owner_user_id"],
            )
            return
        db.audit(
            "door_code_revoked",
```
Command: `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -3` → no output.

**Step 3. door_codes.py: the three failure-branch writes.** (a) Replace
```python
            if past_end:
                db.execute(
                    "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
                    "WHERE id = ? AND state = ?",
                    (REVOKE_FAILED, kind[:40], now_iso, row_id, REVOKE_PENDING),
                )
                db.audit(
                    "door_code_revoke_failed",
                    f"door_code={row_id}",
                    actor="system",
                    owner_user_id=apartment["owner_user_id"],
                )
```
with
```python
            if past_end:
                if db.execute(
                    "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
                    "WHERE id = ? AND state = ?",
                    (REVOKE_FAILED, kind[:40], now_iso, row_id, REVOKE_PENDING),
                ) == 1:
                    db.audit(
                        "door_code_revoke_failed",
                        f"door_code={row_id}",
                        actor="system",
                        owner_user_id=apartment["owner_user_id"],
                    )
```
(b) Replace
```python
                db.execute(
                    "UPDATE door_code SET claimed_at = NULL, next_attempt_at = ?, last_error = ?, "
                    "updated_at = ? WHERE id = ? AND state = ?",
                    (next_at, kind[:40], now_iso, row_id, REVOKE_PENDING),
                )
                if attempts == 3:
                    mail_notify.door_code_notice(row_id, "cancelled_not_deleted")
```
with
```python
                if db.execute(
                    "UPDATE door_code SET claimed_at = NULL, next_attempt_at = ?, last_error = ?, "
                    "updated_at = ? WHERE id = ? AND state = ?",
                    (next_at, kind[:40], now_iso, row_id, REVOKE_PENDING),
                ) == 1 and attempts == 3:
                    mail_notify.door_code_notice(row_id, "cancelled_not_deleted")
```
(c) The final `else:` branch. Replace
```python
            db.execute(
                "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
                "WHERE id = ? AND state = ?",
                (REVOKE_FAILED, kind[:40], now_iso, row_id, REVOKE_PENDING),
            )
            db.audit(
                "door_code_revoke_failed",
                f"door_code={row_id}",
                actor="system",
                owner_user_id=apartment["owner_user_id"],
            )
            mail_notify.door_code_notice(row_id, "cancelled_not_deleted")
```
with
```python
            if db.execute(
                "UPDATE door_code SET state = ?, claimed_at = NULL, last_error = ?, updated_at = ? "
                "WHERE id = ? AND state = ?",
                (REVOKE_FAILED, kind[:40], now_iso, row_id, REVOKE_PENDING),
            ) == 1:
                db.audit(
                    "door_code_revoke_failed",
                    f"door_code={row_id}",
                    actor="system",
                    owner_user_id=apartment["owner_user_id"],
                )
                mail_notify.door_code_notice(row_id, "cancelled_not_deleted")
```
Command: `cd App && .venv/bin/python -m pytest tests/test_sm_door_code_state.py -q --tb=short 2>&1 | tail -30` → all pass, no PINNED edit needed. If a pin fails, STOP.

**Step 4. test_door_code_cancel_guard.py: two tests.** Append at the end of the file:
```python
def _audits(action: str) -> int:
    return db.query_one("SELECT COUNT(*) AS n FROM audit WHERE action = ?", (action,))["n"]


def _revoke_with_delete(monkeypatch, during_delete):
    apartment, stay = _cancelled_stay()
    row = _code(apartment, stay, door_codes.REVOKE_PENDING, valid_to="2099-01-01T00:00:00+00:00")
    mails: list = []
    monkeypatch.setattr(door_codes.ttlock, "account_for", lambda owner: {"id": 1, "status": "ok"})
    monkeypatch.setattr(door_codes.ttlock, "delete_code", lambda *a, **k: during_delete(row))
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", lambda *a, **k: mails.append(a))
    door_codes._revoke_one(row)
    return row, mails


def test_revoke_that_lost_the_row_during_delete_writes_no_revoked_audit_and_no_mail(monkeypatch):
    revoked, lost = _audits("door_code_revoked"), _audits("door_code_revoke_lost_race")
    row, mails = _revoke_with_delete(
        monkeypatch,
        lambda r: db.execute("UPDATE door_code SET state = ?, claimed_at = NULL WHERE id = ?", (door_codes.ISSUED, r)),
    )
    assert _state(row) == door_codes.ISSUED
    assert mails == []
    assert _audits("door_code_revoked") == revoked
    assert _audits("door_code_revoke_lost_race") == lost + 1


def test_revoke_that_keeps_the_row_still_audits_and_mails(monkeypatch):
    revoked, lost = _audits("door_code_revoked"), _audits("door_code_revoke_lost_race")
    row, mails = _revoke_with_delete(monkeypatch, lambda r: None)
    assert _state(row) == door_codes.REVOKED
    assert [m[1] for m in mails] == ["cancelled_deleted"]
    assert _audits("door_code_revoked") == revoked + 1
    assert _audits("door_code_revoke_lost_race") == lost
```
Command: `cd App && .venv/bin/python -m pytest tests/test_door_code_cancel_guard.py tests/test_sm_door_code_state.py -q --tb=short 2>&1 | tail -30` → all pass. If `door_codes.ttlock` or `door_codes.mail_notify` is not a module attribute, STOP.

**Step 5. Comment wording.** In `App/app/billing.py` replace
```
    The one status move outside TRANSITIONS (owner decision 2026-11-12): an operator
```
with
```
    trial_pending -> paused is the one status move outside TRANSITIONS (trialing -> paused
    is in it; owner decision 2026-11-12): an operator
```
In `App/tests/test_sm_billing_status.py` replace
```
# The one move outside TRANSITIONS: operator plan assignment (owner decision 2026-11-12).
```
with
```
# Operator plan assignment (owner decision 2026-11-12). Only trial_pending -> paused is
# outside TRANSITIONS; trialing -> paused is in the table.
```
Command: `cd App && grep -n '"trialing": {' -A3 app/billing.py | head -6` → shows `paused` in the trialing set (if not, STOP and report).

**Step 6. New file `App/tests/test_billing_operator_pause.py`.** Create:
```python
"""Brief 1141: billing.operator_pause and billing_order.place_for_operator, behaviour."""
from __future__ import annotations

import pytest

from app import billing, billing_order, db
from tests.test_billing_order import BUYER, _set, _values, host  # noqa: F401


def _audits(owner: int) -> int:
    return db.query_one(
        "SELECT COUNT(*) AS n FROM audit WHERE action = ? AND owner_user_id = ?",
        ("billing_status", owner),
    )["n"]


def _status(owner: int) -> str:
    return billing.account(owner)["status"]


@pytest.mark.parametrize("start", ["trial_pending", "trialing"])
def test_operator_pause_moves_to_paused_with_one_audit(host, start):
    owner = host["owner"]
    _set(owner, status=start)
    before = _audits(owner)
    assert billing.operator_pause(owner, actor="op") is True
    assert _status(owner) == "paused"
    assert _audits(owner) == before + 1


@pytest.mark.parametrize("start", ["paused", "active", "overdue", "canceling"])
def test_operator_pause_refuses_other_states_without_audit(host, start):
    owner = host["owner"]
    _set(owner, status=start)
    before = _audits(owner)
    assert billing.operator_pause(owner, actor="op") is False
    assert _status(owner) == start
    assert _audits(owner) == before


@pytest.mark.parametrize("start", ["active", "overdue", "canceling"])
def test_place_for_operator_with_no_plan_in_a_live_state_is_already_ordered(host, start):
    owner = host["owner"]
    _set(owner, status=start, plan=None)
    with pytest.raises(ValueError, match="already_ordered"):
        billing_order.place_for_operator(owner, _values(), actor="op")
    assert _status(owner) == start
```
Command: `cd App && .venv/bin/python -m pytest tests/test_billing_operator_pause.py -q --tb=short 2>&1 | tail -30` → 9 passed. If the `billing_order` import of `host`/`_set`/`_values` fails, copy those three helpers into the new file instead. If any `already_ordered` case fails because `place_for_operator` does something else, do NOT change code: delete that parametrized test, write what it did under "Questions" in the report.

**Step 7. Run all commands in §6, write the report.** Command: `python3 scripts/context_lint.py 2>&1 | tail -3` → `context lint: OK`.

## 5. Do not touch

`App/app/icalsync.py`, `App/app/reporting.py`, `go/` (brief 1140 edits them), `door_codes.TRANSITIONS`, the SQL text of any `door_code` write, `App/app/billing_order.py`. Hard rules: 3 (no secrets), 4 (no dependency), 5 (SQL through `db`).

## 6. Commands

From `App/`, each ending `2>&1 | tail -30`:

1. `.venv/bin/python -m pytest tests/test_door_code_cancel_guard.py tests/test_sm_door_code_state.py tests/test_sm_billing_status.py tests/test_sm_go_parity.py tests/test_billing_operator_pause.py -q --tb=short` → all pass.
2. Test-map door row: `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py -q --tb=short -x` → pass; skips only for missing playwright.
3. Test-map billing row: `.venv/bin/python -m pytest tests/test_billing_*.py -q --tb=short -x` → pass.

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` → `context lint: OK`.

## 7. Acceptance

- [ ] `grep -c "door_code_revoke_lost_race" App/app/door_codes.py` prints 1.
- [ ] Every `db.execute(` that writes door_code inside `_revoke_one` is compared with `== 1` or `!= 1` (read the diff).
- [ ] `git diff --stat` shows no PINNED change in `test_sm_door_code_state.py` and no file outside §3.
- [ ] The two new door tests and the nine new billing tests pass.
- [ ] §6 commands pass; lint says OK.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1141-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/app/door_codes.py` `_revoke_one` (five guarded writes, the `lost_race` early return); the new `lost_race` audit leaves a row that is `issued` while its PIN is deleted on the lock.

## Open questions

The lost-race case (code deleted on the lock, row `issued`, stay live) cannot converge with the current TRANSITIONS: `issued -> revoke_pending` is reverted by the revived loop, and `revoked -> pending` does not exist. Options for the owner: (a) accept the audit as the alert, (b) add a move that re-issues a fresh code for the row (a new transition and a new brief), (c) have `_revoke_one` re-check the stay after `delete_code` and call `ttlock` to recreate the code.

## Owner steps

1. Review the PR diff for `App/app/door_codes.py` (the risk list above).
2. Decide the open question: reply a, b or c; b or c need a new brief.
3. Push the branch and open the PR, then merge with `scripts/merge-pr-on-green.sh` when CI is green.
