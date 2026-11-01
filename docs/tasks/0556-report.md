# 0556 report: Go collect_sendable

Status: blocked

## Files
- `go/internal/ubyport/collect.go` (new): LoadApartment, CollectOptions, CollectSendable, DueForAutomaticSend, ReportingDeadline, decrypt helper.
- `go/internal/ubyport/collect_test.go` (new): branch table, decrypt and order, bad token, ReportingDeadline table.
- `docs/tasks/0556-report.md` (this file).

## Commands
- `gofmt -l ./internal/ubyport/` empty; `go vet ./internal/ubyport/` clean.
- `go test ./internal/ubyport/ -run 'Collect|ReportingDeadline' -count=1 -v`: TestReportingDeadline PASS. All DB tests FAIL at connect: `admin connect failed`.
- Cause: `psql` with the brief URL (`postgres://postgres:ubyhost@127.0.0.1/ubyhost_test`) and with `/postgres` both return `password authentication failed for user "postgres"`. Postgres is accepting connections on 5432. `UBYHOST_TEST_DATABASE_URL` is not set in the environment. I did not look for other credentials.
- Skip count: not measured; the DB tests need the URL to run. Must be 0 before merge.
- `python3 scripts/context_lint.py`: not run (not reached).

## Deviations from the brief
- No GuestMeta struct. Claim and batch fields are already in OutcomeGuest and BatchPair; the filter-only fields stay in an internal struct.
- ReportingDeadline returns a time in the Prague location. DueForAutomaticSend subtracts the 6 h margin as a duration. Europe's DST switch is never between 17:59 and 23:59, so this equals Python's wall-clock arithmetic.
- "Today" for GuestIsComplete is the Prague date of Now. Not verified against Python's validate_guest default.
- Stored-timestamp parsing accepts RFC 3339, naive, space-separated and date-only forms; naive reads as UTC.
- The demo check is the SQL predicate only (`COALESCE(source,'') != 'demo'`), as the brief says. demo.is_demo_stay was not read.
- The stale-signature warning log line is not ported.
- The brief's "blocked duplicate" case uses the sample text "duplicate record".

## Owner step
Give the executor a working `UBYHOST_TEST_DATABASE_URL`, then rerun:
`cd go && UBYHOST_TEST_DATABASE_URL=<url> go test ./internal/ubyport/ -count=1 -v 2>&1 | tail -30`
