package main

// The door-codes job: doorcodes.Reconciler, every 5 minutes, as _job_door_codes in
// App/app/scheduler.py. It is active only when door_codes is in UBYHOST_GO_JOB_KINDS. It does
// nothing while UBYHOST_DOOR_CODES is off (config.py DOOR_CODES_ENABLED reads that name, not
// UBYHOST_DOOR_CODES_ENABLED). The run log and job_ok or job_failed are kept by jobs.Run.
// The cleaning steps that _job_door_codes also runs are not part of this job.

import (
	"context"
	"log/slog"
	"os"
	"sync"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
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
	var rec *doorcodes.Reconciler
	var setupErr error
	return func(ctx context.Context) (int, error) {
		if !doorCodesOn(os.Getenv("UBYHOST_DOOR_CODES")) {
			return 0, nil
		}
		once.Do(func() { rec, setupErr = newDoorCodesReconciler(pool) })
		if setupErr != nil {
			return 0, setupErr
		}
		counts, err := rec.Reconcile(ctx)
		if counts.Total() > 0 {
			slog.Info("door codes", "counts", counts)
		}
		return counts.Total(), err
	}
}
