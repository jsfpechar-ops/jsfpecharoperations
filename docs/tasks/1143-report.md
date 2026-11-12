# 1143 report

Status: review
Branch: worktree-agent-afb4402b9074677fd | Base: 7b8ff2ae | Last code commit: 6a499d36

## Files changed (steps 1 to 6)

- App/app/icalsync.py: +50 / -2 (helper `_update_reservation_unless_claimed`, call-site change) (steps 1 and 2)
- App/tests/test_icalsync.py: +25 (regression test appended) (step 3)
- go/internal/ical/syncfeed.go: helper `updateReservationUnlessClaimed` (commit d87cea09, step 4), call site (c99d4129, step 5)
- go/internal/ical/syncfeed_test.go: +31, `TestUpdateReservationUnlessClaimed` (6a499d36, step 6)
- docs/tasks/1143-report.md, docs/tasks/1143-ical-date-move-respects-submission-claim.md (Status line only)

## Commands and last lines

- `cd go && UBYHOST_TEST_DATABASE_URL=... go test ./internal/ical/ -count=1`: `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical  5.909s`
- `go test ./internal/ical/ -count=1 -run TestUpdateReservationUnlessClaimed -v`: `--- PASS: TestUpdateReservationUnlessClaimed (0.34s)`, `ok`. Not skipped.
- `go test ./internal/ical/ -count=1 -run TestSyncFeedDatesInFlightKeepsDigest -v`: `--- PASS: TestSyncFeedDatesInFlightKeepsDigest (0.42s)`, `ok`. Not skipped.
- `go vet ./internal/ical/`: no output, exit 0. `go build` and `gofmt -l`: clean.
- `App/.venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py -q --tb=short -x -rs`: `60 passed in 5.61s`, 0 skipped.

## Acceptance (§7)

- [x] New Python test passes; the two Python files pass (60 passed, 0 skipped).
- [x] New Go test runs and passes (PASS, not SKIP).
- [x] `TestSyncFeedDatesInFlightKeepsDigest` runs and passes.
- [x] Python and Go date writes carry the live-claim condition in one UPDATE.
- [ ] `git diff --stat` lists only the four §3 code files: not verified. The branch diff vs 7b8ff2ae also contains docs/tasks files from earlier commits.

## Deviations

- Done: steps 1 to 6 of 1143 (cont-1 steps 1 to 6). Left: nothing in the brief. `context_lint.py` (1143 §6 command 3) not run, not in the cont-1 brief.

## Questions

- None blocking.

## Owner steps left

- Review the PR when opened by the owner. Merge only with `scripts/merge-pr-on-green.sh <PR number>`.
