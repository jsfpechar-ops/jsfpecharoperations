# 1150 report: iCal date move over a crash-stuck `running` filing (K-F22)

Status: review

## Files changed

- `App/app/icalsync.py`: `_send_in_flight` docstring corrected; last line now also returns `_running_submission_covers_stay(reservation_id)` (no age cutoff).
- `App/tests/test_icalsync.py`: `_unclear_batch` gains `point` and `hours_old` (default keeps old callers identical); `test_a_crash_stuck_running_batch_defers_fitting_the_guest_window` made unpointed and checks `ical_feed.body_sha256` is empty; new `_stay_dates` helper and 4 new tests.
- `docs/tasks/1150-ical-move-unclaimed-running.md`: Status set to `review`.
- `docs/tasks/1150-report.md`: this report.

## Commands (last lines)

- Step 1, `pytest tests/test_icalsync.py -k "running or crash_stuck"` (before fix): `3 failed, 5 passed, 60 deselected in 1.84s`
- Step 2, `pytest tests/test_icalsync.py`: `68 passed in 7.58s`
- Step 4, `ruff check app tests --select E9,F63,F7,F82,F401,F841`: `All checks passed!`
- Step 4, area run (`test_icalsync`, `test_ical_skip_unchanged`, `test_stale_submission`, `test_no_em_dashes`) with `-rs`: `97 passed in 10.16s`, no skip lines.
- Step 4, `python3 scripts/context_lint.py`: `context lint: OK` (WARN about status.md is for the orchestrator, as the brief says).

## Revert bites

- (a) Tail of `_send_in_flight` reverted to `_pointed_at_open_submission` only. FAIL: `3 failed, 5 passed`. Restored with `git checkout`: PASS `8 passed`.
- (b) Reservation-scoped check replaced by global `SELECT 1 ... state = 'running'`. FAIL: `2 failed, 6 passed`
  (`test_a_running_batch_of_another_guest_does_not_hold_the_date_move`, `test_a_running_batch_listing_only_a_sent_guest_does_not_hold_the_date_move`). Restored: PASS `8 passed`.

## Acceptance (section 7)

- [x] `_send_in_flight` returns True for a `running` row listing an unsent guest of the stay, any age, unpointed, no claim.
- [x] 4 new tests and the changed crash-stuck test pass; bite (a) fails 3, bite (b) fails 2, each passes after `git checkout`.
- [x] Docstring no longer claims the `running` case is covered by the pointer.
- [x] ruff clean; area run green, 0 skipped; lint OK; only section 3 files changed.

## Deviations

- The step scripts (edit helpers) were written to `/home/user/scratchpad_1150_step1.py` and `/home/user/scratchpad_1150_step2.py`, outside the repo and outside the scratchpad directory. Not committed.
- No screenshots: no UI change.

## Questions

- None.

## Owner steps left

1. Push `task/1150-ical-move-running`.
2. Open the PR as a draft and keep it draft until 1150b is also ready, then merge both with `scripts/merge-pr-on-green.sh`.
