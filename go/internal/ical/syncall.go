package ical

import (
	"context"
	"log/slog"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

// SyncTotals is what one SyncAll run did: the totals dict of sync_all (icalsync.py 997-1058).
type SyncTotals struct {
	Feeds, Created, Updated, Cancelled, Errors int
	NotModified, Unchanged, Changed            int
}

// syncAllFeedsSQL lists the active feeds of active apartments, the job path of sync_all.
const syncAllFeedsSQL = `SELECT f.id, f.apartment_id, f.url, f.own_name, f.label, f.last_status,
	f.body_sha256, f.etag, f.last_modified
	FROM ical_feed f JOIN apartment a ON a.id = f.apartment_id
	WHERE f.active = 1 AND a.active = 1 ORDER BY f.id`

// SyncAll is sync_all with no arguments (icalsync.py 997-1058), the scheduled job path.
// It syncs every active feed. A feed whose apartment is paused is skipped and not
// counted. A feed that fails is recorded and counted in Errors; the rest still run.
// The last_ical_sync setting is written at the end.
func SyncAll(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, opt FetchOptions) (SyncTotals, error) {
	var t SyncTotals
	rows, err := pool.Query(ctx, syncAllFeedsSQL)
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
	slog.Info("ical_sync_run", "feeds", t.Feeds, "not_modified", t.NotModified,
		"unchanged", t.Unchanged, "changed", t.Changed, "errors", t.Errors)
	return t, nil
}

// importPaused is import_paused (icalsync.py 997-1058, billing.py 140-152): a paused
// plan stops calendar import. The answer is cached per apartment in seen for one run.
// Billing off, no account or no owner means not paused.
func importPaused(ctx context.Context, pool *pgxpool.Pool, billingOn bool, apartmentID int64, seen map[int64]bool) (bool, error) {
	if !billingOn {
		return false, nil
	}
	if v, ok := seen[apartmentID]; ok {
		return v, nil
	}
	var paused bool
	err := pool.QueryRow(ctx,
		`SELECT EXISTS (SELECT 1 FROM apartment a JOIN billing_account b ON b.owner_user_id = a.owner_user_id
		   WHERE a.id = $1 AND b.status = 'paused')`, apartmentID).Scan(&paused)
	if err != nil {
		return false, err
	}
	seen[apartmentID] = paused
	return paused, nil
}

// billingEnabled reads UBYHOST_BILLING_ENABLED as billing.enabled does: 1, true or yes.
func billingEnabled(getenv func(string) string) bool {
	switch strings.ToLower(getenv("UBYHOST_BILLING_ENABLED")) {
	case "1", "true", "yes":
		return true
	}
	return false
}
