# 1149: a revoke that loses its race re-issues the guest's door code

Status: todo
Depends on: none | Base commit: HEAD of branch claude/zealous-maxwell-a7ub54 | Branch: task/1149-door-revoke-lost-race
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When `door_codes._revoke_one` deletes the lock code but its result UPDATE changes 0 rows because the stay came back, the row stays `issued` with a PIN that no longer exists on the lock (K-DC-LOST, from 1141). Fix: when the row is still `issued` with the deleted code id and the stay is live, move it `issued -> pending` in one guarded UPDATE and call `issue()` at once, so the guest gets a new working code and the new-code mail. Otherwise change nothing. A failed re-issue reuses the existing retry loop and the existing `door_code_delayed` / failed host alerts: no new alert, no new mail kind, no migration, no dependency.

## 2. Context

Rules: SQL only through `db` helpers, Postgres-portable; `door_codes.TRANSITIONS` is mirrored in `go/internal/statemachine/tables.go` (`test_sm_go_parity.py` fails if they differ); every state writer is pinned in `PINNED` of `test_sm_door_code_state.py`. Anchors are verbatim from HEAD; if one is missing, STOP (§8).

**Revoke path** (`App/app/door_codes.py` `_revoke_one`): claim lease (`claimed_at`, `LEASE_MINUTES = 2`) -> stay-live check (live: `_keep_issued`, return) -> `ttlock.delete_code` (lock drops the PIN) -> state-guarded UPDATE `revoke_pending -> revoked`. The revive loop in `_handle_cancellations` calls `_keep_issued` with no held claim, which skips a row whose lease is under 2 minutes old. So the row is lost only when the delete outlasts the lease (stalled process, paused worker, many token refreshes; the gateway timeout is 35 s per call) and the stay is revived in that window. `issue()` only claims `pending`/`retrying`; `_handle_moves` only selects `issued` rows; `reconcile` expiry only touches `issued`. So only a revival can win.

**Simulation** (throwaway, real functions, fake lock holding the PINs, forced inside `ttlock.delete_code` after the lock dropped the PIN; run on SQLite and on Postgres, identical). `lost` = the `door_code_revoke_lost_race` audit. `BAD` = row `issued`, guest PIN gone from the lock.

| # | Interleaving | Final row | Lock | Guest code | Real-code result |
|---|---|---|---|---|---|
| S1 | No competitor | revoked | empty | n/a (cancelled) | ok |
| S2 | Revival while lease fresh (<2 min) | revoked, then reset and re-issued next tick | new PIN | works | ok |
| S3 | Revival after lease expired (the lost race) | issued, old id | empty | dead | **BAD, reproduced** |
| S4 | S3 plus a date move making a new code | issued, new id | new PIN | works | ok (old id deleted, row is fine) |
| S5 | Second revoke after lease expiry | revoked | empty | n/a | ok (`lost` audit only) |
| S6 | `issue()` during the delete | revoked | empty | n/a | ok (`issue()` returns False) |
| S7 | S3 while the operator has paused the plan | issued, old id | empty | dead | **BAD, reproduced** |
| S8 | Delete times out after the lock executed it, later revival | issued, old id | empty | dead | **BAD, reproduced** (no `lost` audit: out of scope, see below) |
| S9 | Process crashes after the delete, revival after the lease | issued, old id | empty | dead | **BAD, reproduced** (same, out of scope) |
| S10 | Crash after the delete, stay stays cancelled, retry | revoked | empty | n/a | ok |
| S11 | Delete refused (permission), revival | issued | PIN still there | works | ok |

So the lost-race bad state (S3, S7) is real. A competing date move (S4) is harmless, so the fix must test `provider_code_id`. S8 and S9 produce the same bad row without a 0-row UPDATE: the delete result is unknown until the lock is queried. They are NOT fixed here (they need a `find_code_by_name` call per revival); they become follow-up 1149b if the owner wants it.

Existing test that must keep passing, `App/tests/test_door_code_cancel_guard.py`: the stay is still cancelled when the row flips to `issued`, and the row stays `issued` with no mail. The fix leaves it alone because the stay is not live (SQL EXISTS guard).

