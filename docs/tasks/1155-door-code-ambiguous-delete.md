# 1155: a revived door code whose delete may have run is checked on the lock (K-DC-AMBIG)

Status: todo
Depends on: none (1149 is merged) | Base commit: HEAD of branch claude/zealous-maxwell-a7ub54 | Branch: task/1155-door-ambig-delete
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

When a revoke's lock delete times out after the lock ran it, or the process dies right after the delete, the row stays `revoke_pending` / `revoke_failed` with its PIN; if the stay then comes back, `_keep_issued` marks it `issued` although the PIN is gone, and nothing is audited (K-DC-AMBIG, 1149 simulation rows S8 and S9). Fix: when a revived row had a delete attempt whose result is unknown, ask the lock once; if the code id is gone, re-issue through the 1149 path `_reissue_lost_pin` (which audits `door_code_pin_reissued`); if the lock cannot answer, keep the row and try again, then give up after 3 tries. No migration, no dependency, no new state transition, no new mail kind.

## 2. Context

Rules: SQL only through `db` helpers, Postgres-portable; no schema change; no new dependency (rule 4). Anchors are verbatim from HEAD; if one is missing, STOP (§8).

**Outbound-request reason (for the PR):** one extra `POST /v3/lock/listKeyboardPwd` (already in `ttlock.ALLOWED_PATHS`, already used by `issue()` retries through `find_code_by_name`) per revived row whose delete may have run, at most 3 per row, to confirm the guest's PIN still exists before the stay page shows it. No new host. It sends only what `issue()` already sends: lock id, the code name `UH-<row id>` and the stay window. Rows with no delete attempt, and rows already `issued`, cost no call, on every tick.

**How a delete attempt is detected (no marker, no migration).** `_handle_cancellations` sets `attempts = 0` when it moves `issued -> revoke_pending`. `_revoke_one` adds 1 to `attempts` when it claims the row, and only a claim on a cancelled stay goes on to `ttlock.delete_code`. A claim on a live stay ends in `_keep_issued`, which resets `attempts` to 0. So a revived row with `attempts` above 0 had a claim. The result of its delete is unknown when `last_error` is empty (a crash after the claim, or a timeout path that never wrote an error), `network` (timeout or non-JSON answer, `ttlock.py` `_post`), or `transient` (a server fault). Any other `last_error` is a definite answer from the API or lock (`offline`, `permission`, `no_account`, ...), so the PIN is still there and no call is made. `_revoke_one` calls `_revive_one` after its own claim, so it uses the threshold `attempts > 1` there.

**Decision, lookup fails (fail safe, bounded).** Marking the row `issued` without confirmation is the bug itself, so the first failures keep the row `revoke_pending` (the guest page shows no PIN, `view()` returns None for that state). The row's lease `claimed_at` holds the next try back by `LEASE_MINUTES` (2) with no new column. `attempts` counts the failed lookups (the first one restarts it at 1, `last_error = lookup_failed`). After 3 failed lookups the row is kept `issued` as before this brief and `door_code_pin_unverified` is audited, so a lasting TTLock error (permission, bad account) cannot hide a working PIN for good. `door_code_delayed` / failed alerts only look at pending rows and are not touched.

**Decision, a code with the same name and window but another id.** It is not this row's PIN: the row counts as gone and gets a new code.

**Existing tests that change:** `App/tests/test_door_code_lost_pin.py` (1149) revives a row whose claim made `attempts = 1`, so it would now reach the lookup. Its fixture `world` gets one line that stubs `_lock_code_state` as present, so those 7 tests still pin the 1149 zero-row path alone. Nothing else in the door-codes row is affected (checked: all of `test_door_codes_safeguards.py` uses `offline`, a definite answer, and still passes).

