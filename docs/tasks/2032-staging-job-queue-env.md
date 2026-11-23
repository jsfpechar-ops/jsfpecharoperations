# 2032: Job queue runs all 15 kinds on staging (D1 auth/admin report, production blocker)

Status: todo
Depends on: 2029 (PR #1263 merged) | Base commit: main | Branch: task/2032-job-queue-env
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

After the Python worker was removed (compose comment `1782: sole app process`), only the Go service runs and enqueues jobs. Make a wrong job env fail loudly and make the shipped docs and `.env.example` give a working 15-kind setup, so staging and production cannot silently stall.

## 2. Context

Root cause (from code; the staging `.env` could not be read): a kind runs only if it is in `UBYHOST_GO_JOB_KINDS` (`go/cmd/ubyhost-web/main.go:161`) AND enqueued by the Go scheduler, which starts only when `UBYHOST_SCHEDULER=go` and `scheduler.Setup` accepts the env (`register_scheduler.go:32-47`): every one of the 15 kinds of `scheduler.Plan` must be in `UBYHOST_JOB_QUEUE_KINDS` (`CheckQueued`). On failure the Go service logs "scheduler is ignored, the Python worker keeps enqueuing"; no worker exists any more, so nothing is enqueued. Matches staging: `billing_snapshot` ran 36 h ago, 13 kinds Late, `deadlines` failed (job_failed alert).
`docs/ENVIRONMENT.md` lines 54-55 still list 8 Go kinds and a worker fallback; `deploy/lightsail/.env.example` has no `UBYHOST_SCHEDULER`, `UBYHOST_GO_JOB_KINDS` or `UBYHOST_JOB_QUEUE_KINDS` line. Go handlers exist for all 15 kinds (`register_job_*.go`, `goHandlers`).
Missing `billing` row on the Operations page is parity, not a bug: Python `job_intervals()` also omits `billing` (cron-only); `go/internal/web/auth/opspage/data.go:139-147`.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/cmd/ubyhost-web/register_scheduler.go | edit | when `UBYHOST_SCHEDULER=go` and Setup fails, return the error as a startup log at error level naming the missing kinds (it already returns the error; make sure main logs it with `log.Printf` prefix `FATAL-CONFIG` and opens a `job_failed` alert if the alert helper is reachable without the pool, else log only) |
| go/cmd/ubyhost-web/main.go | edit | if `UBYHOST_SCHEDULER` is not `go` and no Python worker exists, log one warning line "no scheduler: no job will be enqueued" |
| deploy/lightsail/.env.example | edit | add the three lines with the full 15-kind value for both lists and `UBYHOST_SCHEDULER=go` |
| docs/ENVIRONMENT.md | edit | rows 54-55: list all 15 kinds, delete the worker fallback text |
| docs/OPERATIONS.md | edit | one line under jobs: where to see "scheduler ignored" |

The 15 kinds, in order: `ical,submit,deadlines,mail,photo_sweep,meta_capi,retention,stay_fee_mail,stripe_sweep,billing,billing_snapshot,door_codes,posthog,push,guide_import`.

## 4. Steps

1. `grep -n "scheduler" go/cmd/ubyhost-web/main.go | head`; read `register_scheduler.go` fully (80 lines).
2. Make the two code edits and one unit test with the env of `scheduler_test.go` (missing kind gives an error naming it).
3. Edit the three docs/example files. `python3 scripts/context_lint.py | tail -30`.
4. `cd go && go test ./cmd/ubyhost-web/... ./internal/scheduler/... 2>&1 | tail -30`.

## 5. Do not touch

`submit` safety: `filing-guard.sh`, DISASTER_RECOVERY steps and rule 1. Do not add `submit` to any list in staging docs beyond the full list; the full list is correct only because mock UbyPort is staging's default. Production `.env` is the owner's.

## 6. Commands

The go test command in step 4 and `python3 scripts/context_lint.py | tail -30`.

## 7. Acceptance

- [ ] Tests pass; `.env.example` and ENVIRONMENT list the same 15 kinds as `Plan`.
- [ ] Owner steps (put in the PR, plain words): 1. SSH to staging, open `.env`. 2. Set `UBYHOST_SCHEDULER=go`, and `UBYHOST_GO_JOB_KINDS` and `UBYHOST_JOB_QUEUE_KINDS` to the 15-kind value, `UBYHOST_ICAL_POLL_MINUTES=60`, `UBYHOST_SUBMIT_SWEEP_MINUTES=10`, `UBYHOST_ENABLE_SCHEDULER=1`. 3. Run `./scripts/deploy.sh`. 4. `docker compose logs ubyhost-go --tail 50` must not say "ignored". 5. Operations page: 14 rows OK within 2x interval, no `job_failed`. 6. Do the same check on production: if its list lacks `mail`, `door_codes`, `photo_sweep`, `retention`, `stay_fee_mail`, `guide_import`, `billing`, those jobs are not running there either.

## 8. Stop and ask

As 2030 §8.

## 9. Report

Write docs/tasks/NNNN-report.md per executor.md: files changed, commands run with results, anything skipped.
