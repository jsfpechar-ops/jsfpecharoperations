# 1166: Go job kind `deadlines` (deadline watch, DSR due alerts, filing watchdog, filing heartbeat)

Status: todo
Depends on: 1153, 1157, 1159b (merged) | Base commit: 8000926 | Branch: the orchestrator's branch (work on the current branch)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (filing path)

## 1. Objective

Add the job kind `deadlines` to the Go job queue, so that putting `deadlines` in `UBYHOST_GO_JOB_KINDS` (and `UBYHOST_JOB_QUEUE_KINDS`) makes Go run Python's `scheduler._job_deadlines` instead of Python. The Python job stays as it is; it is removed by a later brief after a clean production run.

## 2. Context

Hard rule 1: UbyPort filing correctness beats every other feature. This job is what tells the owner a filing deadline is at risk, so the Go job must do exactly what Python does, in the same order.

Python, `App/app/scheduler.py` `_job_deadlines` (behaviour to match, do not edit):

- `raised = reporting.check_deadlines()` then `due_requests = dsr.raise_due_alerts()` in ONE try: if `check_deadlines` raises, `raise_due_alerts` is skipped. On failure: log, `_job_failed("deadlines")` (critical alert at once), `watch_ok = False`.
- `filing_watchdog.run()` always runs next. If it raises: log, `_job_failed("deadlines")`, `_log_run(..., False)`, return: **no heartbeat ping at all**.
- Otherwise: `_job_ok` only if `watch_ok`; then `_filing_heartbeat(watchdog["at_risk"] > 0 or not watch_ok)`, i.e. `<UBYHOST_HEARTBEAT_FILING_URL>` or `<url>/fail`.
- `_JOB_LEVELS["deadlines"] = "critical"`; `host_i18n` `notification.job_name.deadlines` = `deadline watch`; `job_intervals()["deadlines"] = 30`.

Python queue side needs no change (verified): `App/app/jobqueue.py` `claim()` adds `AND NOT (kind = ANY(<GO_JOB_KINDS>))`, so a Go-owned `deadlines` row is never claimed by Python; the Python APScheduler keeps enqueuing the row every 30 min (`_target` -> `jobqueue.enqueue`, `ON CONFLICT ... DO NOTHING` while a row is open); `scheduler.start()` refuses a GO kind that is not also a queue kind. Nothing else in `App/app` calls `_job_deadlines` or `filing_watchdog.run()`.

