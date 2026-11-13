package main

// Lane J1 (brief 1209/1209b): the photo_sweep job, off until an operator adds
// photo_sweep to UBYHOST_GO_JOB_KINDS. Interval as scheduler.job_intervals().

import (
	"context"
	"log/slog"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/jobs"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/photosweep"
)

func init() {
	registerJob("photo_sweep", 12*60, func(pool *pgxpool.Pool) jobs.Handler {
		return func(ctx context.Context) (int, error) {
			sum, err := photosweep.Run(ctx, pool, os.Getenv("UBYHOST_DATA_DIR"), time.Now())
			if err == nil {
				slog.Info("photo sweep", "photos", sum.Photos, "guide_orphans", sum.GuideOrphans,
					"payloads", sum.Payloads, "drafts", sum.Drafts,
					"unverified_deleted", sum.Signup.UnverifiedDeleted,
					"click_ids_cleared", sum.Signup.ClickIDsCleared,
					"meta_events_expired", sum.Signup.MetaEventsExpired)
			}
			// Python's _log_run counts photos and payloads; the same here.
			return sum.Photos + sum.Payloads, err
		}
	})
}
