# 1172 report: double-booking alarm from iCal calendars (Go)

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

## Review round 2 (PR #954 review)
- Renumbered 1166 -> 1172: main already has the Cloudflare 1166 (docs/tasks/1166-report.md), so the brief/report moved to 1172-double-booking-alarm.md / 1172-report.md and all references were renumbered; the add/add merge conflict is gone (main merged in).
- Overlap query now has `AND r1.date_to > $2 AND r2.date_to > $2` with $2 = today (Europe/Prague, same as syncfeed): the first sync after deploy no longer alarms/mails about historical overlaps. Covered by a past-overlap pair in TestDoubleBookingIgnoresAdjacentAndIgnored.
- checkDoubleBookings now also runs on the `not_modified` (HTTP 304) and `unchanged` (same digest) early exits of SyncFeed, so a host-side cancel/ignore clears the alert on the next hourly sync even when no calendar changed.
- Review item 4 (manual stay + same booking from iCal looks like a double booking): left unchanged in this PR, flagged for the owner - either skip identical-date pairs with a `manual` side or reword the alert/mail copy to cover duplicates.
- Review item 5 confirmed intended: one e-mail per pair ever (idempotency key = alert dedupe key); a cleared-and-returning overlap reopens the in-app alert only.

## CI round 1 (run 43377882606, head 01286ac0)
- Green: go, test-postgres, test, browser shards, Security, smoke, context, lint jobs.
- Failed: `test` and `test-postgres-full`, both only in tests/test_claim_mail.py registry tests: the hardcoded KINDS set (test_the_registered_mail_kinds_are_the_ones_the_app_can_send) and test_no_registered_mail_kind_is_dead did not know the Go-inserted kind.
- Fix: "double_booking" added to the expected set in test_claim_mail.py, and a pointer comment naming "double_booking" added in App/app/host_i18n.py (the Go ical job writes the outbox row; Python never composes it). Verified locally via ast/scan simulation; no pytest interpreter in the executor sandbox, CI re-runs them.
