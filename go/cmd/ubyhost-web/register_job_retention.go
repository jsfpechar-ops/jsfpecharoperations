package main

// Job kind retention: App/app/scheduler.py _job_retention in Go
// (go/internal/retention). A dry run unless UBYHOST_RETENTION_AUTOPURGE and
// UBYHOST_GO_RETENTION_APPLY are both on. Brief 1210.

import (
	"context"
	"log/slog"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/retention"
)

func init() {
	registerJob("retention", 24*60, retentionHandler)
}

// retentionHandler builds the handler without touching the pool. A failed
// run raises the job_failed alert at once, as Python's _job_failed does, and
// returns the error so the queue records no success. Counts only in the log.
func retentionHandler(pool *pgxpool.Pool) jobs.Handler {
	return func(ctx context.Context) (int, error) {
		cfg, err := retention.ConfigFromEnv(os.LookupEnv)
		if err == nil {
			now := time.Now()
			// Python's date.today() is the server's local date.
			var sum retention.Summary
			sum, err = retention.Run(ctx, pool, cfg, now.Local(), now, nil)
			if err == nil {
				if sum.Total() > 0 {
					args := []any{"dry_run", sum.DryRun}
					for _, c := range sum.Counts {
						args = append(args, c.Name, c.Count)
					}
					slog.Info("retention run", args...)
				}
				return sum.Total(), nil
			}
		}
		if raiseErr := jobs.RaiseFailed(ctx, pool, "retention"); raiseErr != nil {
			slog.Warn("retention job_failed alert not raised")
		}
		return 0, err
	}
}