Anchor A, `App/app/door_codes.py`:
```python
LEASE_MINUTES = 2
# A guest who has finished registering must not wait longer than this in silence.
```
Anchor B, `App/app/door_codes.py` (once): `def _reissue_lost_pin(row_id: int, deleted_code_id: str, owner_user_id: int) -> None:`
Anchor C, `App/app/door_codes.py` (in `_revoke_one`):
```python
    if _stay_is_live(reservation):
        _keep_issued(row_id, now_iso, held_claim=now_iso)
        return
```
Anchor D, `App/app/door_codes.py` (in `_handle_cancellations`):
```python
        "SELECT dc.id FROM door_code dc "
        "JOIN reservation r ON r.id = dc.reservation_id "
        "WHERE dc.state IN (?, ?) AND r.status = 'active' AND r.archived_at IS NULL "
        "AND dc.pin_enc IS NOT NULL",
        (REVOKE_PENDING, REVOKE_FAILED),
    )
    for item in revived:
        if _keep_issued(int(item["id"]), now_iso):
```
Anchor E, `App/tests/test_door_code_lost_pin.py` (once): `    monkeypatch.setattr(ttlock, "find_code_by_name", lambda *a, **k: None)`

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/door_codes.py | edit | 5 constants, 3 helpers, 2 call sites |
| App/tests/test_door_code_lost_pin.py | edit | one fixture line |
| App/tests/test_door_code_ambiguous_delete.py | create | 7 tests |
| docs/tasks/1155-report.md | create | report (§9) |

No other file may change. No transition is added: `door_codes.TRANSITIONS`, `go/internal/statemachine/tables.go` and `test_sm_door_code_state.py` stay as they are (`_revive_one` writes only `claimed_at`, `attempts`, `last_error`; the state writers stay `_keep_issued` and `_reissue_lost_pin`).

## 4. Steps

**Step 1. Branch.** Run `git branch --show-current | tail -30`; expected `claude/zealous-maxwell-a7ub54`. Then `git switch -c task/1155-door-ambig-delete | tail -30`; expected `Switched to a new branch`.

**Step 2. Constants.** Replace Anchor A with
```python
LEASE_MINUTES = 2
# 1155: a revived row whose delete may have run is checked on the lock before it is shown.
PIN_PRESENT, PIN_GONE, PIN_UNKNOWN = "present", "gone", "unknown"
LOOKUP_FAILED = "lookup_failed"
LOOKUP_MAX_TRIES = 3
# last_error values that leave a delete's result unknown: none (a crash after the claim),
# a timeout or non-JSON answer (network), a server fault (transient), or a lookup that failed.
AMBIGUOUS_DELETE_ERRORS = ("", "network", "transient", LOOKUP_FAILED)
# A guest who has finished registering must not wait longer than this in silence.
```
Command: `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -30` -> no output.

