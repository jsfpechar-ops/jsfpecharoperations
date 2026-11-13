package photosweep

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/deadlines"
)

// Summary holds the counts of one sweep, one field per step.
type Summary struct {
	Photos       int // passport_photos.purge_stale
	GuideOrphans int // guide_photos.purge_orphans
	Payloads     int // reporting.purge_submission_payloads
	Drafts       int // guest_draft.purge
	Signup       SignupCounts
}

// clock is the time of one run as each Python step reads it: now for every
// datetime.now(timezone.utc), today for passport_photos' date.today() (the
// server's local date) and pragueToday for claim.prague_today().
type clock struct {
	now         time.Time
	today       time.Time
	pragueToday string
}

// Run is scheduler._job_photo_sweep for the Go job queue. dataDir is
// UBYHOST_DATA_DIR; it must be writable, or the first file to delete fails the
// job. The steps run in Python's order and the first error stops the run and
// is returned, as Python's single try does.
func Run(ctx context.Context, pool *pgxpool.Pool, dataDir string, now time.Time) (Summary, error) {
	if dataDir == "" {
		return Summary{}, errors.New("photo sweep: UBYHOST_DATA_DIR is not set")
	}
	return run(ctx, pool, dataDir, clock{
		now:         now,
		today:       now.Local(),
		pragueToday: deadlines.LocalNow(now).Format("2006-01-02"),
	})
}

func run(ctx context.Context, pool *pgxpool.Pool, dataDir string, c clock) (Summary, error) {
	var s Summary
	var err error
	if s.Photos, err = purgePassportPhotos(ctx, pool, dataDir, c.today, c.now); err != nil {
		return s, err
	}
	if s.GuideOrphans, err = purgeGuideOrphans(ctx, pool, dataDir, c.now); err != nil {
		return s, err
	}
	if s.Payloads, err = purgeSubmissionPayloads(ctx, pool, c.now); err != nil {
		return s, err
	}
	if s.Drafts, err = purgeGuestDrafts(ctx, pool, c.now, c.pragueToday); err != nil {
		return s, err
	}
	if s.Signup, err = purgeSignups(ctx, pool, c.now); err != nil {
		return s, err
	}
	return s, nil
}
