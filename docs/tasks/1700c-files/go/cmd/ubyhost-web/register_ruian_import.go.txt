package main

// Brief 1700c: the monthly ČÚZK address import (go/internal/ruian). A background
// task, not a job-queue kind, so the Python-locked scheduler plan stays as it is.
// It is dormant until UBYHOST_RUIAN_IMPORT=1 (and UBYHOST_RUIAN_ENABLED is not 0).
// Five minutes after start and then every six hours it asks Run, which returns
// at once when the newest published month is already loaded and the table is
// not empty (one HEAD request and one query). A failed run is logged and tried
// again at the next tick.

import (
	"context"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ruian"
)

func init() { registerBackground("ruian_import", ruianImportTask) }

// ruianImportEnabled reads the two switches.
func ruianImportEnabled(getenv func(string) string) bool {
	return strings.TrimSpace(getenv("UBYHOST_RUIAN_IMPORT")) == "1" &&
		strings.TrimSpace(getenv("UBYHOST_RUIAN_ENABLED")) != "0" && !killSwitch(getenv)
}

func ruianImportTask(pool *pgxpool.Pool) (func(context.Context), error) {
	if !ruianImportEnabled(os.Getenv) {
		return nil, nil
	}
	data := os.Getenv("UBYHOST_DATA_DIR")
	if data == "" {
		data = "/data"
	}
	opts := ruian.Options{BaseURL: ruian.DefaultBaseURL, Dir: filepath.Join(data, "ruian"), MinRows: ruian.ProductionMinRows}
	return func(ctx context.Context) {
		wait := 5 * time.Minute
		for {
			t := time.NewTimer(wait)
			select {
			case <-ctx.Done():
				t.Stop()
				return
			case <-t.C:
			}
			n, err := ruian.Run(ctx, pool, opts)
			if err != nil && ctx.Err() == nil {
				slog.Error("ruian import failed", "error", err.Error())
			} else if n > 0 {
				slog.Info("ruian import done", "rows", n)
			}
			wait = 6 * time.Hour
		}
	}, nil
}