**Step 3. Helpers.** Replace Anchor B (the single `def _reissue_lost_pin(...)` line) with the three functions below, then two blank lines, then the same `def _reissue_lost_pin(...)` line again (its body stays untouched):
```python
def _lock_code_state(row, owner_user_id: int) -> str:
    """Ask the lock, with one list call, whether the row's PIN still exists.

    PIN_UNKNOWN when the answer cannot be had (no account, no window, TTLock error):
    nothing is assumed either way. A code with the same name and window but another
    id is not this row's PIN, so it counts as gone.
    """
    account = ttlock.account_for(owner_user_id)
    if (
        not account
        or account["status"] != "ok"
        or not row["valid_from"]
        or not row["valid_to"]
        or not row["provider_code_id"]
    ):
        return PIN_UNKNOWN
    try:
        found = ttlock.find_code_by_name(
            int(account["id"]),
            row["lock_id"],
            f"UH-{row['id']}",
            _iso_to_ms(row["valid_from"]),
            _iso_to_ms(row["valid_to"]),
        )
    except ttlock.TTLockError:
        return PIN_UNKNOWN
    if found and str(found[1]) == str(row["provider_code_id"]):
        return PIN_PRESENT
    return PIN_GONE


def _note_failed_lookup(row_id: int, claim: str) -> int:
    """Count a failed lookup in attempts (restarted at 1 by the first one); return the count."""
    db.execute(
        "UPDATE door_code SET attempts = CASE WHEN last_error = ? THEN attempts + 1 ELSE 1 END, "
        "last_error = ?, updated_at = ? WHERE id = ? AND claimed_at = ?",
        (LOOKUP_FAILED, LOOKUP_FAILED, claim, row_id, claim),
    )
    row = db.query_one("SELECT attempts FROM door_code WHERE id = ?", (row_id,))
    return int(row["attempts"]) if row else LOOKUP_MAX_TRIES


def _revive_one(item, now_iso: str, held_claim: str | None = None) -> bool:
    """The stay is back: show the PIN again, but first confirm it still exists.

    Only a row whose delete may have run (attempts above the claim made by _revoke_one,
    and last_error in AMBIGUOUS_DELETE_ERRORS: a refusal by the lock or API is definite)
    costs one lock call.
    Gone: the row is kept, then _reissue_lost_pin makes a new code. Unknown: the row stays
    revoke_pending (the guest page shows no PIN) and its lease claimed_at delays the next
    try by LEASE_MINUTES; after LOOKUP_MAX_TRIES failures it is kept as before 1155 and
    audited door_code_pin_unverified, so a lasting TTLock error cannot hide the PIN.
    True if the row is issued again.
    """
    row_id = int(item["id"])
    attempted = (
        int(item["attempts"] or 0) > (1 if held_claim else 0)
        and (item["last_error"] or "") in AMBIGUOUS_DELETE_ERRORS
    )
    if not attempted:
        return _keep_issued(row_id, now_iso, held_claim=held_claim)
    claim = held_claim
    if claim is None:
        claim = _iso(_now())
        cutoff = _iso(_now() - timedelta(minutes=LEASE_MINUTES))
        if db.execute(
            "UPDATE door_code SET claimed_at = ?, updated_at = ? WHERE id = ? AND state IN (?, ?) "
            "AND (claimed_at IS NULL OR claimed_at < ?)",
            (claim, now_iso, row_id, REVOKE_PENDING, REVOKE_FAILED, cutoff),
        ) != 1:
            return False
    apartment = db.query_one("SELECT owner_user_id FROM apartment WHERE id = ?", (item["apartment_id"],))
    owner_id = int(apartment["owner_user_id"]) if apartment else 0
    verdict = _lock_code_state(item, owner_id)
    unverified = False
    if verdict == PIN_UNKNOWN:
        if _note_failed_lookup(row_id, claim) < LOOKUP_MAX_TRIES:
            return False
        unverified = True
    if not _keep_issued(row_id, now_iso, held_claim=claim):
        return False
    if unverified:
        db.audit("door_code_pin_unverified", f"door_code={row_id}", actor="system", owner_user_id=owner_id)
    elif verdict == PIN_GONE:
        _reissue_lost_pin(row_id, str(item["provider_code_id"] or ""), owner_id)
    return True
```
Command: `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -30` -> no output.

**Step 4. `_revoke_one` call.** Replace Anchor C with
```python
    if _stay_is_live(reservation):
        _revive_one(row, now_iso, held_claim=now_iso)
        return
```
(`row` is the SELECT made after the claim, so its `attempts` already counts this claim.) Command: `grep -c "_revive_one" App/app/door_codes.py | tail -30` -> `3` (the def and the two calls, after step 5).

**Step 5. Revived loop.** Replace Anchor D with
```python
        "SELECT dc.* FROM door_code dc "
        "JOIN reservation r ON r.id = dc.reservation_id "
        "WHERE dc.state IN (?, ?) AND r.status = 'active' AND r.archived_at IS NULL "
        "AND dc.pin_enc IS NOT NULL",
        (REVOKE_PENDING, REVOKE_FAILED),
    )
    for item in revived:
        if _revive_one(item, now_iso):
```
Command: `grep -c "_revive_one" App/app/door_codes.py | tail -30` -> `3`; `cd App && .venv/bin/python -c "import app.door_codes" 2>&1 | tail -30` -> no output.

**Step 6. 1149 fixture.** Replace Anchor E with
```python
    monkeypatch.setattr(ttlock, "find_code_by_name", lambda *a, **k: None)
    # 1155 checks a revived row on the lock; these tests pin the 1149 zero-row path alone.
    monkeypatch.setattr(door_codes, "_lock_code_state", lambda *a, **k: door_codes.PIN_PRESENT)
```
Command (from `App/`): `.venv/bin/python -m pytest tests/test_door_code_lost_pin.py tests/test_door_code_cancel_guard.py tests/test_sm_door_code_state.py -q --tb=short 2>&1 | tail -30` -> `30 passed`.

