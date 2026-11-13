package main

// Thread "Move scheduler to Go" (plan step J7) owns this file. With
// UBYHOST_SCHEDULER=go the Go service enqueues every job kind on the schedule
// of App/app/scheduler.py (go/internal/scheduler); with any other value it
// does nothing and Python's APScheduler keeps enqueuing.
//
// It runs as a background task (registerBackground, brief 1452): started once
// after the schema check, stopped on SIGINT or SIGTERM and joined before the
// pool closes. A set-up error does not stop the service, which serves live
// pages: it is logged as "background task not started task=scheduler", and
// Python refuses the same configuration, so the Python worker keeps
// enqueuing. If Go stops enqueuing for any other reason while the switch is
// on, the Python worker's watch enqueues the missing kinds and raises the
// critical job_failed:job_queue alert (App/app/scheduler.py).

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/scheduler"
)

func init() { registerBackground("scheduler", schedulerTask) }

// schedulerTask reads the switch and the plan; it does not touch the pool.
func schedulerTask(pool *pgxpool.Pool) (func(context.Context), error) {
	if !scheduler.Enabled(os.Getenv) {
		return nil, nil
	}
	plan, loc, err := scheduler.Setup(os.LookupEnv)
	if err != nil {
		return nil, fmt.Errorf("UBYHOST_SCHEDULER=go is ignored, the Python worker keeps enqueuing: %w", err)
	}
	state := scheduler.NewState(plan, loc, time.Now())
	enqueue := func(ctx context.Context, kind string) (bool, error) {
		return scheduler.Enqueue(ctx, pool, kind)
	}
	return func(ctx context.Context) {
		scheduler.Run(ctx, state, enqueue, time.Now)
	}, nil
}
