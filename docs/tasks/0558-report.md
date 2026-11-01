# 0558 report: Go police sweep and job kind submit

Status: review

## Files
- New: go/internal/ubyport/sweep.go (SubmitForApartment, RetryOutcomeUnknownBatches, Sweep, NewSweepDeps, LoadCodebook, ClientFor, EndpointFor, ErrGuestUnreadable)
- New: go/internal/ubyport/sweep_test.go (4 database tests)
- Edit: go/cmd/ubyhost-web/main.go (imports, "submit" in goIntervals with 10 minutes, "submit" handler)
- Edit: go/internal/ubyport/collect.go (one line: decryptOrPlain returns guestUnreadable so errors.Is(err, ErrGuestUnreadable) works; message text unchanged)
- Edit: go/internal/validation/validation.go (IssuesToText appended; it was missing)

## Commands
- gofmt -l, go vet ./internal/ubyport/ ./cmd/..., go build ./...: clean
- `UBYHOST_TEST_DATABASE_URL=... go test ./internal/ubyport/ ./cmd/... -count=1 -v`
  last lines: `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport 24.098s`
  skips: 0. TestSweepDemoApartmentIsNoop, TestSweepIncompleteSetupAlertsAndSendsNothing, TestSweepBatchesSeventyGuestsInThrees, TestSweepContainsUnreadableGuestAndSkipsAuthAlert: PASS.
- python3 scripts/context_lint.py: see Deviations

## Deviations
- Beyond section 3: the collect.go one-line edit (brief section 2 allows a typed ErrGuestUnreadable).
- The job handler returns Submitted as its count. No heartbeat ping in Go; Python keeps it while the kind is off.
- goIntervals uses 10 (config default). Go does not read UBYHOST_SUBMIT_SWEEP_MINUTES.
- UBYHOST_UBYPORT_ENV set but empty is read as mock (Python would raise).
- Unknown UBYHOST_UBYPORT_ENV: SubmitForApartment returns an error before collecting (sweep_failed), instead of Python's ValueError inside submit_batch.
- Not covered by a test: claim release after a batch error, the retry resend itself, and the legal-entity demo check. The code has them (defer, markBatchRetried, isDemoApartment).
- Test fixture sweepFixtureApartment adds the valid UbyPort fields to notifyApartment.

## Questions
- None. No stop-and-ask condition was hit.

## Owner steps (not run)
1. Only when you decide to switch the kind on: set UBYHOST_GO_JOB_KINDS=submit and add submit to UBYHOST_JOB_QUEUE_KINDS in the server env, then restart. Until both are set the Go binary claims no submit job.
2. Keep the Python scheduler running submit until this is proven on staging.

## Diff stat (907ac19)
 docs/tasks/0558-go-police-sweep-job.md |  36 +++
 go/cmd/ubyhost-web/main.go             |  19 +-
 go/internal/ubyport/collect.go         |   3 +-
 go/internal/ubyport/sweep.go           | 562 +++++++++++++++++++++++++++++++++
 go/internal/ubyport/sweep_test.go      | 132 ++++++++
 go/internal/validation/validation.go   |   9 +
 6 files changed, 758 insertions(+), 3 deletions(-)