**Step 7. Create `App/tests/test_door_code_ambiguous_delete.py`** with exactly:
```python
"""1155: a revived row whose delete may have run is checked on the lock before it is shown.

A fake lock holds the PINs. The delete is made to time out or crash after the lock
dropped the PIN, the stay comes back, and the row must not stay "issued" with a dead PIN.
"""
from __future__ import annotations

import pytest

from app import config, db, door_codes, ttlock
from tests.test_door_code_cancel_guard import _audits, _cancelled_stay, _code, _purge, _state
from tests.test_door_code_lost_pin import FakeLock, _expire_lease, _revive, _row


class Crash(BaseException):
    """A process death: nothing in door_codes catches it."""


@pytest.fixture
def world(monkeypatch):
    db.init_db()
    _purge()
    lock = FakeLock()
    lock.lookups = 0
    lock.lookup_error = None

    def find(*args, **kwargs):
        lock.lookups += 1
        if lock.lookup_error:
            raise lock.lookup_error
        for code_id, pin in lock.pins.items():
            return pin, code_id
        return None

    monkeypatch.setattr(config, "DOOR_CODES_ENABLED", True)
    monkeypatch.setattr(ttlock, "account_for", lambda owner: {"id": 1, "status": "ok"})
    monkeypatch.setattr(ttlock, "allowed_for", lambda owner: True)
    monkeypatch.setattr(ttlock, "delete_code", lambda *a, **k: lock.delete(*a, **k))
    monkeypatch.setattr(ttlock, "create_period_code", lambda *a, **k: lock.create())
    monkeypatch.setattr(ttlock, "add_custom_code", lambda *a, **k: lock.create())
    monkeypatch.setattr(ttlock, "find_code_by_name", find)
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


def _delete_then(monkeypatch, lock, error):
    def delete(*a, **k):
        lock.delete(*a, **k)
        raise error

    monkeypatch.setattr(ttlock, "delete_code", delete)


def _tick():
    door_codes._handle_cancellations(db.utcnow())


def _assert_new_working_pin(lock, row, sent):
    after = _row(row)
    assert after["state"] == door_codes.ISSUED
    assert after["provider_code_id"] in lock.pins and after["provider_code_id"] != "pid-1"
    assert "pid-1" not in lock.pins and lock.made == 1
    assert db.decrypt_field(after["pin_enc"]) == "5550000"
    assert sent == [row]


def test_a_delete_that_timed_out_after_the_lock_ran_it_gets_a_new_pin(world, monkeypatch):
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and lock.pins == {}
    _revive(stay)
    again = _audits("door_code_pin_reissued")
    _tick()
    _assert_new_working_pin(lock, row, sent)
    assert _audits("door_code_pin_reissued") == again + 1
    assert lock.lookups == 1


def test_a_crash_after_the_delete_gets_a_new_pin_once_the_lease_ends(world, monkeypatch):
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, Crash())
    with pytest.raises(Crash):
        door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_PENDING and lock.pins == {}
    _revive(stay)
    _tick()
    assert _state(row) == door_codes.REVOKE_PENDING and lock.lookups == 0  # lease still fresh
    _expire_lease(row)
    _tick()
    _assert_new_working_pin(lock, row, sent)
    assert lock.lookups == 1


def test_a_delete_the_lock_refused_keeps_its_pin_and_costs_no_lookup(world, monkeypatch):
    lock, stay, row, sent = world

    def refuse(*a, **k):
        raise ttlock.TTLockError("no permission", code=-2018, kind="permission")

    monkeypatch.setattr(ttlock, "delete_code", refuse)
    door_codes._revoke_one(row)
    assert _state(row) == door_codes.REVOKE_FAILED
    _revive(stay)
    again = _audits("door_code_pin_reissued")
    _tick()
    after = _row(row)
    assert after["state"] == door_codes.ISSUED and after["provider_code_id"] == "pid-1"
    assert lock.pins == {"pid-1": "4821937"} and lock.made == 0 and sent == []
    assert _audits("door_code_pin_reissued") == again
    assert lock.lookups == 0


def test_a_row_without_a_delete_attempt_and_an_issued_row_cost_no_lookup(world):
    lock, stay, row, sent = world
    _revive(stay)
    _tick()
    assert _state(row) == door_codes.ISSUED
    _tick()
    _tick()
    assert lock.lookups == 0 and lock.made == 0 and sent == []


def test_a_revoke_that_finds_the_stay_live_checks_a_row_that_had_a_delete_attempt(world):
    lock, stay, row, sent = world
    lock.pins.clear()
    db.execute("UPDATE door_code SET attempts = 1 WHERE id = ?", (row,))
    _revive(stay)
    door_codes._revoke_one(row)
    _assert_new_working_pin(lock, row, sent)
    assert lock.lookups == 1


def test_a_failed_lookup_keeps_the_row_then_gives_up_after_three_tries(world, monkeypatch):
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    _revive(stay)
    lock.lookup_error = ttlock.TTLockError("busy", kind="transient")
    _tick()
    held = _row(row)
    assert held["state"] == door_codes.REVOKE_PENDING and held["last_error"] == door_codes.LOOKUP_FAILED
    assert held["attempts"] == 1 and lock.lookups == 1
    _tick()
    assert lock.lookups == 1  # the lease holds the next try back
    _expire_lease(row)
    _tick()
    assert _row(row)["attempts"] == 2 and lock.lookups == 2
    unverified = _audits("door_code_pin_unverified")
    _expire_lease(row)
    _tick()
    after = _row(row)
    assert after["state"] == door_codes.ISSUED and after["provider_code_id"] == "pid-1"
    assert lock.lookups == 3 and lock.made == 0
    assert _audits("door_code_pin_unverified") == unverified + 1


def test_a_lookup_that_fails_once_and_then_works_still_re_issues(world, monkeypatch):
    lock, stay, row, sent = world
    _delete_then(monkeypatch, lock, ttlock.TTLockError("timeout", kind="network"))
    door_codes._revoke_one(row)
    _revive(stay)
    lock.lookup_error = ttlock.TTLockError("busy", kind="transient")
    _tick()
    assert _state(row) == door_codes.REVOKE_PENDING
    lock.lookup_error = None
    _expire_lease(row)
    _tick()
    _assert_new_working_pin(lock, row, sent)
```
Command (from `App/`): `.venv/bin/python -m pytest tests/test_door_code_ambiguous_delete.py tests/test_door_code_lost_pin.py tests/test_door_code_cancel_guard.py tests/test_sm_door_code_state.py -q --tb=short 2>&1 | tail -30` -> `37 passed`.

