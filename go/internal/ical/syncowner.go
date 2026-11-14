package ical

import (
	"context"
	"log/slog"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// syncOwnerFeedsSQL is the owner branch of sync_all (icalsync.py 1240-1254):
// active feeds of the owner's active apartments.
const syncOwnerFeedsSQL = `SELECT f.id, f.apartment_id, f.url, f.own_name, f.label, f.last_status,
	f.body_sha256, f.etag, f.last_modified
	FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id
	WHERE f.active = 1 AND a.active = 1 AND a.owner_user_id = $1 ORDER BY f.id`

// SyncOwner is sync_all(owner_user_id=owner), the "Sync now" button (brief 1521).
// It is SyncAll limited to one workspace: the same per-feed steps, totals and
// the last_ical_sync setting. SyncAll itself is the scheduled job and is not
// touched.
func SyncOwner(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, opt FetchOptions, owner int64) (SyncTotals, error) {
	var t SyncTotals
	rows, err := pool.Query(ctx, syncOwnerFeedsSQL, owner)
	if err != nil {
		return t, err
	}
	var feeds []Feed
	for rows.Next() {
		var f Feed
		if err := rows.Scan(&f.ID, &f.ApartmentID, &f.URL, &f.OwnName, &f.Label, &f.LastStatus,
			&f.BodySHA256, &f.ETag, &f.LastModified); err != nil {
			rows.Close()
			return t, err
		}
		feeds = append(feeds, f)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return t, err
	}
	billingOn := billingEnabled(getenv)
	paused := map[int64]bool{}
	for _, feed := range feeds {
		isPaused, err := importPaused(ctx, pool, billingOn, feed.ApartmentID, paused)
		if err != nil {
			return t, err
		}
		if isPaused {
			continue
		}
		t.Feeds++
		stats, err := SyncFeed(ctx, pool, getenv, feed, opt, nil)
		if err != nil {
			slog.Error("ical feed failed", "feed", feed.ID, "err", err)
			if rerr := recordFeedFailure(ctx, pool, feed, err); rerr != nil {
				slog.Error("ical feed failure not recorded", "feed", feed.ID, "err", rerr)
			}
			stats.Error = err.Error()
		}
		if stats.Error != "" {
			t.Errors++
			continue
		}
		t.Created += stats.Created
		t.Updated += stats.Updated
		t.Cancelled += stats.Cancelled
		switch stats.Outcome {
		case "not_modified":
			t.NotModified++
		case "unchanged":
			t.Unchanged++
		default:
			t.Changed++
		}
	}
	if _, err := pool.Exec(ctx,
		"INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
		"last_ical_sync", ubyport.UTCNow()); err != nil {
		return t, err
	}
	slog.Info("ical_sync_run", "owner", owner, "feeds", t.Feeds, "not_modified", t.NotModified,
		"unchanged", t.Unchanged, "changed", t.Changed, "errors", t.Errors)
	return t, nil
}