Anchor A, `App/app/door_codes.py` (TRANSITIONS):
```python
    ISSUED: {
        REVOKE_PENDING,  # _handle_cancellations: stay cancelled before valid_to
        EXPIRED,  # reconcile: valid_to has passed
    },
```
Anchor B, `App/app/door_codes.py` (in `_revoke_one`):
```python
            db.audit(
                "door_code_revoke_lost_race",
                f"door_code={row_id}",
                actor="system",
                owner_user_id=apartment["owner_user_id"],
            )
            return
```
Anchor C, `App/app/door_codes.py`: the line `def _revoke_one(row_id: int) -> None:` (once).
Anchor D, `go/internal/statemachine/tables.go`: `"issued":         {"expired", "revoke_pending"},`
Anchor E, `App/tests/test_sm_door_code_state.py`: `    ("_handle_cancellations", ("pending", "retrying"), ("pending", "retrying"), ("revoked",)),`

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | one transition, one helper, one call |
| go/internal/statemachine/tables.go | edit | mirror the transition |
| App/tests/test_sm_door_code_state.py | edit | pin the new writer |
| App/tests/test_door_code_lost_pin.py | create | 7 tests |
| docs/tasks/1149-report.md | create | report (§9) |

No other file may change.

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30`; expected `claude/zealous-maxwell-a7ub54`. Then `git switch -c task/1149-door-revoke-lost-race | tail -30`; expected `Switched to a new branch`.

**Step 2. door_codes.py: declare the transition.** Replace Anchor A with
```python
    ISSUED: {
        REVOKE_PENDING,  # _handle_cancellations: stay cancelled before valid_to
        EXPIRED,  # reconcile: valid_to has passed
        PENDING,  # _reissue_lost_pin: a revoke deleted the lock code, the stay is live
    },
```
Command: `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -30` -> no output.

**Step 3. door_codes.py: the helper.** Insert this function immediately above Anchor C (one blank line pair between functions):
```python
def _reissue_lost_pin(row_id: int, deleted_code_id: str, owner_user_id: int) -> None:
    """A revoke deleted the lock code but lost the row to a revival: make a new code.

    One guarded UPDATE decides, so nothing is re-issued unless the row is still issued
    with the code id that was just deleted (a date move already made a new code: the id
    differs) and the stay is live (a cancelled stay is left to the next revoke). The
    row goes issued -> pending and issue() runs at once, so a success leaves no pending
    row for _alert_delayed. A failure is handled by issue() and the retry loop: their
    host alerts and mails are reused, no new alert.
    """
    now_iso = _iso(_now())
    if db.execute(
        "UPDATE door_code SET state = ?, pin_enc = NULL, provider_code_id = NULL, "
        "issued_at = NULL, notified_at = NULL, claimed_at = NULL, attempts = 0, "
        "next_attempt_at = NULL, last_error = ?, updated_at = ? "
        "WHERE id = ? AND state = ? AND provider_code_id = ? "
        "AND EXISTS (SELECT 1 FROM reservation r WHERE r.id = door_code.reservation_id "
        "AND r.status = 'active' AND r.archived_at IS NULL)",
        (PENDING, "pin_lost", now_iso, row_id, ISSUED, deleted_code_id),
    ) != 1:
        return
    db.audit(
        "door_code_pin_reissued",
        f"door_code={row_id}",
        actor="system",
        owner_user_id=owner_user_id,
    )
    try:
        issue(row_id, allow_gateway=True)
    except Exception:
        log.exception("door code %s: re-issue after a lost revoke failed", row_id)
```
Command: `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -30` -> no output.

**Step 4. door_codes.py: the call.** In Anchor B replace the last two lines (`            )` then `            return`) with
```python
            )
            _reissue_lost_pin(row_id, str(row["provider_code_id"] or ""), apartment["owner_user_id"])
            return
```
(`row` is the SELECT made before the delete, so it holds the id that was deleted.) Command: `grep -c "_reissue_lost_pin" App/app/door_codes.py | tail -30` -> `3` (the TRANSITIONS comment, the def, the call).

**Step 5. tables.go.** Replace Anchor D with `"issued":         {"expired", "pending", "revoke_pending"},`. Command: `cd go && go test ./internal/statemachine/... 2>&1 | tail -30` -> `ok`.

**Step 6. PINNED.** Insert this line directly above Anchor E:
```python
    ("_reissue_lost_pin", ("issued",), ("issued",), ("pending",)),
