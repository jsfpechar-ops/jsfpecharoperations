package main

// The door-codes job, as _job_door_codes in App/app/scheduler.py: every 5 minutes it runs
// doorcodes Reconcile, then doorcleaning Reconcile (all owners), then doorcleaning ProcessQueue.
// It is active only when door_codes is in UBYHOST_GO_JOB_KINDS. It does nothing while
// UBYHOST_DOOR_CODES is off (config.py DOOR_CODES_ENABLED reads that name). Any failure returns an
// error, and jobs.Run records job_failed as Python's _job_failed does.

import (
	"context"
	"log/slog"
	"os"
	"sync"

	"github.com/jackc/pgx/v5/pgxpool"

	doorcleaning "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes/cleaning"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)

func init() {
	registerJob("door_codes", 5, doorCodesHandler)
}

// doorCodesOn reads a Python-style switch: "1", "true" or "yes" is on (config.py).
func doorCodesOn(v string) bool {
	return v == "1" || v == "true" || v == "yes"
}

// doorCodesHandler builds the handler. It must not use the pool or the network while building:
// goHandlers(nil) (parseGoKinds and the tests) calls it with a nil pool. The wiring is built on
// the first run that is switched on.
func doorCodesHandler(pool *pgxpool.Pool) jobs.Handler {
	var once sync.Once
	var job *doorCodesJob
	var setupErr error
	return func(ctx context.Context) (int, error) {
		if !doorCodesOn(os.Getenv("UBYHOST_DOOR_CODES")) {
			return 0, nil
		}
		once.Do(func() { job, setupErr = newDoorCodesJob(pool) })
		if setupErr != nil {
			return 0, setupErr
		}
		return job.run(ctx)
	}
}

// run is the three steps of _job_door_codes, in order. The returned count is the sum of what
// Python logs: the reconcile counts, the cleaner events and the cleaner queue changes.
func (j *doorCodesJob) run(ctx context.Context) (int, error) {
	counts, err := j.rec.Reconcile(ctx)
	if err != nil {
		return 0, err
	}
	events, err := doorcleaning.Reconcile(ctx, j.pool, j.clock)
	if err != nil {
		return 0, err
	}
	codes, err := doorcleaning.ProcessQueue(ctx, j.pool, j.cleanQ)
	if err != nil {
		return 0, err
	}
	total := counts.Total() + events + codes
	if total > 0 {
		slog.Info("door codes", "counts", counts, "cleaning_events", events, "cleaning_codes", codes)
	}
	return total, nil
}
