package billing

import (
	"context"
	"fmt"

	"github.com/jackc/pgx/v5/pgxpool"
)

// portfolioSQL is the subset of billing_analytics.portfolio the snapshot needs.
const portfolioSQL = `SELECT b.owner_user_id, b.status, b.plan, b.billing_interval, b.apartments_billed,
	b.addon_ttlock, b.addon_whitelabel, b.founder, b.carry_czk, b.discount_percent
	FROM billing_account b JOIN user_account u ON u.id = b.owner_user_id
	WHERE b.plan IS NOT NULL ORDER BY b.owner_user_id`

const insertSnapshotSQL = `INSERT INTO billing_month_snapshot (owner_user_id, month, status, plan,
	billing_interval, apartments, addon_ttlock, addon_whitelabel, founder,
	discount_percent, list_czk, net_czk, monthly_czk, created_at)
	VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
	ON CONFLICT (owner_user_id, month) DO UPDATE SET
	status = excluded.status, plan = excluded.plan,
	billing_interval = excluded.billing_interval, apartments = excluded.apartments,
	addon_ttlock = excluded.addon_ttlock, addon_whitelabel = excluded.addon_whitelabel,
	founder = excluded.founder, discount_percent = excluded.discount_percent,
	list_czk = excluded.list_czk, net_czk = excluded.net_czk,
	monthly_czk = excluded.monthly_czk, created_at = excluded.created_at`

type account struct {
	owner      int64
	status     string
	plan       string
	interval   string
	apartments int
	ttlock     bool
	whitelabel bool
	founder    bool
	carry      int
	discount   int
}

func flag(on bool) int {
	if on {
		return 1
	}
	return 0
}

// WriteMonthSnapshot upserts one row per plan-holding account for month
// (YYYY-MM) in one transaction, like billing_analytics.write_month_snapshot.
// now is the created_at stamp. It returns the number of rows written.
func WriteMonthSnapshot(ctx context.Context, pool *pgxpool.Pool, month, now string) (int, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer tx.Rollback(ctx)

	rows, err := tx.Query(ctx, portfolioSQL)
	if err != nil {
		return 0, err
	}
	defer rows.Close()
	var accounts []account
	for rows.Next() {
		var a account
		var ttlock, whitelabel, founder int
		if err := rows.Scan(&a.owner, &a.status, &a.plan, &a.interval, &a.apartments,
			&ttlock, &whitelabel, &founder, &a.carry, &a.discount); err != nil {
			return 0, err
		}
		a.ttlock = ttlock != 0
		a.whitelabel = whitelabel != 0
		a.founder = founder != 0
		accounts = append(accounts, a)
	}
	if err := rows.Err(); err != nil {
		return 0, err
	}
	rows.Close()

	for _, a := range accounts {
		q, err := Quote(a.apartments, a.plan, a.interval, a.ttlock, a.whitelabel, a.founder, a.discount)
		if err != nil {
			return 0, fmt.Errorf("price account: %w", err)
		}
		net := q.Total + a.carry
		monthly := Monthly(net, a.interval)
		if _, err := tx.Exec(ctx, insertSnapshotSQL, a.owner, month, a.status, a.plan,
			a.interval, a.apartments, flag(a.ttlock), flag(a.whitelabel), flag(a.founder),
			a.discount, q.List, net, monthly, now); err != nil {
			return 0, err
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return 0, err
	}
	return len(accounts), nil
}
