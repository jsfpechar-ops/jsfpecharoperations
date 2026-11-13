package main

// Job kind guide_import (Python scheduler interval: 60 minutes). It runs only
// when the kind is listed in UBYHOST_GO_JOB_KINDS (and UBYHOST_JOB_QUEUE_KINDS);
// otherwise this registration only makes the name valid. The factory does not
// touch the pool or the network while building.

import (
	"context"
	"os"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guideimport"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
)

func init() {
	registerJob("guide_import", 60, func(pool *pgxpool.Pool) jobs.Handler {
		ai := anthropic.NewService(pool, anthropic.ConfigFromEnv(os.LookupEnv))
		job := guideimport.New(pool, guideimport.ConfigFromEnv(os.LookupEnv), ai)
		return func(ctx context.Context) (int, error) { return job.Run(ctx) }
	})
}