**Step 8. Commit.** `git add App/app/door_codes.py App/tests/test_door_code_lost_pin.py App/tests/test_door_code_ambiguous_delete.py && git commit -m "1155: check a revived door code on the lock when its delete may have run" | tail -30`.
Commit message ends with the attribution lines the session reminder gives.

**Step 9. Revert-bite, six runs.** Each run, all from the repo root: apply the `sed`, run `T`, expect the named result, then `git checkout App/app/door_codes.py | tail -30`. `T` is `cd App && .venv/bin/python -m pytest tests/test_door_code_ambiguous_delete.py -q --tb=no 2>&1 | tail -30`. After the `sed`, `git diff --stat | tail -30` must show `1 file changed, 1 insertion(+), 1 deletion(-)`; if not, STOP (§8).
- (a) No lookup: `sed -i 's/^    verdict = _lock_code_state(item, owner_id)$/    verdict = PIN_PRESENT/' App/app/door_codes.py` then `T`: `5 failed, 2 passed` (`..without_a_delete_attempt..` and `delete_the_lock_refused..` pass).
- (b) No re-issue on gone: `sed -i 's/^    elif verdict == PIN_GONE:$/    elif False:/' App/app/door_codes.py` then `T`: `4 failed, 3 passed` (`timed_out`, `crash`, `revoke_that_finds_the_stay_live`, `fails_once_and_then_works`).
- (c) No retry on unknown: `sed -i 's/^        if _note_failed_lookup(row_id, claim) < LOOKUP_MAX_TRIES:$/        if False:/' App/app/door_codes.py` then `T`: `2 failed, 5 passed` (`failed_lookup_keeps_the_row`, `fails_once_and_then_works`).
- (d) Lookup on every revived row: `sed -i 's/^        int(item\["attempts"\] or 0) > (1 if held_claim else 0)$/        True/' App/app/door_codes.py` then `T`: `1 failed, 6 passed` (`..without_a_delete_attempt..`).
- (e) `_revoke_one` skips the check: `sed -i 's/^        _revive_one(row, now_iso, held_claim=now_iso)$/        _keep_issued(row_id, now_iso, held_claim=now_iso)/' App/app/door_codes.py` then `T`: `1 failed, 6 passed` (`revoke_that_finds_the_stay_live`).
- (f) Lookup after a definite refusal: `sed -i 's/^        and (item\["last_error"\] or "") in AMBIGUOUS_DELETE_ERRORS$/        and True/' App/app/door_codes.py` then `T`: `1 failed, 6 passed` (`delete_the_lock_refused..`).
If a run does not fail as stated, STOP (§8). Finally `git status --short | tail -30` -> empty.

