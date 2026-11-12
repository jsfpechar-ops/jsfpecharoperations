# 1150: iCal date move over a crash-stuck `running` filing (K-F22), Python

Status: todo
Depends on: 1148 (merged; the helper `_running_submission_covers_stay` is reused) | Base commit: a176c3ee (HEAD of branch claude/zealous-maxwell-a7ub54) | Branch: task/1150-ical-move-running
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK filing path: the reviewer reads every diff line in the Risk list. Go twin: brief 1150b (runs after this one). Do both before merging either.

## 1. Objective

Close K-F22 in Python. An iCal date move (a changed `DTSTART`/`DTEND` for a known stay) does not see a `running` submission whose send crashed: no guest points at it, so the guard `_send_in_flight` says "nothing in flight" and the stay and the unsent guest windows are rewritten while UbyPort may hold the old window. After this brief the move is deferred (stored dates kept, feed digest not stored, next poll retries) while a `running` submission lists an unsent guest of the stay, and the docstring that wrongly claimed this case was covered is corrected.

## 2. Context

Rule 1: UbyPort filing correctness beats every other feature. Read nothing else; the reasoning is here.

**The gap.** A guest is pointed at a batch (`guest.submission_id`) only when the batch ends `outcome_unknown` (reporting.py:2127, `recover_stale_submissions`). While a batch is `running` the only link is `submission.guest_ids` (JSON). Crash timeline: sender crashes mid-send; the claim expires after 5 minutes (`SUBMISSION_CLAIM_TTL_SECONDS`); `recover_stale_submissions` (reporting.py:2085) turns the row into `outcome_unknown` and points the guests, but it only runs in the sweep (every 10 minutes, non-`manual` apartments, reporting.py:2409) or at the start of a send (reporting.py:2360). A calendar date move arriving in between sees no live claim and no pointed guest, so it lands. `_update_reservation_unless_claimed` (1143/1136) cannot help: it guards only live claims.

**Decision for a `running` row of any age (owner left this open; decided here from the code).**
- `outcome_unknown` on a move: already defers, and for ever until the host resolves it. `_send_in_flight` ends in `_pointed_at_open_submission`, which joins `guest.submission_id` to `submission.state IN ('running','outcome_unknown')`. Unchanged.
- A `running` row older than 30 minutes: ALSO defers. This differs from the cancel policy of 1148 on purpose. A cancel changes only the stay status; it never touches what was filed, so letting it through with an alert (`cancelled_filing_unconfirmed`) is safe. A move rewrites `stay_from`/`stay_to` of the unsent guests, which destroys the record of what the register may already hold; correctness beats freshness. And a `running` row of any age is an `outcome_unknown` that has not been written yet: `recover_stale_submissions` tests only the claim, never the age, so the next sweep or manual send converts it, and that state already defers a move for ever. The 30-minute bound would therefore only open a window in which the move lands over an unconfirmed filing, then the row becomes `outcome_unknown` with the new window on the guest.
- So `RUNNING_CANCEL_DEFER_SECONDS` and `_running_defers_cancel` are NOT used here and are not renamed. The move check calls `_running_submission_covers_stay(reservation_id)` with no cutoff.
- No new alert. The case "move went through over an unconfirmed filing" no longer exists. The existing `moved_after_report` (icalsync.py ~1045, raised when a move lands over a guest that is `sent`) is unchanged and stays correct. A forever-stuck `running` row of a `manual` apartment is resolved by the host's next send (it calls `recover_stale_submissions` first) and then shows the existing critical `submission_outcome_unknown` alert. Residual, not fixed: until then the deferral is silent (log line `ical_dates_deferred_in_flight` only).
- A `running` row that lists only a `sent` guest, or only guests of other stays, must NOT defer (`_running_submission_covers_stay` already filters on unsent guests of this reservation).

**Masked by an existing test.** `_unclear_batch(..., state="running")` in tests/test_icalsync.py always points the guest at the row, which a real crash never does, so `test_a_crash_stuck_running_batch_defers_fitting_the_guest_window` passes today although the bug exists. This brief adds a `point` flag and makes that test unpointed.

