package jobs

import (
	"context"
	"log/slog"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	// KeepDoneDays and KeepDeadDays: how long a finished or a dead row stays.
	KeepDoneDays = 7
	KeepDeadDays = 30
	// PurgeBatch rows per DELETE. Each batch is its own short transaction, so
	// no lock is held across batches and a claim is never kept waiting.
	PurgeBatch = 500
	// purgeMaxBatches caps one call (500 x 100 = 50,000 rows); the next hourly run continues.
	purgeMaxBatches = 100
)

// Open rows (done_at and dead_at both NULL) are never selected. SKIP LOCKED
// leaves any row another session holds for the next run.
const purgeDoneSQL = `
	DELETE FROM job WHERE id IN (
		SELECT id FROM job
		WHERE done_at IS NOT NULL AND done_at < $1
		ORDER BY id LIMIT $2
		FOR UPDATE SKIP LOCKED)`

const purgeDeadSQL = `
	DELETE FROM job WHERE id IN (
		SELECT id FROM job
		WHERE dead_at IS NOT NULL AND dead_at < $1
		ORDER BY id LIMIT $2
		FOR UPDATE SKIP LOCKED)`

// Purge deletes done rows older than KeepDoneDays and dead rows older than
// KeepDeadDays, PurgeBatch at a time, and returns the rows removed.
func Purge(ctx context.Context, pool *pgxpool.Pool) (int64, error) {
	var total int64
	for _, q := range []struct {
		sql  string
		days int
	}{{purgeDoneSQL, KeepDoneDays}, {purgeDeadSQL, KeepDeadDays}} {
		cutoff := Now(-time.Duration(q.days) * 24 * time.Hour)
		for i := 0; i < purgeMaxBatches; i++ {
			tag, err := pool.Exec(ctx, q.sql, cutoff, PurgeBatch)
			if err != nil {
				return total, err
			}
			total += tag.RowsAffected()
			if tag.RowsAffected() < PurgeBatch {
				break
			}
		}
	}
	if total > 0 {
		slog.Info("job purge", "removed", total)
	}
	return total, nil
}