```
Command (from `App/`): `.venv/bin/python -m pytest tests/test_sm_door_code_state.py tests/test_sm_go_parity.py -q --tb=short -x 2>&1 | tail -30` -> `25 passed`.

**Step 7. Create `App/tests/test_door_code_lost_pin.py`** with exactly:
```python
"""1149: a revoke that deleted the lock code but lost the row must not leave a dead PIN.

A fake lock holds the PINs. Each test makes a competing writer run inside the
delete call, after the lock has dropped the PIN, then checks the row against the lock.
"""
from __future__ import annotations

import itertools
from datetime import timedelta

import pytest

from app import alerts, config, db, door_codes, ttlock
from tests.test_door_code_cancel_guard import _audits, _cancelled_stay, _code, _purge, _state


class FakeLock:
    def __init__(self):
        self.pins = {"pid-1": "4821937"}
        self.made = 0
        self.fail_create = None
        self._seq = itertools.count(2)

    def delete(self, account_id, lock_id, code_id, priority=None):
        self.pins.pop(str(code_id), None)

    def create(self, *args, **kwargs):
        if self.fail_create:
            raise self.fail_create
        self.made += 1
        code_id = f"pid-{next(self._seq)}"
        self.pins[code_id] = "5550000"
        return "5550000", code_id


@pytest.fixture
def world(monkeypatch):
    db.init_db()
    _purge()
    lock = FakeLock()
    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(ttlock, "account_for", lambda owner: {"id": 1, "status": "ok"})
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: True)
    monkeypatch.setattr(ttlock, "delete_code", lambda *a, **k: lock.delete(*a, **k))
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: lock.create())
    monkeypatch.setattr(ttlock, "add_custom_code", lambda *a, **k: lock.create())
    monkeypatch.setattr(ttlock, "find_code_by_name", lambda *a, **k: None)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_notice", lambda *a, **k: None)
    monkeypatch.setattr(door_codes.mail_notify, "door_code_delayed_notice", lambda *a, **k: None)
    monkeypatch.setattr(door_codes.push, "door_code_missing", lambda *a, **k: None)
    monkeypatch.setattr(door_codes.mail, "drain", lambda **k: None)
    sent: list = []
    monkeypatch.setattr(door_codes, "send_code_mail", lambda row_id: sent.append(row_id))
    apartment, stay = _cancelled_stay()
    row = _code(apartment, stay, door_codes.REVOKE_PENDING, valid_to="2099-01-01T00:00:00+00:00")
    db.execute("UPDATE door_code SET valid_from = ? WHERE id = ?", ("2098-12-30T00:00:00+00:00", row))
    yield lock, stay, row, sent
    _purge()


def _revive(stay):
    db.execute("UPDATE reservation SET status = 'active' WHERE id = ?", (stay,))


def _expire_lease(row):
    old = door_codes._iso(door_codes._now() - timedelta(minutes=door_codes.LEASE_MINUTES + 1))
    db.execute("UPDATE door_code SET claimed_at = ? WHERE id = ?", (old, row))


def _revive_after_lease(monkeypatch, lock, stay, row, extra=None):
    """Delete runs on the lock, takes longer than the lease, the stay comes back."""
    def slow_delete(*a, **k):
        lock.delete(*a, **k)
        _revive(stay)
        _expire_lease(row)
        door_codes._handle_cancellations(db.utcnow())
        if extra:
            extra()

    monkeypatch.setattr(ttlock, "delete_code", slow_delete)


def _row(row):
    return db.query_one("SELECT * FROM door_code WHERE id = ?", (row,))


def test_lost_race_with_a_live_stay_gets_a_new_working_pin(world, monkeypatch):
    lock, stay, row, sent = world
    lost, again = _audits("door_code_revoke_lost_race"), _audits("door_code_pin_reissued")
    _revive_after_lease(monkeypatch, lock, stay, row)
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.ISSUED
    assert after["provider_code_id"] in lock.pins and after["provider_code_id"] != "pid-1"
    assert "pid-1" not in lock.pins and lock.made == 1
    assert db.decrypt_field(after["pin_enc"]) == "5550000"
    assert sent == [row]
    assert _audits("door_code_revoke_lost_race") == lost + 1
    assert _audits("door_code_pin_reissued") == again + 1


