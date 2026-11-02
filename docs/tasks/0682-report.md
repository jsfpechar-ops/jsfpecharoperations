# 0682 report (executor, Haiku 5.5)
Status: blocked

## Files changed
- `go/internal/calendar/calendar.go` (new): pure helpers ported from dashboard_calendar.py: parse_dates, parse_range, visual hour, hour validity, display_at, tone, deadline_cell (given precomputed inputs).
- `go/internal/calendar/calendar_test.go` (new): unit tests for parse_range edges, visual hour, tone (all status x overdue x preview), deadline_cell (countdown, on time, late with floor and min 1, no filing time, not required).
- `docs/tasks/0682-go-dashboard-calendar.md` (brief copy, Status: blocked).
- `docs/tasks/0682-report.md` (this file).

## Commands (last lines)
- `cd go && gofmt -w internal/calendar && go vet ./internal/calendar/ && go test ./internal/calendar/ -count=1 | tail -30`: `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar 0.012s` (no DB tests, so 0 skipped in this package for now; DB tests not written).
- Toolchain note: go.mod asks for go 1.25.0; the local go 1.24.7 auto-downloaded go1.25.14 and worked.

## Steps ticked (brief section 4)
- Step 1 (package + route): NOT done. No `GET /dashboard/calendar` route, no events() query, no main.go registration.
- Step 2 (unit tests, no DB): partly done (parse_range, visual hour, tone, deadline_cell). Not done: deadline_cell inputs from reservation progress; urgency bucket (deadlines.urgency not ported).
- Step 3 (DB tests): NOT done.
- Step 4 (commit): commit made for the partial work; not the full message contract.

## Deviations
Done: partial step 2 (pure helpers and unit tests). Left: step 1 (events query, route, main.go, progress/expected/guest-identity logic, owner scoping via apartmentRows pattern), step 3 (DB tests and byte-exact fixture), section 7 acceptance.
Reason for stopping: the brief's scope (reporting.reservation_progress, guest_issues/_stay_dates, guest_filed_by_hand, guest_identity_verified, expected_guest_count, reservation_deadline_anchor, deadlines.urgency, demo.is_demo_stay, guest decryption with preload fallback, access.apartments/owner_id, plus the DB test harness) does not fit the 30-tool-call / 80k-token executor limit. Stopped at the checkpoint rather than guess.

## Known differences from Python (so far)
- `isoDate` accepts only ASCII digits; Python's `\d` regex also matches Unicode digits (and then fails in fromisoformat), so behaviour should match in practice.
- `hourOf` accepts nil, int, int64 and string (Atoi after trim). Python int() also accepts floats-as-ints and some other forms; not reproduced.
- `deadlineCell` takes `urgencyLevel`, `filedAt`, `due` as inputs; the Python `_filing_stamp`/`filed_at` (Prague local time via deadlines.local_now) and `reporting_deadline` are not ported here.
- `tone` takes the deadline level as a string; computing it (deadlines.urgency) is left to the caller.

## Questions
- Exports needed from `go/internal/ubyport` (e.g. `ReportingDeadline` is already exported; `reservationDeadlineAnchor`, `LoadGuests` scope/decrypt helpers are unexported) are not yet decided; the brief allows one-line exports. Confirm the next executor may export them.

## Owner steps left
- None yet. The next executor should continue from step 1 with the calendar events query and route, then step 3 DB tests. The local Postgres setup in brief section 6 is still needed.