**Step 10. Door-codes row (test-map).** From `App/`: `.venv/bin/python -m pytest tests/test_door_code*.py tests/test_ttlock*.py tests/test_smart_locks_page.py tests/test_sm_door_code_state.py tests/test_sm_go_parity.py -q --tb=short -rs 2>&1 | tail -30` -> no failures; the only skips allowed are the two `playwright` browser tests (do not install it: new dependency).

**Step 11. Lint.** From `App/`: `.venv/bin/ruff check app tests --select E9,F63,F7,F82,F401,F841 2>&1 | tail -30` -> `All checks passed!`.

**Step 12. Postgres.** From `App/`: `UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_door_code_ambiguous_delete.py tests/test_door_code_lost_pin.py tests/test_door_code_cancel_guard.py tests/test_door_codes_safeguards.py -q --tb=short 2>&1 | tail -30` -> all pass. If Postgres is not running, write `not run: no Postgres` in the report.

**Step 13. Report.** Write `docs/tasks/1155-report.md` (§9), set this file's line 3 to `Status: review`, then `python3 scripts/context_lint.py | tail -3` from the repo root.

## 5. Do not touch

`App/app/ttlock.py` (no new call function: `find_code_by_name` is reused), `docs/context/*` (the orchestrator closes K-DC-AMBIG), migrations, `go/`, `_reissue_lost_pin` and `_keep_issued` bodies. Hard rules: 3 (no secrets or guest data in tests: the PINs are fake), 4, 5.

## 6. Commands

All Python from `App/`, each ending `2>&1 | tail -30`: Steps 2 to 12 give the exact command and result. Never the full suite.

## 7. Acceptance

- [ ] `test_door_code_ambiguous_delete.py` is 7 passed; the 1149 and cancel-guard tests still pass (37 with the state test).
- [ ] The six revert-bite runs fail as stated and `git status --short` is empty afterwards.
- [ ] The door-codes row passes with only the two `playwright` skips; ruff passes; Postgres run passes or is reported as not run.
- [ ] `grep -c "_lock_code_state\|find_code_by_name" App/app/door_codes.py | tail -30` shows the lookup is called from `_lock_code_state` only for the revive (the `issue()` retry call is the other one).
- [ ] The report lists the outbound-request reason line from §2.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found verbatim;
- a test fails twice;
- a revert-bite run does not fail as stated;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency, a migration or a new state transition seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1155-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/app/door_codes.py`: `_revive_one` (the claim, the three verdicts, the give-up after 3 tries), the `attempted` condition, and the two call sites. `_lock_code_state` is shared with brief 1155b.

## Owner steps

1. Open the pull request for `task/1155-door-ambig-delete` as a draft; paste the outbound-request reason from §2 into its description.
2. When CI is green and the review is done, run `scripts/merge-pr-on-green.sh <PR number>` (rule 8). Merging deploys.
3. The orchestrator then removes K-DC-AMBIG from `docs/context/known-issues.md` and adds one line to `docs/context/decisions.md`: fail safe for 3 lookups, then show the PIN and audit `door_code_pin_unverified`.
