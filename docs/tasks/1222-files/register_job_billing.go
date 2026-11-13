package main

// The billing job (brief 1222): billing_jobs.run in Go, once a day. It does
// nothing while UBYHOST_BILLING_ENABLED is off. Hand it to Go by adding billing
// to UBYHOST_GO_JOB_KINDS (it must stay in UBYHOST_JOB_QUEUE_KINDS).

import (
	"context"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)

func init() {
	registerJob("billing", 24*60, billingHandler)
}

// billingHandler builds the handler. It must not use the pool while building:
// parseGoKinds and the tests call it with a nil pool.
func billingHandler(pool *pgxpool.Pool) jobs.Handler {
	return func(ctx context.Context) (int, error) {
		// Python's date.today() is the server's local date, as in the deadlines job.
		runner := &billingjob.Runner{Pool: pool}
		counts, err := runner.Run(ctx, time.Now().Local())
		if counts.Total() > 0 || counts.Errors > 0 {
			slog.Info("billing run", "counts", counts.Map())
		}
		return counts.Total(), err
	}
}
