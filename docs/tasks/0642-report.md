# 0642 report

Status: review. Not pushed (the orchestrator said do not push); no PR opened.

## Commands (last lines)
- `gofmt -l .` and `go vet ./...` (go/): clean, no output.
- `go test ./internal/ubyport/ ./internal/mail/ -count=1 -v` with UBYHOST_TEST_DATABASE_URL set: 61 `--- PASS`, 0 FAIL, 0 SKIP; `ok ubyport 24.841s`, `ok mail 0.004s`.
- `.venv/bin/python scripts/mail_golden.py`: `golden files written: 6 + 2 cases`.
- `python3 scripts/context_lint.py`: `context lint: OK` (plus an orchestrator WARN about status.md, not for this brief).

## Files changed (git diff --stat origin/main)
- go/internal/ubyport/notify.go: refactor onto `QueuePush` and `EnqueueMail`; existing tests pass unchanged.
- go/internal/ubyport/cancelled_notify.go and _test.go (new): queue functions and DB tests.
- go/internal/mail/cancelled_with_guests.go and _test.go (new): builder and golden test.
- App/scripts/mail_golden.py; App/tests/golden/mail/cancelled_cases.json and 6 cancelled_with_guests_* golden files (new).
- docs/tasks/0642-report.md, and the brief Status line set to review.

## Differences from Python
1. Push params: Python stores `property` then `date`. `pyJSONParams` sorts keys, so Go stores `date` then `property`. Same values; the sender reads by name. Exact order needs an ordered params type, which the fixed signature does not allow.
2. `BuildCancelledWithGuests` takes `publicBaseURL` as well (the logo needs it, as in BuildSubmissionProblem). The brief signature did not have it.
3. The HTML shell is copied into cancelled_with_guests.go, because submission_problem.go is not in section 3. Sharing it later is a small refactor.
4. The footer support line is fixed to support@ubyhost.com. Python reads UBYHOST_OPERATOR_EMAIL; Go does not.
5. `_day` parses date-only values. Python's fromisoformat also takes datetimes; the DB date column gives date-only.

## Owner steps left
None for this slice. Nothing calls the new functions yet.

## Questions
Items 1 and 2 above: accept the sorted key order, and accept the extra publicBaseURL parameter?