Anchors, current code (`App/app/icalsync.py`, `_send_in_flight`, lines 373 to 399):
```python
    the register may already hold the old window. A crash-stuck ``running``
    batch is the same fact until ``recover_stale_submissions`` rewrites it.
    Guests already ``sent`` (including filed by hand) do not freeze the
```
and the last line of the function:
```python
    return _pointed_at_open_submission(reservation_id)
```
(that exact line, 4-space indent, occurs once in the file).

`_running_submission_covers_stay(reservation_id: int, newer_than: Optional[str] = None) -> bool` already exists (line ~420, from 1148); with no `newer_than` it considers all `running` rows of the stay's apartment whose JSON `guest_ids` overlap the stay's unsent, unarchived guests.

Test helpers in `App/tests/test_icalsync.py` (imports `json, time, datetime, timedelta, timezone, alerts, config, db, icalsync` already present): `_moved_stay(tmp_path, monkeypatch, *, submit_state="pending")` -> `(feed_id, reservation_id, guest_id)` (stay and guest 2099-01-10..12, feed reports 2099-02-10..12, apartment in `manual` mode); `_sync(feed_id)`; `_unclear_batch(reservation_id, guest_id, *, state="outcome_unknown")`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/icalsync.py | edit | `_send_in_flight` docstring and last line |
| App/tests/test_icalsync.py | edit | `_unclear_batch` flags, one test made realistic, 4 new tests |
| docs/tasks/1150-ical-move-unclaimed-running.md | status | `review` at the end |
| docs/tasks/1150-report.md | create | report |

No other file may change. No copy, no migration, no alert kind.

## 4. Steps

Commit after each step: `git add -A && git commit -qm "1150 step N"`. Work from `App/` for every command.

**Step 1. Test helper and tests first (they must fail before the fix).** All edits in `App/tests/test_icalsync.py`.

(a) Replace the whole `_unclear_batch` function. Old text (verbatim):
```python
def _unclear_batch(reservation_id, guest_id, *, state="outcome_unknown"):
    apartment_id = db.query_one(
        "SELECT apartment_id FROM reservation WHERE id = ?", (reservation_id,)
    )["apartment_id"]
    submission_id = db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "created_at": db.utcnow(),
            "finished_at": db.utcnow(),
            "mode": "auto",
            "state": state,
            "guest_ids": json.dumps([guest_id]),
            "error_text": "read timed out",
        },
    )
    db.update("guest", guest_id, {"submission_id": submission_id})
    return submission_id
```
New text:
```python
def _unclear_batch(
    reservation_id, guest_id, *, state="outcome_unknown", point=True, hours_old=0
):
    apartment_id = db.query_one(
        "SELECT apartment_id FROM reservation WHERE id = ?", (reservation_id,)
    )["apartment_id"]
    submission_id = db.insert(
        "submission",
        {
            "apartment_id": apartment_id,
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=hours_old))
            .replace(microsecond=0)
            .isoformat(),
            "finished_at": db.utcnow(),
            "mode": "auto",
            "state": state,
            "guest_ids": json.dumps([guest_id]),
            "error_text": "read timed out",
        },
    )
    if point:
        db.update("guest", guest_id, {"submission_id": submission_id})
    return submission_id
```

