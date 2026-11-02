# 0553 report: Go G5d-3c mail and push queueing

Status: review

## Files changed
- `go/internal/ubyport/notify.go` (new): `ApartmentRef`, `StaysForSubmission`, `QueueSubmissionProblemMail`, `QueueFilingProblemPush`, plus small helpers.
- `go/internal/ubyport/notify_test.go` (new): six DB tests.
- `docs/tasks/0553-go-g5d3c-mail-push-queue.md` (Status set to review).
- `docs/tasks/0553-report.md` (this file).

## Commands (with UBYHOST_TEST_DATABASE_URL set, so the DB tests ran)
- `gofmt -l .` empty, `go vet ./...` clean.
- `go test ./internal/ubyport/ ./internal/mail/ -count=1 -v | grep -c -- '--- SKIP'` gives `0`.
- `go test ./internal/ubyport/ ./internal/mail/ -count=1` tail: `ok ...internal/ubyport 19.005s`, `ok ...internal/mail 0.004s`.
- `go test ./internal/ubyport/ -run Notify -count=1 -v` : 6 PASS (MailOffOrNoContact, MailRowPayloadAndIdempotency, MailTwoStaysHasNoReservation, MailAddressForms, Push, PushLongNameAndTwoStays).
- `python3 scripts/context_lint.py | tail -3`: see the lint line in the session report.

## Deviations
- Base: the brief says `main`; the branch is `origin/claude/project-thread-bhyvh5`, which already holds the brief. The diff check was against that branch, as the executor instructions say. `git diff --stat` lists `notify.go` only (tests and report are new, untracked until the commit).
- Mail language is fixed to `"en"`: the brief's signature has no `lang` argument. Python reads `HOST_MAIL_LANGUAGE`, which is `"en"`.
- Added `_ "time/tzdata"` to `notify.go`, so the Prague zone loads on a bare container. Standard library, no new dependency.
- `normaliseEmail` supports only the plain and `Name <addr>` forms (no `net/mail`), per the brief. Comments say so.
- The stays SQL is the Python SQL with `$n` placeholders in place of `?`, and `IN (...)` kept as in Python.
- Errors are static messages (no address, reason or key inside).
- Commits: step 1 is `0553 step 1`; the final commit uses the brief's message.

## Owner steps left
None for this brief. 0554 wires the functions into `SubmitBatch`.
