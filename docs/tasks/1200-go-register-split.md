# 1200: Split Go job and route registration into one file per lane

Status: todo
Depends on: none | Base commit: 29f86658 | Branch: task/1200-go-register-split
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Pure refactor, no behaviour change: move job and route registration out of `go/cmd/ubyhost-web/main.go` into one file per migration lane (J=jobs, D=schema, W=web, F=filing) so parallel lanes never edit `main.go` again. One small visible change: `jobNames` in `go/internal/jobs/queue.go` gains the 9 missing kinds, so the job_failed alert for posthog and meta_capi shows the English name from `App/app/host_i18n.py` instead of the raw kind.

## 2. Context

Rules: AGENTS.md rule 1 (filing correctness): the `submit` handler and the schema check move verbatim, not edited. Rule 2: no new outbound request. Routes registered, their order, and every log message stay identical.

Excerpts that must exist verbatim (else STOP, §8):
- `go/cmd/ubyhost-web/main.go` has `func goHandlers(pool *pgxpool.Pool) map[string]jobs.Handler {` at line 258, `var goIntervals = map[string]int{` at line 255, the `startCtx, cancelStart := context.WithTimeout(ctx, 10*time.Second)` block at lines 170-187, and `mux.Handle("POST /webhooks/stripe"` at line 210 through `mux.Handle("GET /pay/{id}/{file}"` at line 226.
- `go/internal/jobs/queue.go` has `var jobNames = map[string]string{"billing_snapshot": "billing snapshot",` at line 116.

Pre-step evidence for acceptance (§6): save the route list from the base commit first.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/cmd/ubyhost-web/main.go | edit | remove moved code, add merge helpers, call registerWeb/registerFiling/checkSchema |
| go/cmd/ubyhost-web/main_test.go | edit | add 2 tests, keep the rest |
| go/cmd/ubyhost-web/register_jobs.go | create | lane J: jobIntervals, jobHandlers |
| go/cmd/ubyhost-web/register_filing.go | create | lane F: filingIntervals, filingHandlers, registerFiling |
| go/cmd/ubyhost-web/register_web.go | create | lane W: registerWeb |
| go/cmd/ubyhost-web/register_schema.go | create | lane D: checkSchema |
| go/internal/jobs/queue.go | edit | jobNames lists all 15 kinds |
| go/internal/jobs/queue_test.go | edit | add TestJobNamesCoverAllKinds |

No other file may change.

## 4. Steps

Work from `/home/user/jsfpecharoperations`. Use bash heredocs (`cat > file <<'EOF'`) for new files.

### Step 0. Save the base route list

```bash
git show 29f86658:go/cmd/ubyhost-web/main.go | grep -ho 'mux.Handle("[^"]*"' | sort > /tmp/routes_before.txt; wc -l /tmp/routes_before.txt
```
Expected: 20 lines.

### Step 1. Create go/cmd/ubyhost-web/register_jobs.go