Go pieces that exist (merged, unwired; do not edit): `go/internal/calendar/watch.go` `CheckDeadlines(ctx, pool, getenv, at, owner *int64) (int, error)`; `dsr_due.go` `RaiseDSRDueAlerts(ctx, pool, today) (int, error)` (uses only Y-M-D of `today`; Python's `date.today()` is the server-local date, and neither container sets `TZ`, so it is UTC; the new code passes `at.Local()`, which is exactly "server-local"); `filing_watchdog_run.go` `RunFilingWatchdog(ctx, pool, lookupEnv, at) (WatchdogResult, error)`; `filing_watchdog.go` `FilingHeartbeatURL(getenv, atRisk) string`. `go/internal/jobs`: `Ping`, `RaiseFailed`, `jobNames`, `jobLevels`; `drain` calls `Fail` (retry 1/5/15 min capped at the interval, `RaiseFailed` only when the row dies after 5 attempts) on a handler error, else `Finish` + `recordOK` (resolve `job_failed:<kind>`, write `job_last_ok:<kind>`).

Because Go raises `job_failed` only when a row dies, the new code calls `jobs.RaiseFailed(ctx, pool, "deadlines")` itself on each failed pass (Python parity: the critical alert opens at once) and also returns an error, so `drain` never calls `recordOK` (which would resolve that alert) on a failed run.

## 3. Files

| Path | Action | What |
|---|---|---|
| `go/internal/calendar/deadlines_job.go` | create | `RunDeadlinesJob` and the testable `runDeadlines` composition |
| `go/internal/calendar/deadlines_job_test.go` | create | branch-order unit tests (no DB) and one DB test |
| `go/internal/jobs/queue.go` | edit | `deadlines` in `jobNames` and `jobLevels` |
| `go/cmd/ubyhost-web/main.go` | edit | `deadlines` in `goIntervals` (30) and `goHandlers` |
| `go/cmd/ubyhost-web/main_test.go` | edit | `TestParseGoKindsDeadlines` |
| `docs/ENVIRONMENT.md` | edit | line 53: kinds list plus the switch-back note |
| `docs/tasks/1166-report.md` | create | the report |

No other file may change.

## 4. Steps

### Step 0: check the anchors

From the repo root:

```bash
grep -cF '"submit": "automatic filing", "push": "urgent alerts"}' go/internal/jobs/queue.go; grep -cF 'var jobLevels = map[string]string{"submit": "critical"}' go/internal/jobs/queue.go; grep -cF '"posthog": 15, "meta_capi": 10}' go/cmd/ubyhost-web/main.go; grep -cF '		"submit": func(ctx context.Context) (int, error) {' go/cmd/ubyhost-web/main.go; grep -cF 'func TestWrapSetsHardenHeaders(t *testing.T) {' go/cmd/ubyhost-web/main_test.go; grep -cF '`posthog` and `meta_capi` (the Go service reads the same `POSTHOG_*` and `UBYHOST_META_*` variables from `.env`). |' docs/ENVIRONMENT.md; ls go/internal/calendar/deadlines_job.go 2>&1 | tail -1
```

Expected: six lines `1`, then `ls: cannot access ...: No such file or directory`. Anything else: STOP (§8).

### Step 1: create `go/internal/calendar/deadlines_job.go`

Create the file with exactly this content (tabs for indentation, one trailing newline):

```go
// The deadlines job: App/app/scheduler.py _job_deadlines in Go. It runs the
// deadline watch (check_deadlines, then raise_due_alerts), then the filing
// watchdog even when the watch failed, then pings the filing heartbeat.
package calendar

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)

// DeadlinesSummary holds the counts of one deadlines run, as _log_run logs them.
type DeadlinesSummary struct {
	Alerts      int
	RequestsDue int
	Watchdog    WatchdogResult
}

// deadlinesSteps are the parts of one run; tests replace them.
type deadlinesSteps struct {
	check       func() (int, error)
	dsrDue      func() (int, error)
	watchdog    func() (WatchdogResult, error)
	raiseFailed func() error
	ping        func(url string)
	getenv      func(string) string
}

// RunDeadlinesJob is _job_deadlines for the Go job queue. at is the instant of
// the run; ping GETs the filing heartbeat URL (jobs.Ping in production). A
// failed watch or watchdog raises the critical job_failed alert at once, as
// Python's _job_failed does, and returns an error so the queue does not record
// a success. A failed watchdog sends no heartbeat at all.
func RunDeadlinesJob(ctx context.Context, pool *pgxpool.Pool, lookupEnv func(string) (string, bool), at time.Time, ping func(url string)) (DeadlinesSummary, error) {
	getenv := func(name string) string {
		v, _ := lookupEnv(name)
		return v
	}
	return runDeadlines(deadlinesSteps{
		check: func() (int, error) { return CheckDeadlines(ctx, pool, getenv, at, nil) },
		// Python's date.today() is the server's local date (TZ unset: UTC).
		dsrDue:      func() (int, error) { return RaiseDSRDueAlerts(ctx, pool, at.Local()) },
		watchdog:    func() (WatchdogResult, error) { return RunFilingWatchdog(ctx, pool, lookupEnv, at) },
		raiseFailed: func() error { return jobs.RaiseFailed(ctx, pool, "deadlines") },
		ping:        ping,
		getenv:      getenv,
	})
}

func runDeadlines(s deadlinesSteps) (DeadlinesSummary, error) {
	var sum DeadlinesSummary
	watchErr := func() error {
		n, err := s.check()
		if err != nil {
			return err
		}
		sum.Alerts = n
		n, err = s.dsrDue()
		if err != nil {
			return err
		}
		sum.RequestsDue = n
		return nil
	}()
	if watchErr != nil {
		slog.Error("deadline watch failed", "error", fmt.Sprintf("%T", watchErr))
		deadlinesRaiseFailed(s)
	} else if sum.Alerts > 0 || sum.RequestsDue > 0 {
		slog.Info("deadline watch", "alerts", sum.Alerts, "requests_due", sum.RequestsDue)
	}
	// WP23: the watchdog runs even when the watch failed; its mails and its
	// heartbeat reach the owner when the app itself is not being looked at.
	w, err := s.watchdog()
	if err != nil {
		// No ping at all: the external monitor alerts on the missing ping.
		slog.Error("filing watchdog failed", "error", fmt.Sprintf("%T", err))
		deadlinesRaiseFailed(s)
		if watchErr != nil {
			return sum, fmt.Errorf("deadline watch: %w; filing watchdog: %v", watchErr, err)
		}
		return sum, fmt.Errorf("filing watchdog: %w", err)
	}
	sum.Watchdog = w
	if w != (WatchdogResult{}) {
		slog.Info("filing watchdog", "at_risk", w.AtRisk, "unknown_risk", w.UnknownRisk,
			"awaiting_retry", w.AwaitingRetry, "host_mails", w.HostMails, "digest", w.Digest)
	}
	// A failed deadline watch counts as a failure too: nobody is being told.
	if url := FilingHeartbeatURL(s.getenv, w.AtRisk > 0 || watchErr != nil); url != "" {
		s.ping(url)
	}
	if watchErr != nil {
		return sum, fmt.Errorf("deadline watch: %w", watchErr)
	}
	return sum, nil
}

func deadlinesRaiseFailed(s deadlinesSteps) {
	if err := s.raiseFailed(); err != nil {
		slog.Error("job_failed alert not raised", "job", "deadlines")
	}
}
```

```bash
sha256sum go/internal/calendar/deadlines_job.go 2>&1 | tail -1
```

Expected: `f917eb69ddc57622877b2a488314c9893f4ef224517f76a136ce12b4d81fc857`. Commit `1166 step 1`.

### Step 2: create `go/internal/calendar/deadlines_job_test.go`

Create the file with exactly this content:

```go
package calendar

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"
)

// deadlinesFake records what runDeadlines called, in order.
type deadlinesFake struct {
	calls    []string
	checkErr error
	dsrErr   error
	wdErr    error
	wd       WatchdogResult
	url      string
}

func (f *deadlinesFake) steps() deadlinesSteps {
	return deadlinesSteps{
		check: func() (int, error) {
			f.calls = append(f.calls, "check")
			return 2, f.checkErr
		},
		dsrDue: func() (int, error) {
			f.calls = append(f.calls, "dsr")
			return 1, f.dsrErr
		},
		watchdog: func() (WatchdogResult, error) {
			f.calls = append(f.calls, "watchdog")
			return f.wd, f.wdErr
		},
		raiseFailed: func() error {
			f.calls = append(f.calls, "failed")
			return nil
		},
		ping: func(url string) { f.calls = append(f.calls, "ping "+url) },
		getenv: func(name string) string {
			if name == "UBYHOST_HEARTBEAT_FILING_URL" {
				return f.url
			}
			return ""
		},
	}
}

// TestRunDeadlinesOrderMatchesPython walks every branch of _job_deadlines.
func TestRunDeadlinesOrderMatchesPython(t *testing.T) {
	boom := errors.New("boom")
	cases := []struct {
		name    string
		fake    deadlinesFake
		calls   string
		wantErr bool
	}{
		{"all well", deadlinesFake{url: "https://hb.example/f"},
			"check,dsr,watchdog,ping https://hb.example/f", false},
		{"at risk pings fail", deadlinesFake{url: "https://hb.example/f/", wd: WatchdogResult{AtRisk: 1}},
			"check,dsr,watchdog,ping https://hb.example/f/fail", false},
		{"no heartbeat url", deadlinesFake{},
			"check,dsr,watchdog", false},
		{"check fails skips dsr", deadlinesFake{url: "https://hb.example/f", checkErr: boom},
			"check,failed,watchdog,ping https://hb.example/f/fail", true},
		{"dsr fails", deadlinesFake{url: "https://hb.example/f", dsrErr: boom},
			"check,dsr,failed,watchdog,ping https://hb.example/f/fail", true},
		{"watchdog fails, no ping", deadlinesFake{url: "https://hb.example/f", wdErr: boom},
			"check,dsr,watchdog,failed", true},
		{"both fail, no ping", deadlinesFake{url: "https://hb.example/f", checkErr: boom, wdErr: boom},
			"check,failed,watchdog,failed", true},
	}
	for _, c := range cases {
		f := c.fake
		_, err := runDeadlines(f.steps())
		if got := strings.Join(f.calls, ","); got != c.calls {
			t.Errorf("%s: calls %q, want %q", c.name, got, c.calls)
		}
		if (err != nil) != c.wantErr {
			t.Errorf("%s: error %v, want error %v", c.name, err, c.wantErr)
		}
	}
}

func TestRunDeadlinesSummary(t *testing.T) {
	f := deadlinesFake{wd: WatchdogResult{AtRisk: 3, Digest: 1}}
	sum, err := runDeadlines(f.steps())
	if err != nil {
		t.Fatal(err)
	}
	want := DeadlinesSummary{Alerts: 2, RequestsDue: 1, Watchdog: WatchdogResult{AtRisk: 3, Digest: 1}}
	if sum != want {
		t.Fatalf("summary %+v, want %+v", sum, want)
	}
}

// TestRunDeadlinesJobOnDatabase runs the real passes on an empty schema, then
// with the request table gone: the watchdog still runs, the heartbeat goes to
// /fail and the critical job_failed alert is open, as in Python.
func TestRunDeadlinesJobOnDatabase(t *testing.T) {
	pool := dbPool(t)
	ctx := context.Background()
	env := map[string]string{"UBYHOST_HEARTBEAT_FILING_URL": "https://hb.example/f"}
	lookup := func(name string) (string, bool) {
		v, ok := env[name]
		return v, ok
	}
	var pinged []string
	ping := func(url string) { pinged = append(pinged, url) }
	at := time.Date(2026, 11, 12, 9, 0, 0, 0, time.UTC)
	sum, err := RunDeadlinesJob(ctx, pool, lookup, at, ping)
	if err != nil {
		t.Fatalf("empty run: %v", err)
	}
	if sum != (DeadlinesSummary{}) {
		t.Fatalf("empty run summary %+v, want zero", sum)
	}
	if _, err := pool.Exec(ctx, "DROP TABLE data_subject_request CASCADE"); err != nil {
		t.Fatal(err)
	}
	if _, err := RunDeadlinesJob(ctx, pool, lookup, at, ping); err == nil {
		t.Fatal("run without the request table returned no error")
	}
	if strings.Join(pinged, ",") != "https://hb.example/f,https://hb.example/f/fail" {
		t.Fatalf("pings %v, want the plain URL then /fail", pinged)
	}
	var level, message string
	if err := pool.QueryRow(ctx,
		"SELECT level, message FROM alert WHERE dedupe_key = 'job_failed:deadlines' AND resolved_at IS NULL").Scan(&level, &message); err != nil {
		t.Fatal(err)
	}
	if level != "critical" || message != "Background job 'deadline watch' failed." {
		t.Fatalf("alert %q %q, want critical and the English deadlines name", level, message)
	}
}
```

```bash
sha256sum go/internal/calendar/deadlines_job_test.go 2>&1 | tail -1
```

Expected: `c0a9b317310114f1994cf12b9f1a350f39cd84935d5dabb25e4463f99bfa6ef1`. Commit `1166 step 2`.

### Step 3: `go/internal/jobs/queue.go`

Replace (exactly once):

```go
	"submit": "automatic filing", "push": "urgent alerts"}

// jobLevels is the alert level per job; every job not listed is "warning".
var jobLevels = map[string]string{"submit": "critical"}
```

with:

```go
	"submit": "automatic filing", "push": "urgent alerts", "deadlines": "deadline watch"}

// jobLevels is the alert level per job; every job not listed is "warning".
var jobLevels = map[string]string{"submit": "critical", "deadlines": "critical"}
```

```bash
sha256sum go/internal/jobs/queue.go 2>&1 | tail -1
```

Expected: `c6ca1a2c8cba41813f34a601c003edbf848fc2e3596aca02d97eaf9f145ff635`. Commit `1166 step 3`.

### Step 4: `go/cmd/ubyhost-web/main.go`

4a. Replace (exactly once) `"posthog": 15, "meta_capi": 10}` with `"posthog": 15, "meta_capi": 10, "deadlines": 30}` (same line, `goIntervals`).

4b. Replace (exactly once):

```go
		"submit": func(ctx context.Context) (int, error) {
			keys, err := secure.LoadDataKeys(os.Getenv)
```

with:

```go
		"deadlines": func(ctx context.Context) (int, error) {
			sum, err := calendar.RunDeadlinesJob(ctx, pool, os.LookupEnv, time.Now(), func(url string) {
				jobs.Ping(ctx, url, "filing")
			})
			return sum.Alerts + sum.RequestsDue, err
		},
		"submit": func(ctx context.Context) (int, error) {
			keys, err := secure.LoadDataKeys(os.Getenv)
```

No import changes (`calendar`, `jobs`, `os`, `time` are already imported).

```bash
sha256sum go/cmd/ubyhost-web/main.go 2>&1 | tail -1
```

Expected: `4abfffc3049fb63272f51c3e56b794be0d7c7477226b39d331bce9ad7f31106a`. Commit `1166 step 4`.

### Step 5: `go/cmd/ubyhost-web/main_test.go`

Replace (exactly once) `func TestWrapSetsHardenHeaders(t *testing.T) {` with:

```go
func TestParseGoKindsDeadlines(t *testing.T) {
	kinds, err := parseGoKinds("submit, deadlines")
	if err != nil || len(kinds) != 2 || kinds[1] != "deadlines" {
		t.Fatalf("parseGoKinds(submit, deadlines) = %v, %v", kinds, err)
	}
	if goIntervals["deadlines"] != 30 {
		t.Fatalf("deadlines interval %d, want 30 minutes", goIntervals["deadlines"])
	}
}

func TestWrapSetsHardenHeaders(t *testing.T) {
```

```bash
sha256sum go/cmd/ubyhost-web/main_test.go 2>&1 | tail -1
```

Expected: `bb459cf079be2f60fb2499cacdfabd2c53ab751149dc539c13838d83fdf66b61`. Commit `1166 step 5`.

### Step 6: `docs/ENVIRONMENT.md` (line 53, the `UBYHOST_GO_JOB_KINDS` row)

Replace (exactly once):

```text
Today `billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit`, `posthog` and `meta_capi` (the Go service reads the same `POSTHOG_*` and `UBYHOST_META_*` variables from `.env`). |
```

with:

```text
Today `billing_snapshot`, `stripe_sweep`, `ical`, `push`, `submit`, `posthog`, `meta_capi` and `deadlines` (the Go service reads the same `POSTHOG_*`, `UBYHOST_META_*` and `UBYHOST_HEARTBEAT_*` variables from `.env`). `deadlines` is the deadline watch plus the filing watchdog and its heartbeat; to hand it back to Python, remove it from this list (keep it in `UBYHOST_JOB_QUEUE_KINDS`) and run `./scripts/deploy.sh`. |
```

```bash
sha256sum docs/ENVIRONMENT.md 2>&1 | tail -1
```

Expected: `157d891d23864cded5b83f46b87e4c8a3968708590174f8bc7a56f2a6c117098`. Commit `1166 step 6`.

A sha256 mismatch in any step: compare your edit with the block once, fix it once; still different: STOP (§8).

## 5. Do not touch

`App/` (no Python change: §2), `go/go.mod`, `go/go.sum`, the other files in `go/internal/calendar/`, `go/internal/jobs/heartbeat.go`, `docs/context/status.md`, `docs/context/test-map.md` (both at lint caps), `scripts/pg-restore.sh`, `docs/DISASTER_RECOVERY.md`, `docs/plans/portable-disaster-recovery.md` (another thread owns them). Never set `UBYHOST_GO_JOB_KINDS` anywhere: switching is an owner step. Hard rules 1, 3 (no secret or URL in a log line), 4 (no dependency), 8 (never push to `main`).

## 6. Commands

From `go/` (test-map has no Go row; this is the check for the touched packages):

```bash
test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/calendar/ ./internal/jobs/ ./cmd/ubyhost-web/ -count=1 2>&1 | tail -30
```

Expected: three `ok` lines. Without `UBYHOST_TEST_DATABASE_URL` the DB tests skip locally and run in CI against Postgres.

```bash
go test ./internal/calendar/ ./cmd/ubyhost-web/ -run 'TestRunDeadlines|TestParseGoKindsDeadlines' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30
```

Expected: `--- PASS` for `TestRunDeadlinesOrderMatchesPython`, `TestRunDeadlinesSummary`, `TestParseGoKindsDeadlines`; `TestRunDeadlinesJobOnDatabase` is `--- PASS` with a database or `--- SKIP` without; two `ok` lines.

From the repo root:

```bash
python3 scripts/context_lint.py 2>&1 | tail -5
```

Expected: `context lint: OK`. No Python test runs: no `App/` file changes.

## 7. Acceptance

- [ ] The first §6 command prints three `ok` lines.
- [ ] Each step's `sha256sum` matched.
- [ ] `git diff --stat "$(git log -1 --format=%H --grep=^Brief.1166)"..HEAD | tail -30` lists only the §3 paths.
- [ ] `git diff "$(git log -1 --format=%H --grep=^Brief.1166)"..HEAD --stat -- App go/go.mod go/go.sum | tail -5` prints nothing.
- [ ] `grep -c '"deadlines"' go/cmd/ubyhost-web/main.go` prints `2`; `grep -c '"deadlines"' go/internal/jobs/queue.go` prints `2`.
- [ ] `grep -n 'slog\.' go/internal/calendar/deadlines_job.go | grep -i 'url\|err)' | tail -5` prints nothing (no URL or error text in a log line).
- [ ] `python3 scripts/context_lint.py` passes.
- [ ] Six commits `1166 step 1` to `1166 step 6`; nothing pushed.

## 8. Stop and ask

Stop, and write the report, if:

- an anchor in step 0 gives another count, or a "replace" block is not found exactly once;
- a sha256 still differs after one fix;
- a test fails twice, or `go vet` fails on the pasted code (do not rewrite it: report the error);
- `TestRunDeadlinesJobOnDatabase` fails against a database: report the failing line;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed, or `go.mod`/`go.sum` changes;
- a file outside §3 needs a change, or §5 would be touched;
- a step is unclear;
- you need push, merge, a PR, secrets, SSH or deploy (the orchestrator or owner does that).

## 9. Report

Write `docs/tasks/1166-report.md` (600 tokens at most) with: 1. `git diff --stat "$(git log -1 --format=%H --grep=^Brief.1166)"..HEAD` (last 10 lines); 2. each §6 command with the last 5 lines of its output; 3. §7 ticked; 4. deviations; 5. questions; 6. owner steps left. Set `Status: review`. Commit `1166 report`.

## Risk list (for the reviewer)

- `go/internal/calendar/deadlines_job.go` (whole file: order, skip-DSR-on-check-failure, no ping on watchdog failure, `/fail` on watch failure or at-risk, alert raised before returning the error).
- `go/cmd/ubyhost-web/main.go` (handler wiring, ping job name `filing`, interval 30).
- `go/internal/jobs/queue.go` (level `critical`, name `deadline watch`).

Known parity gaps (accepted, owner to know):

1. Retry: Python finishes the queue row even when a pass fails and runs again at the next 30-min tick. Go returns an error, so `drain` retries the row after 1, 5, 15 and 30 min (5 attempts, then dead; `RaiseFailed` again, harmless refresh). A failing run therefore re-runs the watchdog and re-pings `/fail` sooner. Watchdog mails stay deduplicated (`at_risk_mailed_at`, digest setting), so no extra mail.
2. Log lines: Go logs the error type only, not the message (house rule for Go jobs); the message is in `job.error` (300 chars). The `job run` line counts `rows` = alerts + requests due instead of Python's per-key `_log_run` fields; the per-pass counts are in the `deadline watch` / `filing watchdog` info lines.
3. Date: `RaiseDSRDueAlerts` gets `at.Local()` (server-local, like `date.today()`); `CheckDeadlines` reads its validation date as UTC. Both are UTC while neither container sets `TZ` (true today).

## Owner steps

After merge and the auto-deploy, only when you choose to switch (one job at a time; `submit` stays as it is):

1. On the server, open `/opt/ubyhost/deploy/lightsail/.env` and add `deadlines` to both `UBYHOST_JOB_QUEUE_KINDS` and `UBYHOST_GO_JOB_KINDS` (comma lists).
2. Deploy:

```bash
cd /opt/ubyhost/deploy/lightsail && ./scripts/deploy.sh
```

3. After 35 minutes, check one Go run and no Python run:

```bash
cd /opt/ubyhost/deploy/lightsail && docker compose logs --since 40m ubyhost-go | grep 'job=deadlines' | tail -3; docker compose logs --since 40m worker | grep 'job=deadlines' | tail -3
```

Expected: a Go line with `ok=1`, nothing from `worker`; the filing heartbeat monitor stays green.

4. Roll back: remove `deadlines` from `UBYHOST_GO_JOB_KINDS` only and run step 2 again.
