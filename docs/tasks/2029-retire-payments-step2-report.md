# 2029 step 2 report

Status: review

## Files changed
- `go/cmd/ubyhost-web/register_jobs.go` — skip `stripe_sweep` handler when `PaymentsRetired`; log `job skipped: payments retired`
- `go/cmd/ubyhost-web/register_scheduler_test.go` — `TestJobsStripeSweepSkipsWhenPaymentsRetired`
- `App/app/scheduler.py` — `_job_stripe_sweep` logs and returns when `PAYMENTS_RETIRED` (schedule still gated by `PAYMENTS_HIDDEN` from step 1)
- `docs/context/job-ownership.md` — `stripe_sweep` row notes retired skip; `billing_snapshot` unchanged

## Commands (last 5 lines)
Go: `ok github.com/.../go/cmd/ubyhost-web 0.090s`

## §7 (step 2 scope)
- [x] `stripe_sweep` skipped when `UBYHOST_PAYMENTS_RETIRED=1` (Go handler + Python job)
- [x] `billing_snapshot` unchanged
- [x] Skip logs one line, no error
- [x] No `config.py` edit in this step

## Deviations
Go `expire_requests` mail step (`register_job_mail.go`) not edited — not in step 2 file list; still runs when only Go serves mail and RETIRED=1. Go scheduler still enqueues `stripe_sweep` cron rows; handler no-ops with log (brief “do not schedule” would need `scheduler.go` or `register_scheduler.go`, not listed).

## Questions
None.

## Owner
Merge after step 1 PR; stack step 2 PR base `cursor/retire-payments-step1-47ba`.