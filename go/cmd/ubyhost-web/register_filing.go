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
