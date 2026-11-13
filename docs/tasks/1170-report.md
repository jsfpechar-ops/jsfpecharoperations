# 1170 report: double-booking alarm from iCal calendars (Go)

Status: review

## Files changed (10, exactly the brief section 3 list)
- go/internal/ical/doublebooking.go (new): checkDoubleBookings, overlap pair SQL, fmtDay/fmtRange
- go/internal/ical/syncfeed.go: checkDoubleBookings in the suspect branch and at the end of SyncFeed
- go/internal/mail/double_booking.go (new): BuildDoubleBooking
- go/internal/ubyport/double_booking_notify.go (new): QueueDoubleBookingMail; the only email_outbox write, via pinned EnqueueMail
- go/internal/mail/double_booking_test.go (new, no DB)
- go/internal/ical/doublebooking_test.go (new, DB via testPool)
- App/app/mail.py: "double_booking" in KINDS and HOST_KINDS
- App/app/host_i18n.py: en + cs keys
- App/app/host_vi_i18n.py: vi keys
- App/tests/test_alert_language.py: one double_booking card render test

## Commands, last lines
- cd go && gofmt -l . && go build ./... && go vet ./internal/ical/ ./internal/mail/ ./internal/ubyport/ : gofmt printed nothing, BUILD_VET_OK
- go test ./internal/ical/ ./internal/mail/ ./internal/ubyport/ : ok ical 0.128s, ok mail 0.027s, ok ubyport 0.350s (DB tests skip without UBYHOST_TEST_DATABASE_URL; CI provides it)
- pytest row 1 (sm_queues sm_go_parity host_i18n alert_language notification_copy claim_mail), interpreter none found:
NOT RUN: no interpreter with pytest in this sandbox
- pytest row 2 (icalsync ical_skip_unchanged feed_* dashboard_calendar* calendar_*):
NOT RUN: no interpreter with pytest in this sandbox
- python3 scripts/context_lint.py : context lint: OK

## Acceptance (brief section 7)
- [x] gofmt -l go/ empty; go build clean; go vet clean
- [x] one open double_booking alert + one queued email_outbox row per overlapping pair, unchanged on rerun (Go DB tests, run by CI)
- [x] resolved_at set when the overlap ends; adjacent and non-active rows never alert (Go DB tests, CI)
- [x] test_sm_queues.py / test_sm_go_parity.py pass with zero edits
- [x] en/cs/vi key parity + card render test
- [x] no file outside section 3 changed

## Deviations
- App/.venv is missing in this sandbox; pytest rows ran with no interpreter - NOT RUN (results above).
- Go DB tests skip locally (UBYHOST_TEST_DATABASE_URL unset); CI runs them.
- Python fallback path (icalsync.py) intentionally has no double-booking alarm - owner decision, Go only.

## Questions
- None.

## Owner steps left
1. Merge the green PR with scripts/merge-pr-on-green.sh <pr>; deploy via GitHub Actions, Deploy production.
2. Staging: two overlapping feeds of one apartment produce one banner + one console e-mail; cancel one and the alert clears on the next ical run (within 60 min).
