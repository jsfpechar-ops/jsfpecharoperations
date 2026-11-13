# 1450: Go scheduler package (dormant): enqueue every job kind on Python's schedule behind `UBYHOST_SCHEDULER=go`

Status: todo
Depends on: 1452 (`registerBackground`) | Base: the orchestrator's branch (claude/happy-babbage-2zeeam); anchors checked in step 0 | Branch: the current one
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

**One big PR mode.** Work on the branch that is checked out. Commit `1450 step k` after each step. Do not create a branch, do not push, do not open a PR.

## 1. Objective

Add `go/internal/scheduler` and `go/cmd/ubyhost-web/register_scheduler.go`, so the Go service can enqueue all 15 job kinds with the same intervals, cron times and time zone as `App/app/scheduler.py`, but only when `UBYHOST_SCHEDULER=go` (default off: nothing in Go runs and Python keeps enqueuing). Plan step J7, tier A: this decides when the police filing sweep (`submit`) and the deadline watch (`deadlines`) run, so a parity golden from the real Python and APScheduler proves every fire time.

## 2. Context

Rules (AGENTS.md): 1 filing correctness first (the schedule of `submit` and `deadlines` must equal Python's, and a late run is enqueued, never dropped); 2 no personal data, no outbound request; 3 nothing real in the repo; 4 no new dependency: no cron library, the schedule code is hand-written (`go/go.mod` unchanged; `time/tzdata` is the standard library); 5 SQL with Postgres placeholders, no schema change (the `job` table and its index exist since `App/migrations_pg/00003_job.sql`).

**The code is in sidecar files.** `docs/tasks/1450-files/` mirrors the repo paths. You only copy them (step 1, step 2) and check their sha256 (step 0). Never type or edit the code.

**What it does.**
- `scheduler.Plan(lookup)` lists the 15 triggers in the order `scheduler.start()` adds them. `ical` reads `UBYHOST_ICAL_POLL_MINUTES` (60) and `submit` reads `UBYHOST_SUBMIT_SWEEP_MINUTES` (10). Both are parsed like Python's `int()`: white space, a sign, `_` between digits. Unset gives the default. A value `int()` refuses (empty included) stops Python at import, and a value at or below 0 makes Python ignore the switch (brief 1451, `go_scheduler_problem`). Go refuses both, so both sides always agree that the switch is off. The one value Python takes and Go refuses is non-ASCII digits; the Python watch of 1451 covers that case.
- `NewState`, `NextWake` and `Due` hold the schedule with APScheduler 3.11.3 rules (`App/requirements.txt`): interval jobs count elapsed time and first run one interval after start (`ical` and `photo_sweep`: 20 s, `_soon()`); cron jobs run at the local wall time in `Europe/Prague`; missed runs coalesce into one.
- `Enqueue(ctx, pool, kind)` is the SQL of `App/app/jobqueue.py` `enqueue`: `INSERT ... ON CONFLICT (kind) WHERE done_at IS NULL AND dead_at IS NULL DO NOTHING`.
- `Run` sleeps to the next due time and enqueues. It logs `scheduler started` once and `scheduler enqueued job=<kind>` for each row it adds. On a database error it logs `scheduler enqueue failed job=<kind> failed_total=<n>`, and that run is lost, as in Python. `Counts()` gives the running totals, and the Python watch (1451) enqueues a kind left out this way and raises the alert.
- `Setup` refuses to start unless every kind is in `UBYHOST_JOB_QUEUE_KINDS`: a kind off the queue runs in-process in Python, so a Go row for it would run it twice. Python's `go_scheduler_problem` (1451) ignores the switch on the same condition and keeps enqueuing.
- `register_scheduler.go`: `init()` calls `registerBackground("scheduler", schedulerTask)` (brief 1452). It starts once after the schema check, is stopped by SIGINT/SIGTERM and is joined before the pool closes. Tests that build the mux start nothing. Switch off: the setup returns nil. Bad configuration: it returns an error, logged as `background task not started task=scheduler error=UBYHOST_SCHEDULER=go is ignored, the Python worker keeps enqueuing: ...`.

**Set-up error: not fatal (decision).** `ubyhost-go` serves live pages since today, so a crash loop on a scheduler setting would take real pages down.
Not fatal is safe because the two sides refuse the same configurations, so Python then keeps enqueuing.
Any other way Go stops enqueuing (container down, crash loop, dropped profile) is caught by the Python watch: the jobs still get enqueued, and a critical alert is raised.

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
2. With the switch off, Python still accepts `UBYHOST_SUBMIT_SWEEP_MINUTES=0` (APScheduler turns it into 1 s), as today. With the switch on, both sides treat 0 or below as "switch off", so the value never runs on one side and fails on the other.

**Nobody enqueuing** (switch on, Go not scheduling) is closed by brief 1451's Python watch, not here.

**Double enqueue (Go and Python both on for a minute during the switch or the rollback).** The partial unique index `job_one_open_per_kind ON job (kind) WHERE done_at IS NULL AND dead_at IS NULL` and `ON CONFLICT ... DO NOTHING` on both sides allow one open row per kind, so two enqueues at the same moment write one row (`TestConcurrentEnqueueAddsOneRow`), and two runs of one kind never overlap. Each side keeps its own phase, so while both run a kind can run twice in one interval, one run after the other. Every kind already tolerates that: it is what a restart does today.

**Parity proof.** `App/scripts/scheduler_golden.py` calls the real `scheduler.start()` with a stand-in for `BackgroundScheduler` that records every `add_job`, then builds the real APScheduler triggers and lists 30 fire times per kind from six starts: the nights of both 2026 DST changes, a day before each, exactly 06:00 on 2026-01-15, and 04:14:59.999 on 2026-07-01. It writes `go/internal/scheduler/testdata/python_schedule.json` (11482 lines). `parity_test.go` checks the kinds, their order, trigger arguments, `job_intervals()` and every fire time in UTC and local time. `scheduler_test.go` covers both DST days, interval across DST, first runs, coalescing, the env, the switch and `Run`. `enqueue_test.go` needs PostgreSQL (`UBYHOST_TEST_DATABASE_URL`, skips otherwise).

**Verified by the brief writer** in a throwaway worktree of the branch head (fd4075b47), with 1452 applied first and exactly these files: `gofmt -l` empty, `go build ./...`, `go vet ./internal/scheduler/... ./cmd/...` clean, `go test -race ./internal/scheduler/... ./cmd/ubyhost-web/...` ok against a disposable PostgreSQL 16 (the two enqueue tests PASS, no SKIP), `go mod tidy -diff` empty; the golden script reproduces the golden byte for byte. In the first round these mutations were caught: retention 03:30 to 03:31, `soon` 20 s to 21 s, a cron run as "same time + 24 h", a cron time equal to the start skipped. The schedule logic is unchanged since.

Anchors (step 0, `grep -cF` prints 1 or more): `go/cmd/ubyhost-web/registry.go` `func registerBackground(` (1452 is in); `go/cmd/ubyhost-web/main.go` `startBackground(jobCtx, pool, &jobsDone)`; `go/internal/jobs/queue.go` `func Now(delta time.Duration) string {`; `App/migrations_pg/00003_job.sql` `job_one_open_per_kind`; `App/app/scheduler.py` `_target("guide_import"), "interval", minutes=minutes["guide_import"],`; `App/requirements.txt` `APScheduler==3.11.3`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/scheduler/scheduler.go` | create (copy) | `Plan`, `Setup`, `State`, `Enqueue`, `Run` |
| `go/internal/scheduler/parity_test.go` | create (copy) | Go against the Python golden |
| `go/internal/scheduler/scheduler_test.go` | create (copy) | DST, coalesce, env, switch, `Run` |
| `go/internal/scheduler/enqueue_test.go` | create (copy) | one open row per kind (PostgreSQL) |
| `go/internal/scheduler/testdata/python_schedule.json` | create (copy, then regenerated) | the golden |
| `go/cmd/ubyhost-web/register_scheduler.go` | create (copy) | the `scheduler` background task |
| `go/cmd/ubyhost-web/register_scheduler_test.go` | create (copy) | registered once; off, bad config and on; every Go kind is scheduled |
| `App/scripts/scheduler_golden.py` | create (copy) | writes the golden from the real Python |
| `docs/tasks/1450-report.md` | create | the report |

`docs/tasks/1450-files/` is part of this brief; do not edit it. No other file may change.

## 4. Steps

0. Checks (from the repo root, one call): `git status --short -- go/internal/scheduler go/cmd/ubyhost-web App/scripts | tail -5` is empty; `ls go/internal/scheduler App/scripts/scheduler_golden.py go/cmd/ubyhost-web/register_scheduler.go 2>&1 | tail -3` says "No such file" three times; each anchor of section 2 gives 1 or more with `grep -cF '<anchor>' <file>`. Then:

```bash
cd docs/tasks/1450-files && sha256sum -c <<'EOF' 2>&1 | tail -10
72a69bd3ede06f21ff3db3d54617e98e364a90cab8eb4701065985a0c41681de  App/scripts/scheduler_golden.py
f12774489d489e97b3189185cf95baa511d4b5cc64e4a24f05e319feaa6029e8  go/cmd/ubyhost-web/register_scheduler.go
7e62c63bd56acd870f7e6dfc028d28741d2d651dd9279e34160062e2cab72e27  go/cmd/ubyhost-web/register_scheduler_test.go
a38d857b5976ba571ceba46d0c67752f03594f88d7f14a88b75bd56110e10bae  go/internal/scheduler/enqueue_test.go
07c88a72850b2a7f9b4931ec82e50fd547c4447ef0375d1699b4e500a381addc  go/internal/scheduler/parity_test.go
5171268ea366a865fdbd05f2d83de29c20d0509cfe9f0ebf3ddac9b01f4ababf  go/internal/scheduler/scheduler.go
3c4e1d1ad145b54346f4f1b6b2e9d0bdce8e0aec707404c02f474ad29042d202  go/internal/scheduler/scheduler_test.go
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

   Expected: no output (or `go: downloading` lines only). Commit only these files: `git add go/internal/scheduler go/cmd/ubyhost-web/register_scheduler.go go/cmd/ubyhost-web/register_scheduler_test.go && git commit -m "1450 step 1"`.

2. Copy the golden script and check it reproduces the golden (from the repo root). If `App/.venv/bin/python` is missing, first `cd App && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt 2>&1 | tail -5; cd ..`.

```bash
cp docs/tasks/1450-files/App/scripts/scheduler_golden.py App/scripts/scheduler_golden.py
cd App && .venv/bin/python scripts/scheduler_golden.py 2>&1 | tail -1; cd .. && sha256sum go/internal/scheduler/testdata/python_schedule.json | tail -1 && git status --short | tail -5
```

   Expected: `wrote .../go/internal/scheduler/testdata/python_schedule.json`, the hash `17109dfde7ebba051593e30c87e44f44f69805b5402a88d3f6a67fa6c0ef56e1`, and `git status --short -- go/internal/scheduler App/scripts` shows only `?? App/scripts/scheduler_golden.py`. A different hash: STOP (the Python schedule differs from the base). Commit: `git add App/scripts/scheduler_golden.py && git commit -m "1450 step 2"`.

3. Run section 6. Write the report (section 9) and commit it: `git add docs/tasks/1450-report.md docs/tasks/1450-go-scheduler-package.md && git commit -m "1450 report"`. The code is dormant: nothing runs until the owner switch in 1451.

## 5. Do not touch

`go/cmd/ubyhost-web/main.go`, `registry.go` (brief 1452 owns both), `register_jobs.go`, `register_filing.go` and every other `register_*.go`; `go/internal/jobs/`, `go/internal/hostweb/`, `go/internal/session/`; `go/go.mod`, `go/go.sum`; `App/app/` (brief 1451 owns `App/app/scheduler.py`), `App/tests/` (including `conftest.py`), `App/migrations_pg/`; `deploy/`; `docs/ENVIRONMENT.md`; `docs/context/*`; `docs/tasks/1450-files/`. Never set `UBYHOST_SCHEDULER` anywhere. Other writers commit on this branch at the same time: stage only your files by name, never `git add -A` or `git commit -a`. Rules 1 to 5 as in section 2.

## 6. Commands

From the repo root:

- `cd go && gofmt -l internal/scheduler cmd/ubyhost-web 2>&1 | tail -5` prints nothing.
- `cd go && go vet ./internal/scheduler/... ./cmd/... 2>&1 | tail -30` prints nothing.
- `cd go && go test -count=1 -v ./internal/scheduler/ 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -20` prints `--- PASS` for `TestPlanMatchesPythonAddJobCalls`, `TestFireTimesMatchAPScheduler`, `TestDailyAcrossSpringForward`, `TestDailyAcrossFallBack`, `TestIntervalIgnoresDaylightSaving`, `TestFirstRuns`, `TestCoalesceAfterAStall`, `TestPlanReadsTheTwoIntervals`, `TestEnabled`, `TestSetupNeedsEveryKindQueued`, `TestRunEnqueuesAndStops`; `--- SKIP` for `TestEnqueueKeepsOneOpenRowPerKind` and `TestConcurrentEnqueueAddsOneRow` without `UBYHOST_TEST_DATABASE_URL` (CI runs them; if it is set they must PASS); then `ok`.
- `cd go && go test -count=1 -v -run 'Scheduler' ./cmd/ubyhost-web/ 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -5` prints `--- PASS` for `TestSchedulerIsRegisteredAsBackgroundTask`, `TestSchedulerTaskSetup`, `TestSchedulerCoversEveryGoKind`, then `ok`; `cd go && go test -count=1 ./cmd/ubyhost-web/ 2>&1 | tail -3` prints `ok`.
- `cd go && go build ./... 2>&1 | tail -10` prints nothing.
- `cd go && go mod tidy -diff 2>&1 | grep -v downloading | tail -5` prints nothing.
- `python3 scripts/context_lint.py 2>&1 | tail -30` shows no error naming 1450.

Test-map: no row covers Go packages; the commands above are this brief's tests. No file under `App/app` or `App/tests` changes, so no pytest.

## 7. Acceptance

- [ ] `git log --oneline --grep='^1450 '` lists `1450 step 1`, `1450 step 2` and `1450 report`, and `git show --stat --format=%s $(git log --format=%h --grep='^1450 step') | tail -12` names exactly the eight files of section 3 that are not the report.
- [ ] The copied files equal the sidecar files: `for f in $(cd docs/tasks/1450-files && find . -type f); do cmp docs/tasks/1450-files/$f $f; done` prints nothing.
- [ ] Section 6 output exactly as stated.
- [ ] `git show --stat --format= $(git log --format=%h --grep='^1450 ') -- go/cmd/ubyhost-web/main.go go/cmd/ubyhost-web/registry.go go/internal/jobs go/go.mod App/app deploy | tail -3` prints nothing.

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

1. The files changed (`git show --stat` of the step commits).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of:

- `go/internal/scheduler/scheduler.go`: `first`, `next`, `dailyAtOrAfter` (DST, coalesce), `Enqueue` (same SQL as `jobqueue.enqueue`), `Run` (never drops a due kind; stops on its context).
- `go/cmd/ubyhost-web/register_scheduler.go`: off means nil, bad configuration means an error (not fatal, see the decision in section 2), the set-up never touches the pool.
- `go/internal/scheduler/scheduler.go` `pyInt` and `minutesEnv`: they accept what Python's `int()` accepts (ASCII digits) and refuse 0 or below, matching `go_scheduler_problem` in 1451.
- `App/scripts/scheduler_golden.py`: captures the real `add_job` calls; the trigger construction matches APScheduler's own defaults.
- `go/internal/scheduler/parity_test.go`: compares every field the golden holds.

## Owner steps

None. Nothing changes in production: `UBYHOST_SCHEDULER` is not set and `ubyhost-go` does not receive it until brief 1451. The switch itself is in 1451.
