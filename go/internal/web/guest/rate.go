package guest

import (
	"context"
	"net"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
)

func epoch(t time.Time) float64 { return float64(t.UnixNano()) / 1e9 }

// RateClientKey is rate_limit.client_key for guest guide QR views.
func RateClientKey(r *http.Request, scope string) string {
	host := strings.TrimSpace(r.Header.Get("CF-Connecting-IP"))
	if host == "" {
		if h, _, err := net.SplitHostPort(r.RemoteAddr); err == nil {
			host = h
		} else {
			host = r.RemoteAddr
		}
	}
	if host == "" {
		host = "unknown"
	}
	return host + ":" + scope
}

// RateBlocked mirrors rate_limit.blocked for a 15-minute window (900s).
func RateBlocked(ctx context.Context, pool *pgxpool.Pool, scope, key string, limit int, now time.Time) bool {
	window := 900.0
	if _, err := pool.Exec(ctx, `DELETE FROM rate_limit_event WHERE scope = $1 AND key = $2 AND at < $3`,
		scope, key, epoch(now)-window); err != nil {
		return false
	}
	var n int64
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE scope = $1 AND key = $2`, scope, key).Scan(&n); err != nil {
		return false
	}
	return int(n) >= limit
}

// RateRecord mirrors rate_limit.record.
func RateRecord(ctx context.Context, pool *pgxpool.Pool, scope, key string, now time.Time) error {
	_, err := pool.Exec(ctx, `INSERT INTO rate_limit_event (scope, key, at) VALUES ($1, $2, $3)`, scope, key, epoch(now))
	return err
}

// guestPostMaxAttempts is GUEST_POST_MAX_ATTEMPTS in guest.py.
const guestPostMaxAttempts = 30

// guestPostLimited is _throttle_guest_post: true when this IP+link has used up
// the write budget for scope (guest_save, guest_remove, guest_relang, …).
func guestPostLimited(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, r *http.Request, token, scope string, now time.Time) bool {
	if pool == nil {
		return false
	}
	key := clientip.Key(r, getenv, "guest:"+token)
	if RateBlocked(ctx, pool, scope, key, guestPostMaxAttempts, now) {
		return true
	}
	_ = RateRecord(ctx, pool, scope, key, now)
	return false
}
