# Plan: the `mail` job on Go (J4)

Status: approved with the full Go move (owner, 2026-11-13). Part of [go-full-move](go-full-move.md) §3 J4 and §7 "Plan and port mail job". `stay_fee_mail` is its own thread.

## 1. What the Python job does today

`App/app/scheduler.py:_job_mail`, every 5 minutes, runs seven steps in order. A step that raises is logged and the next step still runs; any failure marks the run failed (alert `job_failed`), a clean run pings `UBYHOST_HEARTBEAT_MAIL_URL`.

| # | Step | Python | What it writes |
|---|---|---|---|
| 1 | `expire_holds` | `claim.expire_holds` | `reservation_claim` provisional → unclaimed |
| 2 | `expire_requests` | `booking_checkout.expire_requests` | `site_booking` requested → expired, deletes its `booking_hold` |
| 3 | `drain` | `mail.drain(8)` | sends queued `email_outbox` rows (SES or console), back-off, `mail_failed` alert after 8 tries |
| 4 | `reminders` | `claim.sweep_reminders` | queues `reminder_guest` / `reminder_host`, raises and resolves `guest_incomplete_checkin`, then drains 8 more |
| 5 | `fee_updates` | `fee_update.sweep_fee_updates` | queues `completion_update` when the stay fee changed after the receipt |
| 6 | `lifecycle` | `lifecycle_mail.run_daily` | onboarding tips, once a day after 09:00 Prague, only with `UBYHOST_LIFECYCLE_MAIL=1` |
| 7 | `purge` | `mail.purge_old(14)` | deletes finished outbox rows and `console_mail_log` older than 14 days |

## 2. Go design

- Package owner: this thread owns `go/internal/mail/` (existing builders stay unchanged) and `go/internal/lifecyclemail/`. Reminders, fee updates, holds and requests live in a new `go/internal/mailjob/` so the shared `mail/` package stays a library.
- Sending: one stdlib SES v2 client (`POST /v2/email/outbound-emails`, SigV4 signed with `crypto/hmac`). No AWS SDK, so no new dependency. v2 `Simple` for plain and List-Unsubscribe mails, v2 `Raw` (MIME built with `mime/multipart`) when there are attachments. Python uses v1 for plain mails; the delivered message is the same, and v2 uses the same IAM action `ses:SendEmail`.
- Backends: `UBYHOST_MAIL_BACKEND` = `disabled` (nothing), `console` (row into `console_mail_log`, stored form only) or `ses` (production only, same checks as `mail.validate_mail_env`). Same env names as Python: `UBYHOST_MAIL_FROM`, `UBYHOST_SES_REGION`, `UBYHOST_AWS_ACCESS_KEY_ID`, `UBYHOST_AWS_SECRET_ACCESS_KEY`.
- Send-time markers, same as Python: `{{claim_secret}}` and `{{door_code}}` (Fernet via `go/internal/secure`), `{{guest_details}}` and `{{receipt_details}}` (rendered from the stay at send time). A marker that cannot be filled fails the row, it never goes out with the marker.
- Attachments: stay fee filing PDF (`stay_fee_filing.pdf_enc`, decrypt blob), platform invoice PDF (`platform_invoice.pdf_blob`, sha256 checked), QR PNG inline (`cid:stayfeeqr`). Both PDFs are stored bytes, so no PDF library is needed.
- Concurrency: the same claim as Python (`UPDATE ... SET state='sending' WHERE id=$1 AND state='queued'`), stale `sending` rows older than 10 minutes go back to `queued`. Python's `mail.send_now` (login links, from the web) keeps working while the job runs on Go, because both use that claim.
- Job: kind `mail`, interval 5, registered in `go/cmd/ubyhost-web/register_job_mail.go`. Steps run in the Python order with the same keep-going rule; heartbeat ping only after a clean run. `jobNames` already has `mail`.

## 3. Parity

Golden scripts write fixtures from Python with invented data; Go tests read them:
- `App/scripts/mail_drain_golden.py`: for fixture outbox rows, the delivered subject, text, HTML, headers and attachment list, and the SES v2 request body; plus back-off times and terminal alert.
- `App/scripts/mail_reminders_golden.py`, `mail_fee_update_golden.py`, `lifecycle_mail_golden.py`: the outbox rows (kind, key, to, subject, payload) and alert keys each step writes on a fixture database.
- `App/tests/test_go_mail_parity.py`: re-runs the golden scripts and fails when the committed fixtures differ.

## 4. Steps (one branch, one PR; task numbers 1230-1239)

| Task | Step | Files |
|---|---|---|
| 1230 | this plan | `docs/plans/go-mail-job.md` |
| 1231 | delivery: drain, deliver, back-off, SES v2 client, console, markers, attachments, purge | new files in `go/internal/mail/`, `App/scripts/mail_drain_golden.py` |
| 1232 | expire holds and booking requests | `go/internal/mailjob/` |
| 1233 | check-in reminders | `go/internal/mailjob/`, `App/scripts/mail_reminders_golden.py` |
| 1234 | fee update mails | `go/internal/mailjob/`, `App/scripts/mail_fee_update_golden.py` |
| 1235 | lifecycle tips | `go/internal/lifecyclemail/`, `App/scripts/lifecycle_mail_golden.py` |
| 1236 | job wiring and parity test | `go/cmd/ubyhost-web/register_job_mail.go`, `App/tests/test_go_mail_parity.py` |

## 5. Switch and rollback (owner)

1. On staging (console backend) add `mail` to `UBYHOST_GO_JOB_KINDS` in both the `worker` and `ubyhost-go` env; check with `docker inspect` that both have it and that `console_mail_log` gets rows.
2. Production: same, then watch `email_outbox` for a day (`sent_at` filled, no `mail_failed` alerts, SES message ids present).
3. Rollback: remove `mail` from both lists and `docker compose up -d`. Rows in flight go back to `queued` after 10 minutes and Python sends them.
4. Python `_job_mail` is removed in a later PR after a clean production week. `mail.send_now` and `mail.enqueue` stay in Python until the web pages that call them move.

## 6. Risks

- Double send: both runtimes running `mail` at once. The row claim makes that safe for drain; the reminder and fee steps use idempotency keys. Still, both env lists must change together.
- Guest data in mail bodies (`guest_details`, `receipt_details`): rendered at send time only, never stored decrypted, never logged.
- SES signing bugs show as failed sends, not wrong mail: the row retries and Python can take over by rollback.