```go
package main

// Lane J (jobs) owns this file: add a Go job here, and only here.
// Interval and handler of one kind live together; kinds must not appear in
// register_filing.go (TestLaneKindsDisjoint).

import (
	"context"
	"log/slog"
	"net"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/metacapi"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/posthog"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pushsend"
)

// jobIntervals are the schedule intervals (minutes) that cap a retry backoff.
var jobIntervals = map[string]int{"billing_snapshot": 24 * 60, "stripe_sweep": 24 * 60, "ical": 60, "push": 1, "posthog": 15, "meta_capi": 10, "deadlines": 30}

// jobHandlers maps each lane-J job kind to its handler.
func jobHandlers(pool *pgxpool.Pool) map[string]jobs.Handler {
	return map[string]jobs.Handler{
		"billing_snapshot": func(ctx context.Context) (int, error) {
			return billing.WriteMonthSnapshot(ctx, pool, time.Now().UTC().Format("2006-01"), jobs.Now(0))
		},
		"stripe_sweep": func(ctx context.Context) (int, error) {
			expired, deleted, err := payments.Sweep(ctx, pool, time.Now().UTC(), jobs.Now(0))
			return expired + deleted, err
		},
		"ical": func(ctx context.Context) (int, error) {
			totals, err := ical.SyncAll(ctx, pool, os.Getenv, ical.FetchOptions{
				Resolver:     net.DefaultResolver,
				AllowPrivate: ical.AllowPrivate(os.Getenv),
			})
			if err == nil {
				jobs.Ping(ctx, os.Getenv("UBYHOST_HEARTBEAT_ICAL_URL"), "ical")
			}
			return totals.Feeds, err
		},
		"push": func(ctx context.Context) (int, error) {
			counts, err := (&pushsend.Sender{Pool: pool, Getenv: os.Getenv, Now: time.Now}).Drain(ctx, 50)
			total := 0
			for _, n := range counts {
				total += n
			}
			return total, err
		},
		"posthog": func(ctx context.Context) (int, error) {
			counts, err := posthog.Sync(ctx, pool, posthog.ConfigFromEnv(os.LookupEnv), nil, time.Now())
			if counts.Sent > 0 || counts.Failed > 0 {
				slog.Info("posthog sync", "sent", counts.Sent, "skipped", counts.Skipped, "failed", counts.Failed)
			}
			return counts.Sent, err
		},
		"meta_capi": func(ctx context.Context) (int, error) {
			sum, err := metacapi.Send(ctx, pool, metacapi.ConfigFromEnv(os.LookupEnv), nil, time.Now())
			if sum != (metacapi.Summary{}) {
				slog.Info("meta conversions", "sent", sum.Sent, "retry", sum.Retry, "failed", sum.Failed, "expired", sum.Expired)
			}
			return sum.Sent, err
		},
		"deadlines": func(ctx context.Context) (int, error) {
			sum, err := calendar.RunDeadlinesJob(ctx, pool, os.LookupEnv, time.Now(), func(url string) {
				jobs.Ping(ctx, url, "filing")
			})
			return sum.Alerts + sum.RequestsDue, err
		},
	}
}
```

### Step 2. Create go/cmd/ubyhost-web/register_filing.go

```go
package main

// Lane F (filing) owns this file: filing jobs and filing routes. Filing
// correctness beats every other feature (AGENTS.md rule 1).

import (
	"context"
	"log/slog"
	"net/http"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// filingIntervals are the schedule intervals (minutes) of the filing jobs.
var filingIntervals = map[string]int{"submit": 10}

// filingHandlers maps each lane-F job kind to its handler.
func filingHandlers(pool *pgxpool.Pool) map[string]jobs.Handler {
	return map[string]jobs.Handler{
		"submit": func(ctx context.Context) (int, error) {
			keys, err := secure.LoadDataKeys(os.Getenv)
			if err != nil {
				return 0, err
			}
			d, err := ubyport.NewSweepDeps(ctx, pool, keys, os.Getenv)
			if err != nil {
				return 0, err
			}
			summary, err := ubyport.Sweep(ctx, d, nil)
			if summary.Submitted > 0 || summary.Failed > 0 {
				slog.Info("ubyport sweep", "apartments", summary.Apartments, "submitted", summary.Submitted, "failed", summary.Failed)
			}
			if err == nil {
				jobs.Ping(ctx, os.Getenv("UBYHOST_HEARTBEAT_URL"), "submit")
			}
			return summary.Submitted, err
		},
	}
}

// registerFiling registers the filing routes. None yet.
func registerFiling(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {}
```

### Step 3. Create go/cmd/ubyhost-web/register_web.go

The 17 `mux.Handle` lines are copied unchanged, same order, from main.go lines 210-226.

