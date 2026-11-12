# 1155b: deleting a door code that is already gone counts as deleted (K-DC-RECANCEL)

Status: todo
Depends on: 1155 | Base commit: HEAD of branch claude/zealous-maxwell-a7ub54 after 1155 is merged | Branch: task/1155b-door-recancel-gone
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When `_revoke_one` deletes a lock code that is already gone (the stay was cancelled again after 1155 or 1149 recovered a lost PIN, or an earlier delete timed out after the lock ran it and the retry finds nothing), TTLock refuses the delete, the code is retried until `valid_to`, the host gets a false `cancelled_not_deleted` mail and the row ends `revoke_failed`. Fix: when the refusal is an errcode the repo does not map, ask the lock once with the 1155 helper `_lock_code_state`; if the code is gone, the delete counts as success (the same `revoked` write, `door_code_revoked` audit and `cancelled_deleted` mail as a real delete). Every other error keeps today's path.

## 2. Context

Rules: SQL only through `db` helpers; no dependency, no migration, no new transition (the existing `revoke_pending -> revoked` write is reused). Anchors are verbatim from HEAD after 1155; if one is missing, STOP (§8).

**What the code does today.** `ttlock._parse_response` raises `TTLockError(code=<errcode>, kind=ERROR_KINDS.get(code, "transient"))`. `ERROR_KINDS` has no entry for a missing-code delete. `-3008` (`unused_code`) is TTLock's answer to *changing* a passcode that was never used on the lock, not to a delete, so it is not the not-found code. The real not-found errcode is not recorded anywhere in the repo or in `docs/plans/ttlock-door-codes.md`, so this brief does not guess one. Today an unmapped errcode becomes kind `transient`, which is in `GATEWAY_RETRY_KINDS`: `_revoke_one` retries after 1, 15, 60 minutes, mails `cancelled_not_deleted` at attempt 3, and past `valid_to` writes `revoke_failed` plus the `door_code_revoke_failed` audit. A timeout or non-JSON answer has `code = None`; a mapped errcode (offline, permission, rate, budget, ...) is a definite answer about a code that exists.

**Decision.** Only an errcode that is not `None` and not in `ttlock.ERROR_KINDS` may mean "no such code". For that one case `_revoke_one` calls `_lock_code_state(row, owner)` (one `/v3/lock/listKeyboardPwd`, outbound reason as in 1155: confirm the code is gone before treating a refusal as success). Only `PIN_GONE` is success; `PIN_PRESENT` and `PIN_UNKNOWN` (lookup failed) fall through to the existing retry path. If the row moved on during the call (the 0-row branch), the existing lost-race branch runs and `_reissue_lost_pin` makes a new code if the stay is live. When the owner learns the real not-found errcode, map it in `ERROR_KINDS` and drop the lookup in a later brief.

Anchor A, `App/app/door_codes.py` (once): `def _reissue_lost_pin(row_id: int, deleted_code_id: str, owner_user_id: int) -> None:`
Anchor B, `App/app/door_codes.py` (in `_revoke_one`):
```python
    try:
        ttlock.delete_code(
            int(account["id"]),
            row["lock_id"],
            row["provider_code_id"] or "",
        )
        if db.execute(
```

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | one helper, one inner try |
| App/tests/test_door_code_recancel.py | create | 5 tests (6 cases, one is parametrized twice) |
| docs/tasks/1155b-report.md | create | report (§9) |

No other file may change.

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30`; expected `claude/zealous-maxwell-a7ub54`. Confirm 1155 is in: `grep -c "def _lock_code_state" App/app/door_codes.py | tail -30` -> `1` (else STOP). Then `git switch -c task/1155b-door-recancel-gone | tail -30`; expected `Switched to a new branch`.

**Step 2. Helper.** Replace Anchor A with the function below, two blank lines, then the same `def _reissue_lost_pin(...)` line again:
```python
def _already_gone(exc: "ttlock.TTLockError", row, owner_user_id: int) -> bool:
    """A refused delete that may only mean "that code no longer exists".

    TTLock answers a delete of a missing code with an errcode this repo does not map
    (the not-found number is not recorded, so none is guessed). Only such an unmapped
    errcode, never a network error or a mapped one, costs one list call; the code counts
    as deleted only when the lock confirms it is gone.
    """
    if exc.code is None or exc.code in ttlock.ERROR_KINDS:
        return False
    return _lock_code_state(row, owner_user_id) == PIN_GONE