def test_a_date_move_that_won_is_left_alone(world, monkeypatch):
    lock, stay, row, sent = world

    def move():
        code_id = lock.create()[1]
        db.execute("UPDATE door_code SET provider_code_id = ? WHERE id = ?", (code_id, row))

    _revive_after_lease(monkeypatch, lock, stay, row, extra=move)
    again = _audits("door_code_pin_reissued")
    door_codes._revoke_one(row)
    after = _row(row)
    assert after["state"] == door_codes.ISSUED and after["provider_code_id"] == "pid-2"
    assert list(lock.pins) == ["pid-2"] and lock.made == 1
    assert _audits("door_code_pin_reissued") == again


def test_a_stay_cancelled_again_is_not_reissued(world, monkeypatch):
    lock, stay, row, sent = world
    monkeypatch.setattr(
        ttlock,
        "delete_code",
        lambda *a, **k: (
            lock.delete(*a, **k),
            db.execute("UPDATE door_code SET state = ?, claimed_at = NULL WHERE id = ?", (door_codes.ISSUED, row)),
        ),
    )
    again = _audits("door_code_pin_reissued")
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.ISSUED
    assert lock.made == 0 and sent == []
    assert _audits("door_code_pin_reissued") == again


def test_a_second_revoke_that_won_needs_no_reissue(world, monkeypatch):
    lock, stay, row, sent = world
    calls = {"n": 0}

    def delete(*a, **k):
        lock.delete(*a, **k)
        calls["n"] += 1
        if calls["n"] == 1:
            _expire_lease(row)
            door_codes._revoke_one(row)

    monkeypatch.setattr(ttlock, "delete_code", delete)
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKED
    assert lock.made == 0 and lock.pins == {}


def test_a_new_issue_cannot_touch_a_revoke_pending_row(world, monkeypatch):
    lock, stay, row, sent = world
    seen = {}

    def delete(*a, **k):
        lock.delete(*a, **k)
        seen["issue"] = door_codes.issue(row, allow_gateway=True)

    monkeypatch.setattr(ttlock, "delete_code", delete)
    door_codes._revoke_one(row)
    assert seen == {"issue": False}
    assert _state(row) == door_codes.REVOKED and lock.made == 0


def test_operator_pause_keeps_the_row_pending_until_the_plan_is_back(world, monkeypatch):
    lock, stay, row, sent = world
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: False)
    _revive_after_lease(monkeypatch, lock, stay, row)
    door_codes._revoke_one(row)
    held = _row(row)
    assert held["state"] == door_codes.PENDING and held["pin_enc"] is None
    assert lock.made == 0
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: True)
    door_codes._issue_due(db.utcnow())
    back = _row(row)
    assert back["state"] == door_codes.ISSUED and back["provider_code_id"] in lock.pins


def test_a_failed_reissue_alerts_the_host_once(world, monkeypatch):
    lock, stay, row, sent = world
    lock.fail_create = ttlock.TTLockError("busy", kind="transient")
    _revive_after_lease(monkeypatch, lock, stay, row)
    door_codes._revoke_one(row)
    assert _state(row) in (door_codes.RETRYING, door_codes.PENDING)
    assert lock.pins == {}
    db.execute("UPDATE reservation SET registration_completed_at = ? WHERE id = ?", ("2000-01-01T00:00:00+00:00", stay))
    door_codes._alert_delayed()
    door_codes._alert_delayed()
    n = db.query_one(
        "SELECT COUNT(*) AS n FROM alert WHERE kind = 'door_code_delayed' AND reservation_id = ? AND resolved_at IS NULL",
        (stay,),
    )["n"]
    assert n == 1
    lock.fail_create = None
    db.execute("UPDATE door_code SET next_attempt_at = NULL WHERE id = ?", (row,))
    door_codes._issue_due(db.utcnow())
    assert _state(row) == door_codes.ISSUED
