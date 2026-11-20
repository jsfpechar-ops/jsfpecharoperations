package main

// Job kind mail: App/app/scheduler.py _job_mail in Go, every 5 minutes
// (docs/plans/go-mail-job.md, task 1236). The seven steps run in Python's
// order. A step that fails is logged and the next step still runs; any
// failure fails the run (job_failed alert, no heartbeat). A clean run pings
// UBYHOST_HEARTBEAT_MAIL_URL. The kind runs only when "mail" is listed in
// UBYHOST_GO_JOB_KINDS.

import (
	"context"
	"errors"
	"log/slog"
	"os"
	"sort"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/lifecyclemail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mailjob"
)

const (
	mailDrainLimit = 8  // mail.drain() in the job and after the reminders
	mailPurgeDays  = 14 // mail.purge_old(14)
)

func init() {
	registerJob("mail", 5, mailHandler)
}

// mailHandler builds the handler. It must not use the pool while building:
// parseGoKinds and the tests call it with a nil pool.
func mailHandler(pool *pgxpool.Pool) jobs.Handler {
	return func(ctx context.Context) (int, error) {
		return runMailJob(ctx, pool, os.Getenv, time.Now())
	}
}

// runMailJob is _job_mail. It returns the sum of the counts _log_run records.
func runMailJob(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now time.Time) (int, error) {
	cfg, cfgErr := mail.ConfigFromEnv(getenv)
	counts := map[string]int{}
	failed := false
	// step runs one Python step: its counts are kept under the keys _log_run
	// records, and a failure is logged and the run goes on.
	step := func(name string, fn func() (map[string]int, error)) {
		got, err := fn()
		if err != nil {
			slog.Error("mail job step failed", "step", name, "error", err.Error())
			failed = true
			return
		}
		for k, v := range got {
			counts[k] = v
		}
	}
	drain := func() (map[string]int, error) {
		if cfgErr != nil {
			return nil, cfgErr
		}
		sum, err := mail.Drain(ctx, pool, cfg, mailDrainLimit)
		return map[string]int{"drain_sent": sum.Sent, "drain_failed": sum.Failed, "drain_skipped": sum.Skipped}, err
	}

	step("expire_holds", func() (map[string]int, error) {
		n, err := mailjob.ExpireHolds(ctx, pool, now)
		return map[string]int{"expire_holds": n}, err
	})
	step("expire_requests", func() (map[string]int, error) {
		n, err := mailjob.ExpireRequests(ctx, pool, now)
		return map[string]int{"expire_requests": n}, err
	})
	step("drain", drain)
	step("reminders", func() (map[string]int, error) {
		// Python's sweep_reminders drains 8 more itself; that drain's counts
		// are not part of the run's items.
		summary, err := mailjob.SweepReminders(ctx, pool, now)
		out := make(map[string]int, len(summary))
		for k, v := range summary {
			out["reminders_"+k] = v
		}
		if err != nil {
			return out, err
		}
		_, err = drain()
		return out, err
	})
	step("fee_updates", func() (map[string]int, error) {
		summary, err := mailjob.SweepFeeUpdates(ctx, pool, now)
		out := make(map[string]int, len(summary))
		for k, v := range summary {
			out["fee_updates_"+k] = v
		}
		return out, err
	})
	step("lifecycle", func() (map[string]int, error) {
		// RunDaily holds the once-a-day gate (UBYHOST_LIFECYCLE_MAIL, mail on,
		// 09:00 Europe/Prague), as Python's run_daily does.
		summary, err := lifecyclemail.RunDaily(ctx, pool, lifecyclemail.ConfigFromEnv(getenv), now)
		out := make(map[string]int, len(summary))
		for k, v := range summary {
			out["lifecycle_"+k] = v
		}
		return out, err
	})
	step("purge", func() (map[string]int, error) {
		n, err := mail.Purge(ctx, pool, now, mailPurgeDays)
		return map[string]int{"purge": n}, err
	})

	total := 0
	for _, v := range counts {
		total += v
	}
	if len(counts) > 0 {
		keys := make([]string, 0, len(counts))
		for k := range counts {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		args := make([]any, 0, 2*len(keys))
		for _, k := range keys {
			args = append(args, k, counts[k])
		}
		slog.Info("mail job run", args...)
	}

	if failed {
		if err := jobs.RaiseFailed(ctx, pool, "mail"); err != nil {
			slog.Warn("mail job_failed alert not raised")
		}
		return total, errors.New("mail job: a step failed")
	}
	jobs.Ping(ctx, getenv("UBYHOST_HEARTBEAT_MAIL_URL"), "mail")
	return total, nil
}