```
Command: `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -30` -> no output.

**Step 3. Inner try.** Replace Anchor B with
```python
    try:
        try:
            ttlock.delete_code(
                int(account["id"]),
                row["lock_id"],
                row["provider_code_id"] or "",
            )
        except ttlock.TTLockError as exc:
            if not _already_gone(exc, row, apartment["owner_user_id"]):
                raise
        if db.execute(
```
(The `raise` leaves the inner try and is caught by the existing outer `except ttlock.TTLockError as exc:`, so every other error keeps its path.) Command: `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -30` -> no output.

**Step 4. Create `App/tests/test_door_code_recancel.py`** with exactly:
```python
"""1155b: a stay cancelled again deletes a code that is already gone: that is success.

A fake lock holds the PINs. Deleting a PIN that is not there raises an errcode the repo
does not map (-3999 here), like TTLock's answer for a missing code.
"""
from __future__ import annotations

import pytest

from app import config, db, door_codes, ttlock
from tests.test_door_code_cancel_guard import _audits, _cancelled_stay, _code, _purge, _state
from tests.test_door_code_lost_pin import FakeLock, _row

UNMAPPED = -3999


@pytest.fixture
def world(monkeypatch):
    db.init_db()
    _purge()
    lock = FakeLock()
    lock.lookups = 0
    lock.lookup_error = None
    notices: list = []

    def delete(account_id, lock_id, code_id, priority=None):
        if str(code_id) not in lock.pins:
            raise ttlock.TTLockError("no such passcode", code=UNMAPPED, kind="transient")
        lock.pins.pop(str(code_id))

    def find(*args, **kwargs):
        lock.lookups += 1
        if lock.lookup_error:
            raise lock.lookup_error
        for code_id, pin in lock.pins.items():
            return pin, code_id
        return None

    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(ttlock, "account_for", lambda owner: {"id": 1, "status": "ok"})
    monkeypatch.setattr(ttlock, "delete_code", delete)
    monkeypatch.setattr(ttlock, "find_code_by_name", find)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", lambda row_id, kind: notices.append(kind))
    apartment, stay = _cancelled_stay()
    row = _code(apartment, stay, door_codes.REVOKE_PENDING, valid_to="2099-01-01T00:00:00+00:00")
    db.execute("UPDATE door_code SET valid_from = ? WHERE id = ?", ("2098-12-30T00:00:00+00:00", row))
    yield lock, stay, row, notices
    _purge()


def test_deleting_a_code_that_is_already_gone_counts_as_revoked(world):
    lock, stay, row, notices = world
    lock.pins.clear()
    revoked = _audits("door_code_revoked")
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.REVOKED and after["pin_enc"] is None
    assert _audits("door_code_revoked") == revoked + 1
    assert notices == ["cancelled_deleted"] and lock.lookups == 1


def test_a_timed_out_delete_then_a_retry_that_finds_the_code_gone_is_revoked(world, monkeypatch):
    lock, stay, row, notices = world
    real = ttlock.delete_code

    def timeout_after_delete(*a, **k):
        real(*a, **k)
        raise ttlock.TTLockError("timeout", kind="network")

    monkeypatch.setattr(ttlock, "delete_code", timeout_after_delete)
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and lock.pins == {}
    monkeypatch.setattr(ttlock, "delete_code", real)
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE id = ?", (row,))
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKED
    assert "cancelled_not_deleted" not in notices


def test_an_unmapped_refusal_while_the_code_is_still_on_the_lock_is_retried(world, monkeypatch):
    lock, stay, row, notices = world

    def refuse(*a, **k):
        raise ttlock.TTLockError("odd", code=UNMAPPED, kind="transient")

    monkeypatch.setattr(ttlock, "delete_code", refuse)
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.REVOKE_PENDING and after["next_attempt_at"] is not None
    assert lock.pins == {"pid-1": "4821937"} and lock.lookups == 1 and notices == []


def test_an_unmapped_refusal_and_a_failed_lookup_are_retried(world):
    lock, stay, row, notices = world
    lock.pins.clear()
    lock.lookup_error = ttlock.TTLockError("busy", kind="transient")
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and notices == []


@pytest.mark.parametrize("code,kind", [(None, "network"), (-2012, "offline")])
def test_a_network_error_or_a_mapped_errcode_costs_no_lookup(world, monkeypatch, code, kind):
    lock, stay, row, notices = world

    def fail(*a, **k):
        raise ttlock.TTLockError("down", code=code, kind=kind)

    monkeypatch.setattr(ttlock, "delete_code", fail)
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and lock.lookups == 0
```
Command (from `App/`): `.venv/bin/python -m pytest tests/test_door_code_recancel.py tests/test_door_code_ambiguous_delete.py tests/test_door_code_lost_pin.py tests/test_door_code_cancel_guard.py -q --tb=short 2>&1 | tail -30` -> `32 passed`.

**Step 5. Commit.** `git add App/app/door_codes.py App/tests/test_door_code_recancel.py && git commit -m "1155b: a delete of a code that is already gone counts as deleted" | tail -30`.
Commit message ends with the attribution lines the session reminder gives.

**Step 6. Revert-bite, three runs.** Each run, from the repo root: apply the `sed`, run `T`, expect the named result, then `git checkout App/app/door_codes.py | tail -30`. `T` is `cd App && .venv/bin/python -m pytest tests/test_door_code_recancel.py -q --tb=no 2>&1 | tail -30`. After the `sed`, `git diff --stat | tail -30` must show `1 file changed, 1 insertion(+), 1 deletion(-)`.
- (a) No swallow: `sed -i 's/^            if not _already_gone(exc, row, apartment\["owner_user_id"\]):$/            if True:/' App/app/door_codes.py` then `T`: `3 failed, 3 passed` (`already_gone_counts_as_revoked`, `timed_out_delete_then_a_retry`, `unmapped_refusal_while_the_code_is_still_on_the_lock`).
- (b) Lookup for every error: `sed -i 's/^    if exc.code is None or exc.code in ttlock.ERROR_KINDS:$/    if False:/' App/app/door_codes.py` then `T`: `3 failed, 3 passed` (`timed_out_delete_then_a_retry`, and both `network_error_or_a_mapped_errcode` cases).
- (c) Unknown counts as gone: `sed -i 's/^    return _lock_code_state(row, owner_user_id) == PIN_GONE$/    return _lock_code_state(row, owner_user_id) != PIN_PRESENT/' App/app/door_codes.py` then `T`: `1 failed, 5 passed` (`unmapped_refusal_and_a_failed_lookup_are_retried`).
If a run does not fail as stated, STOP (§8). Finally `git status --short | tail -30` -> empty.

**Step 7. Door-codes row (test-map).** From `App/`: `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_sm_door_code_state.py tests/test_sm_go_parity.py -q --tb=short -rs 2>&1 | tail -30` -> no failures; only the two `playwright` skips.

**Step 8. Lint.** From `App/`: `.venv/bin/ruff check app tests --select E9,F63,F7,F82,F401,F841 2>&1 | tail -30` -> `All checks passed!`.

**Step 9. Postgres.** From `App/`: `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code_recancel.py tests/test_door_codes_safeguards.py -q --tb=short 2>&1 | tail -30` -> all pass (or report `not run: no Postgres`).

**Step 10. Report.** Write `docs/tasks/1155b-report.md` (§9), set this file's line 3 to `Status: review`, then `python3 scripts/context_lint.py | tail -3` from the repo root.

## 5. Do not touch

`App/app/ttlock.py` (do not add or guess an errcode), `docs/context/*`, migrations, `go/`, `_lock_code_state` and `_revive_one` bodies. Hard rules: 3, 4, 5.

## 6. Commands

All Python from `App/`, each ending `2>&1 | tail -30`: Steps 2 to 9 give the exact command and result. Never the full suite.

## 7. Acceptance

- [ ] `test_door_code_recancel.py` is 6 passed (5 tests, one parametrized twice); step 4 shows `32 passed` with the others.
- [ ] The three revert-bite runs fail as stated and `git status --short` is empty afterwards.
- [ ] The door-codes row passes with only the two `playwright` skips; ruff passes; Postgres run passes or is reported as not run.
- [ ] The report says the real TTLock not-found errcode is still unknown.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found verbatim, or 1155 is not in the tree;
- a test fails twice;
- a revert-bite run does not fail as stated;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency, a migration or a new state transition seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1155b-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/app/door_codes.py`: `_already_gone` (which errors may trigger a lookup) and the inner try in `_revoke_one` (only `PIN_GONE` swallows the error).

## Owner steps

1. Open the pull request for `task/1155b-door-recancel-gone` as a draft after 1155 is merged.
2. When CI is green and the review is done, run `scripts/merge-pr-on-green.sh <PR number>` (rule 8).
3. The orchestrator then removes K-DC-RECANCEL from `docs/context/known-issues.md`. If you ever see the real TTLock errcode for "passcode does not exist" in a log line (`ttlock path=/v3/keyboardPwd/delete ... errcode=N`), tell the orchestrator: mapping it removes the extra lookup.
