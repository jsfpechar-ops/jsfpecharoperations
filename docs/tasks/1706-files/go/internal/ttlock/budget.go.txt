package ttlock

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// budgetProvider is the lock_api_usage.provider value ttlock.py writes.
const budgetProvider = "ttlock"

// Budget is the monthly call guard that every TTLock request passes through (ttlock.py
// _budget_allows and _count_call). Allows is asked before a request; Count runs before it is sent.
type Budget interface {
	Allows(ctx context.Context, priority string) (bool, error)
	Count(ctx context.Context) error
}

// PGBudget keeps the count in lock_api_usage (month, provider, calls), the same table
// and key as ttlock.py, through pgxpool with $n placeholders.
type PGBudget struct {
	pool  *pgxpool.Pool
	limit int64
	now   func() time.Time
}

// NewPGBudget builds the guard. limit is Config.MonthlyCalls; zero or less allows every call.
// The month is the UTC month of now(), as in ttlock.py _month_key.
func NewPGBudget(pool *pgxpool.Pool, limit int64, now func() time.Time) *PGBudget {
	if now == nil {
		now = time.Now
	}
	return &PGBudget{pool: pool, limit: limit, now: now}
}

// MonthKey ports _month_key: the UTC year and month as "YYYY-MM".
func MonthKey(t time.Time) string {
	return t.UTC().Format("2006-01")
}

// CallsThisMonth ports calls_this_month. A missing row counts as 0.
func (b *PGBudget) CallsThisMonth(ctx context.Context) (int64, error) {
	var calls int64
	err := b.pool.QueryRow(ctx,
		"SELECT calls FROM lock_api_usage WHERE month = $1 AND provider = $2",
		MonthKey(b.now()), budgetProvider,
	).Scan(&calls)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, nil
	}
	if err != nil {
		return 0, err
	}
	return calls, nil
}

// Allows ports _budget_allows. At 80 % of the limit low-priority calls stop; at 95 % low and
// normal calls stop. Critical calls (delete) always pass, as in Python.
func (b *PGBudget) Allows(ctx context.Context, priority string) (bool, error) {
	used, err := b.CallsThisMonth(ctx)
	if err != nil {
		return false, err
	}
	if b.limit <= 0 {
		return true, nil
	}
	ratio := float64(used) / float64(b.limit)
	if ratio >= 0.95 && (priority == PriorityLow || priority == PriorityNormal) {
		return false, nil
	}
	if ratio >= 0.80 && priority == PriorityLow {
		return false, nil
	}
	return true, nil
}

// Count ports _count_call: adds one call to this month's row, creating it when needed.
func (b *PGBudget) Count(ctx context.Context) error {
	_, err := b.pool.Exec(ctx,
		"INSERT INTO lock_api_usage (month, provider, calls) VALUES ($1, $2, 1) "+
			"ON CONFLICT (month, provider) DO UPDATE SET calls = lock_api_usage.calls + 1",
		MonthKey(b.now()), budgetProvider,
	)
	return err
}
