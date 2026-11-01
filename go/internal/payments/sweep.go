// Package payments holds the Go port of the stripe_sweep job. It makes no
// outbound call: it expires overdue payment requests and prunes old webhook
// dedupe rows, writing the same rows and audit lines as the Python job.
package payments

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

const selectOverdueSQL = `SELECT id, owner_user_id, status FROM payment_request
	WHERE status IN ('sent', 'awaiting_payment') AND expires_at < $1 ORDER BY id`

const expireSQL = `UPDATE payment_request SET status = 'expired', paid_at = COALESCE(NULL, paid_at),
	updated_at = $1 WHERE id = $2 AND status = $3`

const insertAuditSQL = `INSERT INTO audit (at, actor, action, detail, owner_user_id)
	VALUES ($1, 'host', $2, $3, $4)`

const pruneSQL = `DELETE FROM stripe_webhook_event WHERE created_at < $1`

type overdue struct {
	id      int64
	owner   int64
	current string
}

// Sweep expires overdue payment requests and prunes webhook events older than
// 30 days, in one transaction. today is the UTC date; now is the updated_at
// and audit stamp. It returns the number of requests selected as expired and
// the number of webhook rows deleted.
func Sweep(ctx context.Context, pool *pgxpool.Pool, today time.Time, now string) (expired, deleted int, err error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return 0, 0, err
	}
	defer tx.Rollback(ctx)

	day := today.UTC().Format("2006-01-02")
	rows, err := tx.Query(ctx, selectOverdueSQL, day)
	if err != nil {
		return 0, 0, err
	}
	var list []overdue
	for rows.Next() {
		var o overdue
		if err := rows.Scan(&o.id, &o.owner, &o.current); err != nil {
			rows.Close()
			return 0, 0, err
		}
		list = append(list, o)
	}
	if err := rows.Err(); err != nil {
		rows.Close()
		return 0, 0, err
	}
	rows.Close()

	for _, o := range list {
		tag, err := tx.Exec(ctx, expireSQL, now, o.id, o.current)
		if err != nil {
			return 0, 0, err
		}
		if tag.RowsAffected() != 1 {
			continue
		}
		detail := fmt.Sprintf("id=%d %s->expired", o.id, o.current)
		if _, err := tx.Exec(ctx, insertAuditSQL, now, "payment_request_status", detail, o.owner); err != nil {
			return 0, 0, err
		}
	}
	expired = len(list)

	cutoff := today.UTC().AddDate(0, 0, -30).Format("2006-01-02")
	tag, err := tx.Exec(ctx, pruneSQL, cutoff)
	if err != nil {
		return 0, 0, err
	}
	deleted = int(tag.RowsAffected())
	if deleted > 0 {
		detail := fmt.Sprintf("deleted=%d", deleted)
		if _, err := tx.Exec(ctx, insertAuditSQL, now, "stripe_webhook_sweep", detail, nil); err != nil {
			return 0, 0, err
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return 0, 0, err
	}
	return expired, deleted, nil
}