```go
package main

// Lane W (web) owns this file: add a web route here, and only here.
// /healthz, /metrics and the "/" catch-all stay in main.go.

import (
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/palette"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/payments"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pushsend"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/pushweb"
)

// registerWeb registers the web routes on mux.
func registerWeb(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	mux.Handle("POST /webhooks/stripe", m.wrap("/webhooks/stripe", payments.WebhookHandler(pool, os.Getenv, time.Now)))
	onboarder := payments.NewStripeOnboarder(pool, os.Getenv, time.Now)
	mux.Handle("GET /payments/connect/start", m.wrap("/payments/connect/start", payments.ConnectStartHandler(pool, os.Getenv, time.Now, onboarder)))
	mux.Handle("POST /payments/connect/start", m.wrap("/payments/connect/start", payments.ConnectStartHandler(pool, os.Getenv, time.Now, onboarder)))
	mux.Handle("GET /payments/connect/return", m.wrap("/payments/connect/return", payments.ConnectReturnHandler(pool, os.Getenv, time.Now, onboarder)))
	mux.Handle("POST /account/push/subscribe", m.wrap("/account/push/subscribe", pushweb.SubscribeHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /account/push/refresh", m.wrap("/account/push/refresh", pushweb.RefreshHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /account/push/unsubscribe", m.wrap("/account/push/unsubscribe", pushweb.UnsubscribeHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /account/push/devices/{id}/delete", m.wrap("/account/push/devices/{id}/delete", pushweb.DeviceDeleteHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /account/push/test", m.wrap("/account/push/test", pushweb.TestHandler(&pushsend.Sender{Pool: pool, Getenv: os.Getenv, Now: time.Now}, os.Getenv, time.Now)))
	mux.Handle("GET /api/command-palette", m.wrap("/api/command-palette", palette.Handler(pool, os.Getenv, time.Now)))
	mux.Handle("GET /dashboard/calendar", m.wrap("/dashboard/calendar", calendar.Handler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /payments/requests/new", m.wrap("/payments/requests/new", payments.RequestNewHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /payments/requests/{id}/send", m.wrap("/payments/requests/{id}/send", payments.RequestSendHandler(pool, os.Getenv, time.Now, onboarder)))
	mux.Handle("GET /payments/qr/{file}", m.wrap("/payments/qr/{file}", payments.QRPNGHandler(pool, os.Getenv, time.Now)))
	mux.Handle("POST /payments/requests/{id}/link", m.wrap("/payments/requests/{id}/link", payments.RequestLinkHandler(pool, os.Getenv, time.Now, onboarder)))
	mux.Handle("GET /pay/{id}/{file}", m.wrap("/pay/{id}/{file}", payments.GuestQRPNGHandler(pool, os.Getenv)))
}
```

### Step 4. Create go/cmd/ubyhost-web/register_schema.go

```go
package main

// Lane D (schema) owns this file: the startup schema check.

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/schema"
)

// checkSchema refuses to start while goose files are pending. It logs the
// reason itself and returns a non-nil error, so run() returns 1.
func checkSchema(ctx context.Context, dbURL, migrations string, redact func(error) string) error {
	startCtx, cancelStart := context.WithTimeout(ctx, 10*time.Second)
	conn, err := pgx.Connect(startCtx, dbURL)
	if err != nil {
		cancelStart()
		slog.Error("database connect failed", "error", redact(err))
		return err
	}
	pending, err := schema.Pending(startCtx, conn, migrations)
	_ = conn.Close(startCtx)
	cancelStart()
	if err != nil {
		slog.Error("goose check failed", "error", redact(err))
		return err
	}
	if len(pending) > 0 {
		err := fmt.Errorf("goose files pending: %v", pending)
		slog.Error(err.Error())
		return err
	}
	return nil
}
```

### Step 5. Edit go/cmd/ubyhost-web/main.go

5a. Replace the whole import block (lines 4-36) with:

```go
import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"sort"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)
```

