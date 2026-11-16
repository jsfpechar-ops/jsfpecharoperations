# A3 report

Status: review (draft PR, not merged)

## Part 1 (merged, PR 1060)
Setup alert escalates to critical `pending` when police settings are invalid and a reportable guest waits; backlog sends in one sweep (batches of 32).

## Part 2 (branch feat/ubyport-filing-stalled)
- `go/internal/calendar/filing_stalled.go`: `StalledProperties`, `RunFilingStalled`. Critical `filing_stalled` alert 3 h after the automatic send cap (deadline minus 6 h); resolved once filed; one host and one operator mail per property per Prague day. Titles count-free, count in detail.
- `go/internal/mail/filing_stalled.go`: `BuildFilingStalled` (en only).
- `go/internal/calendar/deadlines_job.go`: runs the check; a stalled property or a failed check fails the filing heartbeat.
- `App/app/alerts.py`, `go/internal/hostweb/layout/alerts.go`: action for `filing_stalled`. `App/app/mail.py`: two mail kinds (host and operator).
- `App/tests/test_claim_mail.py`: mail kind pin extended; the dead-kind scan now also reads Go sources (the two kinds are queued only by Go).
- `docs/context/test-map.md`: Go row; compacted to stay under the token cap (`scripts/context_lint.py` OK).

## Tests
- Go, Postgres 16 (port 5433): `go test ./internal/calendar/... ./internal/ubyport/... ./internal/mail/... ./internal/hostweb/...` all ok.
- Python: `test_claim_mail, test_mail_failed_alert, test_alert_language, test_filing_watchdog, test_go_host_i18n`: 232 passed, 0 skipped.

## Review of PR 1062 (93a5d15), what changed
- A failed stalled check now returns an error after the `/fail` ping, so the job queue records failure and does not resolve `job_failed:deadlines` (deadlines_job.go; tests for the error and zero paths).
- The host sees the count: `notification.filing_stalled.detail` now has `%(count)s` in en, cs and vi; the alert params carry `count`; the Go catalog is regenerated. Python test renders the detail with the number in all three languages.
- `Mailed` counts only newly queued host mails (a repeat on the same day counts 0).
- A failed watchdog returns before the stalled check (documented in deadlines_job.go). No ping is sent then, so the external monitor alerts.
- Setup-critical properties are mailed before the cap by design (brief A3 section 3: "both are mailed before the cap" while the sweep holds apartment_setup critical). One host and one operator mail per property per day. Kept as the brief says; a future-stay host with an incomplete setup gets these mails daily until setup is finished. Owner may narrow this later.
- test-map.md restored the dropped wording and states that the Go DB tests skip without `UBYHOST_TEST_DATABASE_URL`.

## Left
- Brief §14/§18 scenario "two mails on the first day" asserted only as "no second queue on the same day" (first run was observed to queue exactly host + operator).
- Brief §17 cause-by-cause DB cases (auth, failed, manual, setup-before-cap) not yet written; only the pure cause order test.
