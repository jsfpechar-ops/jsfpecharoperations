# 1148b report: iCal cancel with a running or outcome_unknown filing (K-F20), Go

Status: review

## Files changed

- `go/internal/ical/reconcile.go`: import `encoding/json`; helpers `runningCancelDefer`, `pointedAtOpenSubmission`, `runningSubmissionCoversStay`, `runningDefersCancel`, `alertIfFilingInDoubt`; `sendInFlight` tail; `cancelExistingStay` call site.
- `go/internal/ical/syncfeed.go`: sweep call site.
- `go/internal/ical/syncfeed_test.go`: helper `seedSubmission` and 6 tests.
- `docs/context/known-issues.md`: K-F20 line replaced with the closed entry.
- `docs/tasks/1148b-ical-cancel-unclaimed-running-go.md`: Status `review`.
- `docs/tasks/1148b-report.md`: this file.

## Commands (last 5 lines)

- Step 1, `go build` and `gofmt -l`: silent.
- Steps 2 and 3, `go test ./internal/ical/ -count=1`: `ok ... 11.571s`.
- Step 4, six new tests, `-v`: six `--- PASS` lines, then `ok ... 3.634s`.
- Step 6, `gofmt -l` and `go vet`: silent. `grep -c SKIP`: `0`. Full package: `ok ... 18.250s`.
- Step 6, `python3 scripts/context_lint.py | tail -3`: `context lint: OK`. A WARN line about status.md (14 commits after the last status update) is for the orchestrator.

## Revert bites (§7 requires both to fail, then pass)

- (a) `alertIfFilingInDoubt` returns nil. FAIL: `UnconfirmedFiling` (event), `FreshRunningFilingDefersTheCancel`, `OldRunningFilingDoesNotHoldTheCancel`, `VanishedStayWithUnconfirmedFilingCancelsAndAlerts`. PASS: `SettledFiling`, `VanishedStayWithFreshRunningFilingIsDeferred`. Restored with `git checkout`: all 6 PASS, `ok`.
- (b) `runningDefersCancel` returns `false, nil`. FAIL: `FreshRunningFilingDefersTheCancel`, `VanishedStayWithFreshRunningFilingIsDeferred`. Restored: all 6 PASS, `ok`.

## Acceptance (§7)

- [x] Event and sweep both go through `runningDefersCancel` and `alertIfFilingInDoubt`. `sendInFlight` keeps its result (`pointedAtOpenSubmission` has the same query).
- [x] 6 new tests pass against Postgres, 0 SKIP. Both bites fail, then pass.
- [x] vet and gofmt silent. K-F20 closed. Lint OK. Only §3 files changed.

## Deviations

- Steps 2 and 3 went into one commit, `1148b step 2`, because both splices were applied before committing. Step 3 has no commit of its own. Tree content is as the brief specifies.
- The brief's step 4 filter omits the two `Vanished` tests. I added `|VanishedStayWith` so all six ran.
- Edits were applied with a Python splice that asserts the anchor lines first, not with the Edit tool. Text is as the brief gives it.
- Bite (a) also fails the `VanishedStayWithUnconfirmed` test, which the brief does not list. Its expectation is the same kind of alert check, so this is consistent.
- The brief header names base commit `21c87fc6`. I worked on the branch HEAD, `5cbf2d2d` (1148 merged), as the task instructions say.

## Questions

None.

## Owner steps left

1. Push the branch `task/1148b-ical-cancel-running-go`.
2. Open a draft PR.
3. Merge 1148 and 1148b with `scripts/merge-pr-on-green.sh`.