```
Command (from `App/`): `.venv/bin/python -m pytest tests/test_door_code_lost_pin.py tests/test_door_code_cancel_guard.py -q --tb=short -x 2>&1 | tail -30` -> `19 passed`.

**Step 8. Commit.** `git add App/app/door_codes.py App/tests/test_door_code_lost_pin.py App/tests/test_sm_door_code_state.py go/internal/statemachine/tables.go && git commit -m "1149: re-issue the door code when a revoke loses its race" | tail -30`.
Commit message ends with the attribution lines the session reminder gives.

**Step 9. Revert-bite, four runs.** Each run: apply the `sed`, run the command, expect the named tests to FAIL, then `git checkout App/app/door_codes.py`. All commands from the repo root. Test command `T`: `cd App && .venv/bin/python -m pytest tests/test_door_code_lost_pin.py -q --tb=no 2>&1 | tail -30`.
- (a) No re-issue: `sed -i 's/^            _reissue_lost_pin(row_id, .*$/            pass/' App/app/door_codes.py` then `T`: expect 3 failed (`..gets_a_new_working_pin`, `operator_pause...`, `failed_reissue...`).
- (b) Id guard removed: `sed -i 's/AND state = ? AND provider_code_id = ? "/AND state = ? AND ? IS NOT NULL "/' App/app/door_codes.py` then `T`: expect `test_a_date_move_that_won_is_left_alone` failed.
- (c) Live-stay guard removed: `sed -i "s/AND r.status = 'active' AND r.archived_at IS NULL)\",\$/AND r.status != 'zzz')\",/" App/app/door_codes.py` then `T`: expect `test_a_stay_cancelled_again_is_not_reissued` failed.
- (d) No immediate issue: `sed -i 's/^        issue(row_id, allow_gateway=True)$/        pass/' App/app/door_codes.py` then `T`: expect `..gets_a_new_working_pin` failed.
After each, `git checkout App/app/door_codes.py | tail -30`. If a run does not fail as stated, STOP (§8). Finally `git status --short | tail -30` -> empty.

**Step 10. Door-codes row.** From `App/`: `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_sm_door_code_state.py tests/test_sm_go_parity.py -q --tb=short -x -rs 2>&1 | tail -30` -> all pass; the only skips allowed are the two `playwright` browser tests (do not install it: new dependency).

**Step 11. Postgres.** From `App/`: `UBYHOST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code_lost_pin.py tests/test_door_code_cancel_guard.py -q --tb=short 2>&1 | tail -30` -> `19 passed`. If the database is unreachable, record that in the report; do not fail the brief.

**Step 12. Lint and report.** `python3 scripts/context_lint.py | tail -3` -> `context lint: OK`. Write the report (§9), set `Status: review` in this file.

## 5. Do not touch

`ttlock.py`, `alerts.py`, `mail_notify.py`, migrations, templates, `docs/` other than this brief and its report. Hard rules 2 (no new personal data; `last_error = 'pin_lost'` is a code, not data), 4, 5. `door_codes.py` outside the three places above.

## 6. Commands

Steps 5, 6, 7, 10 and 11 above, every one ending `| tail -30`.

## 7. Acceptance

- [ ] `test_door_code_lost_pin.py`: 7 passed; `test_door_code_cancel_guard.py` unchanged and green.
- [ ] Each of the four revert-bite runs failed as listed, and the tree is clean afterwards.
- [ ] `test_sm_door_code_state.py` and `test_sm_go_parity.py` pass; `go test ./internal/statemachine/...` is ok.
- [ ] Door-codes row passes (2 playwright skips allowed).
- [ ] Lint OK. No file outside §3 changed (`git diff --stat HEAD~1 | tail -30`).

## 8. Stop and ask

Stop, and write the report, if an anchor is missing; a test fails twice; a revert-bite does not fail as stated; you reach 25 tool calls (write `blocked`); a new dependency or a migration seems needed; a file outside §3 needs a change; you need push, merge or deploy (hand to the owner).

## 9. Report

Write `docs/tasks/1149-report.md` (600 tokens at most), set `Status: review`: 1 files changed, 2 each command with the last 5 lines, 3 §7 ticked, 4 deviations, 5 questions, 6 owner steps left.

## Risk list (for the reviewer)

`App/app/door_codes.py`: `_reissue_lost_pin` (the UPDATE guards: state, deleted id, live stay) and its call. Rows re-issue at most once per lost race; a re-issue gives the guest a new PIN and a new code mail (the mail key includes the code id). While the plan is paused the row waits as `pending` and the guest page says "preparing".

## Owner steps

1. Open the PR when CI is green and merge with `scripts/merge-pr-on-green.sh`.
2. Decide 1149b: after a timed-out or crashed delete (S8, S9) a revival also leaves a dead PIN. Fixing it costs one TTLock list call per revived row that had a delete attempt. Say "do 1149b" or leave it as a known issue.
