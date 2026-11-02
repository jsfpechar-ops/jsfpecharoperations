# 0686 report

Status: review

Files: `go/internal/calendar/handler_test.go` (new), `go/internal/calendar/handler.go` (login gate, `active = 1`), `docs/tasks/0682-report.md` (0686 section), briefs 0682 and 0686 set to review (0685 left at todo: no 0685 report exists, and lint requires one for review).

Commands (local DB `ubyhost0686`, `UBYHOST_TEST_DATABASE_URL` set):
- `gofmt -l .` clean, `go vet ./...` clean.
- `go test ./internal/calendar/ ./cmd/... -count=1 -v`: all PASS, 0 SKIP. Last lines: `--- PASS: TestDashboardCalendarExactBytes`, `PASS`, `ok internal/calendar`.
- `python3 scripts/context_lint.py`: see the commit message.

Deviations: none found. Not covered: impersonation expiry, acceptance redirect, paused billing on POST.

Owner steps left: review and merge via `scripts/merge-pr-on-green.sh`.
