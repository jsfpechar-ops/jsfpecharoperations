# 1154b report: iCal date move over a crash-stuck running filing (K-F22), Go

Status: review
Branch: task/1154b-ical-move-running-go (base a176c3ee, 1154 merged)

## Files changed

- go/internal/ical/reconcile.go: `sendInFlight` comment and tail. Now falls through to `runningSubmissionCoversStay(ctx, pool, reservationID, "")` (no age limit) after `pointedAtOpenSubmission`.
- go/internal/ical/reconcile_test.go: 1 test appended (`TestSendInFlightFindsACrashStuckRunningBatchByGuestIDs`).
- go/internal/ical/syncfeed_test.go: 2 tests appended (`TestSyncFeedDateMoveWaitsForCrashStuckRunningBatchThenLands`, `TestSyncFeedOldRunningBatchStillDefersTheDateMove`).
- docs/context/known-issues.md: K-F22 line replaced with the closed line.
- docs/tasks/1154b-ical-move-unclaimed-running-go.md: Status set to `review`.
- docs/tasks/1154b-report.md: this file.

## Commands (last 5 lines)

- Step 1, new tests before fix: `--- FAIL` for all 3 new tests, `FAIL`, `FAIL ... ical 1.052s`, `FAIL`.
- Step 2, full package after fix: `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical 15.646s`. gofmt and vet silent.
- Step 4, SKIP count: `0`. Full package: `ok ... ical 21.508s`. gofmt and vet silent.
- Step 4, `grep -c 'K-F22 closed'`: `1`. `python3 scripts/context_lint.py`: `context lint: OK`, preceded by a WARN that status.md is behind App/ commits (orchestrator's update, not changed here).

## Bites

- (a) `return false, nil` in place of the tail: FAIL, three `--- FAIL` (`TestSendInFlightFindsACrashStuckRunningBatchByGuestIDs`, `TestSyncFeedDateMoveWaitsForCrashStuckRunningBatchThenLands`, `TestSyncFeedOldRunningBatchStillDefersTheDateMove`). Restored: three PASS plus `TestSendInFlight` PASS, `ok`.
- (b) `exists(... state = 'running' LIMIT 1)` in place of the tail: FAIL, only `TestSendInFlightFindsACrashStuckRunningBatchByGuestIDs` fails; the two sync tests PASS, as the brief predicted. Restored: all PASS, `ok`.

## Section 7 acceptance

- [x] `sendInFlight` true for an unpointed running row listing an unsent guest of the stay, any age; false for another stay, a sent-only guest, or a settled row.
- [x] 3 new tests pass against Postgres, 0 SKIP; bite (a) fails 3, bite (b) fails 1, each then passes.
- [x] vet and gofmt silent; K-F22 closed; lint OK; only the section 3 files changed.

## Deviations

- Bite (a) and (b) were applied with `sed` and `Edit` respectively, with `git checkout` restore after each. Result is identical to the brief.
- No PR opened and nothing pushed, as instructed.

## Questions

None.

## Owner steps left

1. Push the branch `task/1154b-ical-move-running-go`.
2. Open a draft PR for 1154b.
3. Merge 1154 and 1154b with `scripts/merge-pr-on-green.sh`, in that order.