5b. In `run()`, replace lines 170-187 (from `startCtx, cancelStart := ...` through the closing brace of `if len(pending) > 0 {...}`) with:

```go
	if err := checkSchema(ctx, dbURL, migrations, redact); err != nil {
		return 1
	}
```

5c. In `run()`, delete lines 210-226 (every `mux.Handle("POST /webhooks/stripe"` ... through `mux.Handle("GET /pay/{id}/{file}"` line, including the `onboarder :=` line) and replace them with:

```go
	registerWeb(mux, m, pool)
	registerFiling(mux, m, pool)
```
so the order is: /healthz, /metrics, registerWeb, registerFiling, then `mux.Handle("/", m.wrap("/", notFound))`.

5d. Replace everything from the comment `// goIntervals are the schedule intervals` (line 254) through the end of `goHandlers` (line 324, the `}` after `return map...{ ... }`) with:

```go
// goIntervals are the schedule intervals (minutes) that cap a retry backoff.
// Each lane owns its own map: register_jobs.go, register_filing.go.
var goIntervals = mergeIntervals(jobIntervals, filingIntervals)

// goHandlers maps each Go-owned job kind to its handler, merged from the
// lane files.
func goHandlers(pool *pgxpool.Pool) map[string]jobs.Handler {
	out := map[string]jobs.Handler{}
	for _, part := range []map[string]jobs.Handler{jobHandlers(pool), filingHandlers(pool)} {
		for k, h := range part {
			if _, dup := out[k]; dup {
				panic("duplicate job kind in lane files: " + k)
			}
			out[k] = h
		}
	}
	return out
}

// mergeIntervals joins the lane interval maps; a duplicate kind is a
// programmer error.
func mergeIntervals(parts ...map[string]int) map[string]int {
	out := map[string]int{}
	for _, part := range parts {
		for k, v := range part {
			if _, dup := out[k]; dup {
				panic("duplicate job interval in lane files: " + k)
			}
			out[k] = v
		}
	}
	return out
}
```
Leave `parseGoKinds` unchanged.

### Step 6. Edit go/cmd/ubyhost-web/main_test.go

Append at the end of the file (existing imports `net/http`, `net/http/httptest`, `os`, `strings`, `testing` stay; add nothing):

```go
func TestLaneKindsDisjoint(t *testing.T) {
	filing := filingHandlers(nil)
	for k := range jobHandlers(nil) {
		if _, ok := filing[k]; ok {
			t.Errorf("kind %q is in both register_jobs.go and register_filing.go", k)
		}
	}
}

func TestEveryHandlerHasInterval(t *testing.T) {
	handlers := goHandlers(nil)
	for k := range handlers {
		if goIntervals[k] <= 0 {
			t.Errorf("handler %q has no interval > 0", k)
		}
	}
	for k := range goIntervals {
		if _, ok := handlers[k]; !ok {
			t.Errorf("interval %q has no handler", k)
		}
	}
}
```

### Step 7. Edit go/internal/jobs/queue.go

Replace the two-line `var jobNames = map[string]string{ ... }` (starts line 116, ends with `"deadlines": "deadline watch"}`) with:

```go
// jobNames are the English notification.job_name.* values of
// App/app/host_i18n.py, one per job kind.
var jobNames = map[string]string{
	"billing_snapshot": "billing snapshot",
	"stripe_sweep":     "payment check",
	"ical":             "calendar sync",
	"submit":           "automatic filing",
	"push":             "urgent alerts",
	"deadlines":        "deadline watch",
	"posthog":          "product analytics",
	"meta_capi":        "Meta conversion sending",
	"mail":             "e-mail queue",
	"photo_sweep":      "passport photo cleanup",
	"retention":        "data retention",
	"stay_fee_mail":    "monthly stay fee email",
	"billing":          "billing",
	"door_codes":       "door codes",
	"guide_import":     "guest guide imports",
}
```
`jobLevels` stays unchanged.

