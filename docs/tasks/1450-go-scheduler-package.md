# 1450: Go scheduler package (dormant): enqueue every job kind on Python's schedule behind `UBYHOST_SCHEDULER=go`

Status: todo
Depends on: none | Base commit: 34738084 | Branch: task/1450-go-scheduler
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add `go/internal/scheduler` and `go/cmd/ubyhost-web/register_scheduler.go`, so the Go service can enqueue all 15 job kinds with the same intervals, cron times and time zone as `App/app/scheduler.py`, but only when `UBYHOST_SCHEDULER=go` (default off: nothing in Go runs and Python keeps enqueuing). Plan step J7, tier A: this decides when the police filing sweep (`submit`) and the deadline watch (`deadlines`) run, so a parity golden from the real Python and APScheduler proves every fire time.

## 2. Context

Rules (AGENTS.md): 1 filing correctness first (the schedule of `submit` and `deadlines` must equal Python's, and a late run is enqueued, never dropped); 2 no personal data, no outbound request; 3 nothing real in the repo; 4 no new dependency: no cron library, the schedule code is hand-written (`go/go.mod` unchanged; `time/tzdata` is the standard library); 5 SQL with Postgres placeholders, no schema change (the `job` table and its index exist since `App/migrations_pg/00003_job.sql`).

**The code is in sidecar files.** `docs/tasks/1450-files/` mirrors the repo paths. You only copy them (step 1, step 2) and check their sha256 (step 0). Never type or edit the code.

**What it does.**
- `scheduler.Plan(getenv)` lists the 15 triggers in the order `scheduler.start()` adds them; `ical` reads `UBYHOST_ICAL_POLL_MINUTES` (60), `submit` reads `UBYHOST_SUBMIT_SWEEP_MINUTES` (10).
- `NewState`, `NextWake` and `Due` hold the schedule with APScheduler 3.11.3 rules (`App/requirements.txt`): interval jobs count elapsed time and first run one interval after start (`ical` and `photo_sweep`: 20 s, `_soon()`); cron jobs run at the local wall time in `Europe/Prague`; missed runs coalesce into one.
- `Enqueue(ctx, pool, kind)` is the SQL of `App/app/jobqueue.py` `enqueue`: `INSERT ... ON CONFLICT (kind) WHERE done_at IS NULL AND dead_at IS NULL DO NOTHING`.
- `Run` sleeps to the next due time, enqueues, logs `scheduler started` once and `scheduler enqueued job=<kind>` for each row it adds, `scheduler enqueue failed` on an error.
- `Setup` refuses to start unless every kind is in `UBYHOST_JOB_QUEUE_KINDS`: a kind off the queue runs in-process in Python, so a Go row for it would run it twice. Brief 1451 makes Python refuse the same configuration.
- `register_scheduler.go`: `main.go` has no hook for a background task, so `init()` uses `registerRoutes(startScheduler)`. It adds no route. `run()` calls `newMux` once, after the schema check, with the real pool. `startScheduler` returns at once when the pool is nil (the tests) or `UBYHOST_SCHEDULER` is not `go`, and starts the loop once (`sync.Once`), stopped by SIGINT or SIGTERM.

**Parity table** (Python `App/app/scheduler.py` at 34738084; every kind is enqueued by Go, the consumer does not change: Go claims the kinds in `UBYHOST_GO_JOB_KINDS`, Python claims the rest, for example `door_codes` and `mail`):

| Kind | Python trigger (line) | Go trigger (`Plan`) |
|---|---|---|
| ical | interval `ICAL_POLL_MINUTES` (60), first run +20 s (591) | `Every` env (60) min, `FirstAfter` 20 s |
| submit | interval `SUBMIT_SWEEP_MINUTES` (10) (595) | `Every` env (10) min |
| deadlines | interval 30 min, PostgreSQL only (602) | `Every` 30 min (Go is always PostgreSQL) |
| mail | interval 5 min (606) | `Every` 5 min |
| photo_sweep | interval 720 min, first run +20 s (609) | `Every` 720 min, `FirstAfter` 20 s |
| meta_capi | interval 10 min (613) | `Every` 10 min |
| retention | cron 03:30 (617) | daily 03:30 Europe/Prague |
| stay_fee_mail | cron 07:00 (621) | daily 07:00 |
| stripe_sweep | cron 04:15 (625) | daily 04:15 |
| billing | cron 06:00 (629) | daily 06:00 |
| billing_snapshot | cron 06:15 (633) | daily 06:15 |
| door_codes | interval 5 min (637) | `Every` 5 min |
| posthog | interval 15 min (641) | `Every` 15 min |
| push | interval 1 min (645) | `Every` 1 min |
| guide_import | interval 60 min (649) | `Every` 60 min |

All 15: `max_instances=1, coalesce=True`, scheduler `timezone=config.TIMEZONE` (`Europe/Prague`, config.py line 443). The `job_queue` drain job (15 s) is not an enqueue and stays in Python.

**Time zones and daylight saving.** Interval triggers are elapsed time in APScheduler (`previous_fire_time.timestamp() + interval_length`), so they ignore DST; Go adds a `time.Duration`. None of the five cron times is in the 02:00 to 03:00 gap (last Sunday in March) or the 02:00 to 02:59 repeat (last Sunday in October), so each runs once a day, 23 h or 25 h after the day before.

**Differences from Python, on purpose:**
1. APScheduler skips a run that starts more than 1 s late (`misfire_grace_time` default 1). Go enqueues it late, once. Enqueue is idempotent, so a late row is harmless, and a dropped `submit` row is not.
2. Python accepts `UBYHOST_SUBMIT_SWEEP_MINUTES=0` (APScheduler turns it into 1 s) and crashes on a non-number. Go refuses anything but a whole number above 0 and logs `scheduler not started`.

**Double enqueue (Go and Python both on for a minute during the switch or the rollback).** The partial unique index `job_one_open_per_kind ON job (kind) WHERE done_at IS NULL AND dead_at IS NULL` and `ON CONFLICT ... DO NOTHING` on both sides allow one open row per kind, so two enqueues at the same moment write one row (`TestConcurrentEnqueueAddsOneRow`), and two runs of one kind never overlap. Each side keeps its own phase, so while both run a kind can run twice in one interval, one run after the other. Every kind already tolerates that: it is what a restart does today.

**Parity proof.** `App/scripts/scheduler_golden.py` calls the real `scheduler.start()` with a stand-in for `BackgroundScheduler` that records every `add_job`, then builds the real APScheduler triggers and lists 30 fire times per kind from six starts: the nights of both 2026 DST changes, a day before each, exactly 06:00 on 2026-01-15, and 04:14:59.999 on 2026-07-01. It writes `go/internal/scheduler/testdata/python_schedule.json` (11482 lines). `parity_test.go` checks the kinds, their order, trigger arguments, `job_intervals()` and every fire time in UTC and local time. `scheduler_test.go` covers both DST days, interval across DST, first runs, coalescing, the env, the switch and `Run`. `enqueue_test.go` needs PostgreSQL (`UBYHOST_TEST_DATABASE_URL`, skips otherwise).

**Verified by the brief writer** in a throwaway worktree of 34738084 with exactly these files: `gofmt -l` empty, `go build ./...`, `go vet ./internal/scheduler/... ./cmd/...` clean, `go test -race ./internal/scheduler/... ./cmd/ubyhost-web/...` ok, `go mod tidy -diff` empty, with PostgreSQL 16 the two enqueue tests PASS; the golden script run twice gives the same sha256. Mutations caught: retention 03:30 to 03:31, `soon` 20 s to 21 s, a cron run as "same time + 24 h", a cron time equal to the start skipped.

Anchors (step 0, `grep -cF` prints 1 or more): `go/cmd/ubyhost-web/registry.go` `func registerRoutes(`; `go/cmd/ubyhost-web/main.go` `for _, fn := range routeFuncs {`; `go/internal/jobs/queue.go` `func Now(delta time.Duration) string {`; `App/migrations_pg/00003_job.sql` `job_one_open_per_kind`; `App/app/scheduler.py` `_target("guide_import"), "interval", minutes=minutes["guide_import"],`; `App/requirements.txt` `APScheduler==3.11.3`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/scheduler/scheduler.go` | create (copy) | `Plan`, `Setup`, `State`, `Enqueue`, `Run` |
| `go/internal/scheduler/parity_test.go` | create (copy) | Go against the Python golden |
| `go/internal/scheduler/scheduler_test.go` | create (copy) | DST, coalesce, env, switch, `Run` |
| `go/internal/scheduler/enqueue_test.go` | create (copy) | one open row per kind (PostgreSQL) |
| `go/internal/scheduler/testdata/python_schedule.json` | create (copy, then regenerated) | the golden |
| `go/cmd/ubyhost-web/register_scheduler.go` | create (copy) | starts the scheduler when switched on |
| `go/cmd/ubyhost-web/register_scheduler_test.go` | create (copy) | nil pool starts nothing; every Go kind is scheduled |
| `App/scripts/scheduler_golden.py` | create (copy) | writes the golden from the real Python |
| `docs/tasks/1450-report.md` | create | the report |

`docs/tasks/1450-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (from the repo root, one call): `git branch --show-current` prints `task/1450-go-scheduler`; `git status --short | tail -5` is empty; `ls go/internal/scheduler App/scripts/scheduler_golden.py go/cmd/ubyhost-web/register_scheduler.go 2>&1 | tail -3` says "No such file" three times; each anchor of section 2 gives 1 or more with `grep -cF '<anchor>' <file>`. Then:

```bash
cd docs/tasks/1450-files && sha256sum -c <<'EOF' 2>&1 | tail -10
72a69bd3ede06f21ff3db3d54617e98e364a90cab8eb4701065985a0c41681de  App/scripts/scheduler_golden.py
a5bbd5b26145f9f2d48b293ecf5d14c25eca1caec2ed02aeb8360986885ae0af  go/cmd/ubyhost-web/register_scheduler.go
4e087574074f5ede9456f4f3ea0c5a18ad084aeb0727486cd69bf390d912b61b  go/cmd/ubyhost-web/register_scheduler_test.go
a38d857b5976ba571ceba46d0c67752f03594f88d7f14a88b75bd56110e10bae  go/internal/scheduler/enqueue_test.go
1f87d29b46112a91645dcfe440f2d88ea063b7a5da2c9bbaa0b6980ef02cfce7  go/internal/scheduler/parity_test.go
faf24e939ade3f8690b1baa4ba2525dde8948505373bb2224020d5d8c8fd28cc  go/internal/scheduler/scheduler.go
ab75e40f50d30a238c0488b6e3abc9a821b2aef549d9ca7b89c3d85c5ec2f5d6  go/internal/scheduler/scheduler_test.go
17109dfde7ebba051593e30c87e44f44f69805b5402a88d3f6a67fa6c0ef56e1  go/internal/scheduler/testdata/python_schedule.json
EOF
```

   Expected: eight `OK` lines. Anything else: STOP (section 8).

1. Copy the Go files (from the repo root):

```bash
mkdir -p go/internal/scheduler/testdata
cp docs/tasks/1450-files/go/internal/scheduler/scheduler.go docs/tasks/1450-files/go/internal/scheduler/parity_test.go docs/tasks/1450-files/go/internal/scheduler/scheduler_test.go docs/tasks/1450-files/go/internal/scheduler/enqueue_test.go go/internal/scheduler/
cp docs/tasks/1450-files/go/internal/scheduler/testdata/python_schedule.json go/internal/scheduler/testdata/
cp docs/tasks/1450-files/go/cmd/ubyhost-web/register_scheduler.go docs/tasks/1450-files/go/cmd/ubyhost-web/register_scheduler_test.go go/cmd/ubyhost-web/
cd go && gofmt -l internal/scheduler cmd/ubyhost-web 2>&1 | tail -5 && go build ./... 2>&1 | tail -10
```

   Expected: no output (or `go: downloading` lines only). Commit `1450 step 1`.

2. Copy the golden script and check it reproduces the golden (from the repo root). If `App/.venv/bin/python` is missing, first `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt 2>&1 | tail -5; cd ..`.

```bash
cp docs/tasks/1450-files/App/scripts/scheduler_golden.py App/scripts/scheduler_golden.py
cd App && .venv/bin/python scripts/scheduler_golden.py 2>&1 | tail -1; cd .. && sha256sum go/internal/scheduler/testdata/python_schedule.json | tail -1 && git status --short | tail -5
```

   Expected: `wrote .../go/internal/scheduler/testdata/python_schedule.json`, the hash `17109dfde7ebba051593e30c87e44f44f69805b5402a88d3f6a67fa6c0ef56e1`, and `git status` shows only `?? App/scripts/scheduler_golden.py`. A different hash: STOP (the Python schedule differs from the base). Commit `1450 step 2`.

3. Run section 6. Write the report (section 9) and commit it as `1450 report`. Open one draft PR. The code is dormant, so the owner may merge it when CI is green.

## 5. Do not touch

`go/cmd/ubyhost-web/main.go`, `registry.go`, `register_jobs.go`, `register_filing.go` and every other `register_*.go`; `go/internal/jobs/`, `go/internal/hostweb/`, `go/internal/session/`; `go/go.mod`, `go/go.sum`; `App/app/` (brief 1451 owns `App/app/scheduler.py`), `App/tests/` (including `conftest.py`), `App/migrations_pg/`; `deploy/`; `docs/ENVIRONMENT.md`; `docs/context/*`; `docs/tasks/1450-files/`. Never set `UBYHOST_SCHEDULER` anywhere. Rules 1 to 5 as in section 2.

## 6. Commands

From the repo root:

- `cd go && gofmt -l internal/scheduler cmd/ubyhost-web 2>&1 | tail -5` prints nothing.
- `cd go && go vet ./internal/scheduler/... ./cmd/... 2>&1 | tail -30` prints nothing.
- `cd go && go test -count=1 -v ./internal/scheduler/ 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -20` prints `--- PASS` for `TestPlanMatchesPythonAddJobCalls`, `TestFireTimesMatchAPScheduler`, `TestDailyAcrossSpringForward`, `TestDailyAcrossFallBack`, `TestIntervalIgnoresDaylightSaving`, `TestFirstRuns`, `TestCoalesceAfterAStall`, `TestPlanReadsTheTwoIntervals`, `TestEnabled`, `TestSetupNeedsEveryKindQueued`, `TestRunEnqueuesAndStops`; `--- SKIP` for `TestEnqueueKeepsOneOpenRowPerKind` and `TestConcurrentEnqueueAddsOneRow` without `UBYHOST_TEST_DATABASE_URL` (CI runs them; if it is set they must PASS); then `ok`.
- `cd go && go test -count=1 ./cmd/ubyhost-web/ 2>&1 | tail -5` prints `ok`.
- `cd go && go build ./... 2>&1 | tail -10` prints nothing.
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- `python3 scripts/context_lint.py 2>&1 | tail -30` shows no error naming 1450.

Test-map: no row covers Go packages; the commands above are this brief's tests. No file under `App/app` or `App/tests` changes, so no pytest.

## 7. Acceptance

- [ ] `git diff --stat 34738084..HEAD -- . ':!docs/tasks/1450-go-scheduler-package.md' ':!docs/tasks/1450-files'` lists exactly the files of section 3.
- [ ] The eight copied files equal the sidecar files: `for f in $(cd docs/tasks/1450-files && find . -type f); do cmp docs/tasks/1450-files/$f $f; done` prints nothing.
- [ ] Section 6 output exactly as stated.
- [ ] `git diff --stat 34738084..HEAD -- go/cmd/ubyhost-web/main.go go/cmd/ubyhost-web/registry.go go/internal/jobs go/go.mod App/app deploy` prints nothing.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found, a file to create exists, a sha256 differs, or the regenerated golden has another hash;
- a test fails twice (never change the code: it is fixed by hash);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1450-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- `go/internal/scheduler/scheduler.go`: `first`, `next`, `dailyAtOrAfter` (DST, coalesce), `Enqueue` (same SQL as `jobqueue.enqueue`), `Run` (never drops a due kind; stops on its context).
- `go/cmd/ubyhost-web/register_scheduler.go`: starts only with a pool and `UBYHOST_SCHEDULER=go`, once; uses `registerRoutes` as a start hook because `main.go` has none (see Owner steps).
- `App/scripts/scheduler_golden.py`: captures the real `add_job` calls; the trigger construction matches APScheduler's own defaults.
- `go/internal/scheduler/parity_test.go`: compares every field the golden holds.

## Owner steps

1. Merge the PR when CI is green (`scripts/merge-pr-on-green.sh`). Nothing changes in production: `UBYHOST_SCHEDULER` is not set and `ubyhost-go` does not receive it until brief 1451.
2. Decide later (no action now): a proper `registerBackground(func(ctx, pool))` hook in `main.go` would replace the `registerRoutes` workaround; that is a change to `main.go`, so it needs its own brief.
