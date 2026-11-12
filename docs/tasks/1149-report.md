# 1149 report

Status: review

## 1. Files changed

- App/app/door_codes.py: transition ISSUED to PENDING; helper `_reissue_lost_pin`; call in the lost-race branch of `_revoke_one`.
- go/internal/statemachine/tables.go: transition mirrored.
- App/tests/test_sm_door_code_state.py: PINNED entry for `_reissue_lost_pin`.
- App/tests/test_door_code_lost_pin.py: new, 7 tests.
- docs/tasks/1149-door-revoke-lost-race-recovery.md: Status set to review.
- docs/tasks/1149-report.md: this report.

## 2. Commands (last lines)

- Step 2 and 3 import: no output (exit 0).
- Step 4 `grep -c _reissue_lost_pin`: `3`.
- Step 5 `go test ./internal/statemachine/...`: `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/statemachine`.
- Step 6 state and parity tests: `25 passed in 2.29s`.
- Step 7 lost-pin and cancel-guard tests: `19 passed in 0.73s`.
- Step 9 revert-bite (a) no re-issue: `3 failed, 4 passed`. Failed: lost_race_with_a_live_stay, operator_pause, failed_reissue.
- Step 9 revert-bite (b) id guard removed: `1 failed, 6 passed`. Failed: a_date_move_that_won_is_left_alone.
- Step 9 revert-bite (c) live-stay guard removed: `1 failed, 6 passed`. Failed: a_stay_cancelled_again_is_not_reissued.
- Step 9 revert-bite (d) no immediate issue: `1 failed, 6 passed`. Failed: lost_race_with_a_live_stay.
- Step 9 tree after the four runs: clean.
- Step 10 door-codes row: `280 passed, 2 skipped in 10.56s`. The 2 skips are the playwright browser tests (allowed).
- Step 11 Postgres (ubytest): `19 passed in 5.53s`.
- Step 12 `scripts/context_lint.py`: `context lint: OK`. It also printed a WARN that App/ commits came after the last status.md update. Left for the orchestrator.

## 3. Section 7 acceptance

- [x] test_door_code_lost_pin.py: 7 tests; test_door_code_cancel_guard.py unchanged and green.
- [x] All four revert-bite runs failed as listed; tree clean afterwards.
- [x] test_sm_door_code_state.py and test_sm_go_parity.py pass; go statemachine tests ok.
- [x] Door-codes row passes (2 playwright skips only).
- [x] Lint OK.

## 4. Deviations

- Step 1: the worktree was already on task/1149-door-revoke-lost-race (the owner's instruction), so `git switch -c` was not run. The base commit was the brief commit d42a7500. The step's expected branch name did not match the current branch, and this was not a stop condition.
- Step 2 first attempt: a combined command stalled in the background and did not apply the edit. Rerun applied the same edit once. No content change.
- Commits: steps 2 to 6 each committed as `1149 step k`. Steps 7 and 8 were committed together as `1149: re-issue the door code when a revoke loses its race` with the attribution lines, because the brief's step 8 commit covers the test file.
- Brief Step 8 says `git diff --stat HEAD~1`; this shows only the test file because HEAD~1 is the step 6 commit. Full diff from d42a7500 is in the commit list.
- No PR opened and no push, as instructed by the owner.

## 5. Questions

None.

## 6. Owner steps left

1. Open the PR when CI is green and merge with `scripts/merge-pr-on-green.sh`.
2. Decide 1149b (S8, S9 timed-out or crashed delete leaves a dead PIN). Say "do 1149b" or leave it as a known issue.