### Step 8. Edit go/internal/jobs/queue_test.go

Run `head -20 go/internal/jobs/queue_test.go` first: the package is `jobs` (internal test, so `jobNames` is reachable) and `testing` is imported. Append (no DB, no testPool):

```go
func TestJobNamesCoverAllKinds(t *testing.T) {
	kinds := []string{"billing_snapshot", "stripe_sweep", "ical", "submit", "push", "deadlines", "posthog", "meta_capi",
		"mail", "photo_sweep", "retention", "stay_fee_mail", "billing", "door_codes", "guide_import"}
	for _, k := range kinds {
		if jobNames[k] == "" {
			t.Errorf("jobNames has no entry for %q", k)
		}
	}
	if len(jobNames) != len(kinds) {
		t.Errorf("jobNames has %d entries, want %d", len(jobNames), len(kinds))
	}
}
```

### Step 9. Verify names against host_i18n.py

```bash
cd App/app && for k in billing_snapshot stripe_sweep ical submit push deadlines posthog meta_capi mail photo_sweep retention stay_fee_mail billing door_codes guide_import; do grep -m1 "\"notification.job_name.$k\":" host_i18n.py; done | tail -30
```
Expected: 15 lines, the first (English) occurrence of each; values match Step 7. If any differs, STOP.

## 5. Do not touch

Everything outside §3. Especially `App/` (read-only here, grep only) and anything about the Python deadlines (another thread removes those). Do not edit the body of the `submit` handler, the schema check messages, or `jobLevels`. No new dependency (rule 4).

## 6. Commands

From `go/`:
```bash
gofmt -l ./cmd ./internal/jobs
go vet ./... 2>&1 | tail -30
go test ./cmd/ubyhost-web/ ./internal/jobs/ -count=1 2>&1 | tail -30
```
Expected: gofmt prints nothing; vet prints nothing; tests `ok` (DB tests may skip without `UBYHOST_TEST_DATABASE_URL`; that is fine). If `gofmt -l` lists a file, run `gofmt -w` on only that file. From the repo root:
```bash
grep -ho 'mux.Handle("[^"]*"' go/cmd/ubyhost-web/*.go | grep -v _test | sort > /tmp/routes_after.txt; diff /tmp/routes_before.txt /tmp/routes_after.txt && echo SAME_ROUTES
git diff --stat | tail -30; git status --short | tail -30
```
Test-map row: Go (`go/`). No Python tests.

## 7. Acceptance

- [ ] `gofmt -l ./cmd ./internal/jobs` prints nothing; `go vet ./...` clean.
- [ ] `go test ./cmd/ubyhost-web/ ./internal/jobs/ -count=1` is ok, including TestLaneKindsDisjoint, TestEveryHandlerHasInterval, TestJobNamesCoverAllKinds and the unchanged older tests.
- [ ] The diff command in §6 prints `SAME_ROUTES` (20 patterns before and after).
- [ ] `git diff --stat` plus `git status --short` show only the 8 §3 files (4 new register_*.go untracked).
- [ ] `grep -c 'mux.Handle' go/cmd/ubyhost-web/main.go` is 3 (healthz, metrics, "/").
- [ ] `main.go` no longer imports pgx, schema, billing, calendar, ical, metacapi, palette, payments, posthog, pushsend, pushweb, secure, ubyport, or net.
- [ ] Step 9 output matches the names in `jobNames`.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear (for example a compile error about an unused or missing import: fix only imports inside the file you are editing, and say so in the report);
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1200-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the diff of: `go/cmd/ubyhost-web/main.go`, `go/cmd/ubyhost-web/register_schema.go` (log messages and exit-1 behaviour identical), `go/cmd/ubyhost-web/register_filing.go` (submit handler byte-identical to the old goHandlers entry).

## Owner steps

1. Merge the PR once CI is green. Nothing else.
