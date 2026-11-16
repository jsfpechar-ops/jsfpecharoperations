package main

// Brief 1816: the Go twin of App/app/jobqueue.py purge(). Housekeeping, not a
// queued job (it must not write job rows itself). It runs one minute after
// start and then every hour until the context ends. A failed run is logged
// and tried again next hour.

import (
	"context"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)

func init() { registerBackground("job_purge", jobPurgeTask) }

func jobPurgeTask(pool *pgxpool.Pool) (func(context.Context), error) {
	return func(ctx context.Context) {
		wait := time.Minute
		for {
			t := time.NewTimer(wait)
			select {
			case <-ctx.Done():
				t.Stop()
				return
			case <-t.C:
			}
			if _, err := jobs.Purge(ctx, pool); err != nil && ctx.Err() == nil {
				slog.Warn("job purge failed", "error", err.Error())
			}
			wait = time.Hour
		}
	}, nil
}
