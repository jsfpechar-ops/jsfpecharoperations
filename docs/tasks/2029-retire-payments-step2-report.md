# 2029 step 2 report

Status: review

## Files changed
- `go/cmd/ubyhost-web/register_jobs.go` — skip `stripe_sweep` handler when `PaymentsRetired`; log `job skipped: payments retired`
- `go/internal/scheduler/scheduler.go` — omit `stripe_sweep` from `Plan` when `PaymentsHidden` (includes retired)
- `go/cmd/ubyhost-web/register_job_mail.go` — omit `expire_requests` mail step when hidden/retired (Python parity)
- `go/cmd/ubyhost-web/register_scheduler_test.go` — `TestSchedulerOmitsStripeSweepWhenPaymentsRetired`, `TestJobsStripeSweepSkipsWhenPaymentsRetired`
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
None after follow-up: scheduler `Plan` and mail `expire_requests` gated.

## PR
https://github.com/jsfpechar-ops/jsfpecharoperations/pull/1271 (draft, base `cursor/retire-payments-step1-47ba`). Not #1267 (that is step 3).

## Questions
None.

## Owner
Merge after step 1 PR; stack step 2 PR base `cursor/retire-payments-step1-47ba`.