(b) Replace the body of `test_a_crash_stuck_running_batch_defers_fitting_the_guest_window`. Old text (verbatim, from its docstring line to the end of the function):
```python
    """A ``running`` row with no live claim is the same fact as outcome_unknown."""
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    _unclear_batch(reservation_id, guest_id, state="running")

    _sync(feed_id)
    guest = db.query_one("SELECT stay_from, stay_to FROM guest WHERE id = ?", (guest_id,))
    stay = db.query_one(
        "SELECT date_from, date_to FROM reservation WHERE id = ?", (reservation_id,)
    )
    assert (guest["stay_from"], guest["stay_to"]) == ("2099-01-10", "2099-01-12")
    assert (stay["date_from"], stay["date_to"]) == ("2099-01-10", "2099-01-12")
```
New text:
```python
    """A ``running`` row with no live claim is the same fact as outcome_unknown.

    A crash leaves the guest unpointed (only ``outcome_unknown`` is pointed at),
    so the batch is found through ``submission.guest_ids`` (K-F22).
    """
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    _unclear_batch(reservation_id, guest_id, state="running", point=False)

    _sync(feed_id)
    guest = db.query_one("SELECT stay_from, stay_to FROM guest WHERE id = ?", (guest_id,))
    stay = db.query_one(
        "SELECT date_from, date_to FROM reservation WHERE id = ?", (reservation_id,)
    )
    assert (guest["stay_from"], guest["stay_to"]) == ("2099-01-10", "2099-01-12")
    assert (stay["date_from"], stay["date_to"]) == ("2099-01-10", "2099-01-12")
    feed = db.query_one("SELECT body_sha256 FROM ical_feed WHERE id = ?", (feed_id,))
    assert not feed["body_sha256"]
```

(c) Insert these tests directly above the line `def test_a_hand_filed_guest_does_not_freeze_the_booking_dates(` (two blank lines between functions):
```python
def _stay_dates(reservation_id):
    row = db.query_one(
        "SELECT date_from, date_to FROM reservation WHERE id = ?", (reservation_id,)
    )
    return (row["date_from"], row["date_to"])


def test_a_date_move_waits_for_a_crash_stuck_running_batch_then_lands(monkeypatch, tmp_path):
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    submission_id = _unclear_batch(reservation_id, guest_id, state="running", point=False)

    _sync(feed_id)
    assert _stay_dates(reservation_id) == ("2099-01-10", "2099-01-12")

    # The batch is resolved (recovered and settled): the next poll applies the move.
    db.update("submission", submission_id, {"state": "ok"})
    _sync(feed_id)
    assert _stay_dates(reservation_id) == ("2099-02-10", "2099-02-12")


def test_an_old_running_batch_still_defers_the_date_move(monkeypatch, tmp_path):
    """No age limit for a move: an old row becomes outcome_unknown, which defers anyway."""
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    _unclear_batch(reservation_id, guest_id, state="running", point=False, hours_old=3)

    _sync(feed_id)

    assert _stay_dates(reservation_id) == ("2099-01-10", "2099-01-12")
    assert alerts.open_alert(f"moved_after_report:{reservation_id}") is None


def test_a_running_batch_of_another_guest_does_not_hold_the_date_move(monkeypatch, tmp_path):
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    submission_id = _unclear_batch(reservation_id, guest_id, state="running", point=False)
    db.update("submission", submission_id, {"guest_ids": json.dumps([guest_id + 1000])})

    _sync(feed_id)

    assert _stay_dates(reservation_id) == ("2099-02-10", "2099-02-12")


def test_a_running_batch_listing_only_a_sent_guest_does_not_hold_the_date_move(
    monkeypatch, tmp_path
):
    feed_id, reservation_id, guest_id = _moved_stay(
        tmp_path, monkeypatch, submit_state="sent"
    )
    _unclear_batch(reservation_id, guest_id, state="running", point=False)

    _sync(feed_id)

    assert _stay_dates(reservation_id) == ("2099-02-10", "2099-02-12")
```
Command: `.venv/bin/python -m pytest tests/test_icalsync.py -q --tb=line -k "running or crash_stuck" 2>&1 | tail -30`. Expected (fix not yet applied): `3 failed, 5 passed`; the failures are `test_a_crash_stuck_running_batch_defers_fitting_the_guest_window`, `test_a_date_move_waits_for_a_crash_stuck_running_batch_then_lands` and `test_an_old_running_batch_still_defers_the_date_move`.

