package guest

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	pinScopeFail      = "pin_fail"
	pinScopeFailToken = "pin_fail_token"
	pinMaxFailures    = 10
	pinTokenMax       = 3 * pinMaxFailures
	pinWindowSec      = 15 * 60
	pinTokenLockSec   = 24 * 60 * 60
)

func rateEpoch(t time.Time) float64 { return float64(t.UnixNano()) / 1e9 }

func ratePrune(ctx context.Context, pool *pgxpool.Pool, scope, key string, window int, now time.Time) error {
	_, err := pool.Exec(ctx,
		`DELETE FROM rate_limit_event WHERE scope = $1 AND key = $2 AND at < $3`,
		scope, key, rateEpoch(now)-float64(window))
	return err
}

func rateCount(ctx context.Context, pool *pgxpool.Pool, scope, key string, window int, now time.Time) (int, error) {
	if err := ratePrune(ctx, pool, scope, key, window, now); err != nil {
		return 0, err
	}
	var n int64
	err := pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM rate_limit_event WHERE scope = $1 AND key = $2`, scope, key).Scan(&n)
	return int(n), err
}

func rateBlocked(ctx context.Context, pool *pgxpool.Pool, scope, key string, max, window int, now time.Time) (bool, error) {
	if key == "" {
		return true, nil
	}
	n, err := rateCount(ctx, pool, scope, key, window, now)
	return n >= max, err
}

func rateRecord(ctx context.Context, pool *pgxpool.Pool, scope, key string, now time.Time) error {
	_, err := pool.Exec(ctx,
		`INSERT INTO rate_limit_event (scope, key, at) VALUES ($1, $2, $3)`,
		scope, key, rateEpoch(now))
	return err
}

func pinBlocked(ctx context.Context, pool *pgxpool.Pool, clientKey string, now time.Time) (bool, error) {
	return rateBlocked(ctx, pool, pinScopeFail, clientKey, pinMaxFailures, pinWindowSec, now)
}

func pinTokenBlocked(ctx context.Context, pool *pgxpool.Pool, lockKey string, now time.Time) (bool, error) {
	return rateBlocked(ctx, pool, pinScopeFailToken, lockKey, pinTokenMax, pinTokenLockSec, now)
}

func pinFailureCount(ctx context.Context, pool *pgxpool.Pool, clientKey string, now time.Time) (int, error) {
	return rateCount(ctx, pool, pinScopeFail, clientKey, pinWindowSec, now)
}

func recordPinFailure(ctx context.Context, pool *pgxpool.Pool, clientKey, lockKey string, now time.Time) error {
	if err := rateRecord(ctx, pool, pinScopeFail, clientKey, now); err != nil {
		return err
	}
	if lockKey != "" {
		return rateRecord(ctx, pool, pinScopeFailToken, lockKey, now)
	}
	return nil
}