**Step 2. The fix in icalsync.py.**
(a) In the `_send_in_flight` docstring replace
```
    the register may already hold the old window. A crash-stuck ``running``
    batch is the same fact until ``recover_stale_submissions`` rewrites it.
```
with
```
    the register may already hold the old window. A crash-stuck ``running``
    batch is the same fact until ``recover_stale_submissions`` rewrites it
    (that pass has no age test, only a stale claim). No guest points at a
    ``running`` batch, only at ``outcome_unknown``, so ``submission.guest_ids``
    is the only link to it and is read here, with no age limit: a move is
    deferred until the batch is resolved, never applied over it.
```
(b) Replace the last line of the function, `    return _pointed_at_open_submission(reservation_id)`, with:
```python
    return _pointed_at_open_submission(reservation_id) or _running_submission_covers_stay(
        reservation_id
    )
```
Command: `.venv/bin/python -m pytest tests/test_icalsync.py -q --tb=short 2>&1 | tail -30`. Expected: `68 passed`.

**Step 3. Revert bites.** Commit step 2 first so `git checkout` restores it.
(a) With Edit, replace in `_send_in_flight` the three lines of step 2(b) with the single line `    return _pointed_at_open_submission(reservation_id)`. Run `.venv/bin/python -m pytest tests/test_icalsync.py -q --tb=line -k "running or crash_stuck" 2>&1 | tail -30`. Expected: `3 failed, 5 passed` (the same three as step 1). Then `git checkout app/icalsync.py` and rerun: `8 passed`.
(b) With Edit, replace `_running_submission_covers_stay(\n        reservation_id\n    )` (inside `_send_in_flight` only, the 3 lines after `or `) with `bool(\n        db.query_one("SELECT 1 AS n FROM submission WHERE state = 'running' LIMIT 1")\n    )`. Run the same pytest. Expected: `2 failed, 6 passed`: `test_a_running_batch_of_another_guest_does_not_hold_the_date_move` and `test_a_running_batch_listing_only_a_sent_guest_does_not_hold_the_date_move`. Then `git checkout app/icalsync.py` and rerun: `8 passed`.

**Step 4. Area run, lint.**
`.venv/bin/ruff check app tests --select E9,F63,F7,F82,F401,F841 2>&1 | tail -30`. Expected: `All checks passed!`.
`.venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_stale_submission.py tests/test_no_em_dashes.py -q --tb=short -x 2>&1 | tail -30`. Expected: `97 passed`, 0 skipped. (No copy is added, so the host-copy tests are not needed.)
Then from the repo root: `python3 scripts/context_lint.py | tail -3`. Expected: `context lint: OK` (a WARN about status.md is for the orchestrator).

## 5. Do not touch

`App/app/reporting.py`, `claim.py`, `_update_reservation_unless_claimed`, `_running_defers_cancel`, `RUNNING_CANCEL_DEFER_SECONDS`, `_pointed_at_open_submission`, any cancel code, `go/`, copy files, migrations, docs other than this brief and its report. Hard rules: 1 (filing correctness first), 4 (no dependency), 5 (SQL through `db`).

## 6. Commands

Those in each step. Test-map row: Calendar, iCal feeds (`test_icalsync.py`, `test_ical_skip_unchanged.py`) plus `test_stale_submission.py`. No full suite.

## 7. Acceptance

- [ ] `_send_in_flight` returns True for a `running` row listing an unsent guest of the stay, of any age, with the guest unpointed and no claim.
- [ ] 4 new tests and the changed crash-stuck test pass; bite (a) fails 3 and bite (b) fails 2, each then passes after `git checkout`.
- [ ] Docstring no longer claims the `running` case is covered by the pointer.
- [ ] ruff clean; area run green with 0 skipped; lint OK; only §3 files changed.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report as `blocked`);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear.

## 9. Report

Write `docs/tasks/1150-report.md` (600 tokens at most) and set `Status: review`: files changed, each command with the last 5 lines, §7 ticked, both bite results, deviations, questions, owner steps left (push the branch; open the PR as a draft and keep it until 1150b is ready).

## Risk list (for the reviewer)

The `_send_in_flight` tail (no cutoff on purpose: see §2 decision; the owner may still prefer the 30-minute bound plus an alert, which needs a new alert kind and copy); `_running_submission_covers_stay` JSON overlap (reused unchanged from 1148); the test helper change (`point=True` default keeps every old caller identical).

## Owner steps

1. Nothing before review. After 1150b is also green, merge both PRs with `scripts/merge-pr-on-green.sh`.
