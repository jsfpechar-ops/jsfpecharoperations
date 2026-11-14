package public

// The rows the unsubscribe page reads and writes: App/app/lifecycle_mail.py
// (unsubscribe, set_opt_out, suppress, is_opted_out) and
// App/app/rate_limit.py (blocked, record), as plain PostgreSQL.

import (
	"context"
	"errors"
	"net"
	"net/http"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const (
	unsubScope       = "mail_unsubscribe"
	unsubLimit       = 30
	unsubWindowSecs  = 3600
	suppressionScope = "onboarding" // lifecycle_mail.SUPPRESSION_SCOPE
)

// unsubKey is rate_limit.client_key(request, scope): the peer address
// (CF-Connecting-IP, which Caddy overwrites, else the socket peer, else
// "unknown") and the scope.
func unsubKey(r *http.Request) string {
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
	return host + ":" + unsubScope
}

func epoch(t time.Time) float64 { return float64(t.UnixNano()) / 1e9 }

// rateBlocked is rate_limit.blocked(scope, key, 30, 3600): prune the window,
// then true when the key has 30 or more events left.
func rateBlocked(ctx context.Context, pool *pgxpool.Pool, key string, now time.Time) (bool, error) {
	if _, err := pool.Exec(ctx, `DELETE FROM rate_limit_event WHERE scope = $1 AND key = $2 AND at < $3`,
		unsubScope, key, epoch(now)-unsubWindowSecs); err != nil {
		return false, err
	}
	var n int64
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM rate_limit_event WHERE scope = $1 AND key = $2`,
		unsubScope, key).Scan(&n); err != nil {
		return false, err
	}
	return n >= unsubLimit, nil
}

// rateRecord is rate_limit.record.
func rateRecord(ctx context.Context, pool *pgxpool.Pool, key string, now time.Time) error {
	_, err := pool.Exec(ctx, `INSERT INTO rate_limit_event (scope, key, at) VALUES ($1, $2, $3)`,
		unsubScope, key, epoch(now))
	return err
}

// userExists is SELECT 1 FROM user_account WHERE id = ?.
func userExists(ctx context.Context, pool *pgxpool.Pool, id int64) (bool, error) {
	var one int
	err := pool.QueryRow(ctx, `SELECT 1 FROM user_account WHERE id = $1`, id).Scan(&one)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	return err == nil, err
}

// optedOut is lifecycle_mail.is_opted_out.
func optedOut(ctx context.Context, pool *pgxpool.Pool, id int64) (bool, error) {
	var flag *int64
	err := pool.QueryRow(ctx, `SELECT onboarding_emails_opt_out FROM user_account WHERE id = $1`, id).Scan(&flag)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	return flag != nil && *flag != 0, err
}

// unsubscribe is lifecycle_mail.unsubscribe: false when the account is gone;
// else suppress the address hash (when the token has one), set the account's
// opt-out flag and, when that changed it, write the audit line. One
// transaction, where Python commits each statement alone.
func unsubscribe(ctx context.Context, pool *pgxpool.Pool, id int64, digest string, now time.Time) (bool, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer tx.Rollback(ctx) //nolint:errcheck
	var one int
	if err := tx.QueryRow(ctx, `SELECT 1 FROM user_account WHERE id = $1`, id).Scan(&one); err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return false, nil
		}
		return false, err
	}
	at := session.UTCNow(now)
	if digest != "" {
		if _, err := tx.Exec(ctx, `INSERT INTO mail_suppression (email_hash, scope, created_at) VALUES ($1, $2, $3)
			ON CONFLICT (email_hash, scope) DO NOTHING`, digest, suppressionScope, at); err != nil {
			return false, err
		}
	}
	var flag *int64
	if err := tx.QueryRow(ctx, `SELECT onboarding_emails_opt_out FROM user_account WHERE id = $1`, id).Scan(&flag); err != nil {
		return false, err
	}
	if flag == nil || *flag == 0 {
		if _, err := tx.Exec(ctx, `UPDATE user_account SET onboarding_emails_opt_out = 1, onboarding_emails_opt_out_at = $1 WHERE id = $2`,
			at, id); err != nil {
			return false, err
		}
		if _, err := tx.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
			VALUES ($1, 'unsubscribe_link', 'onboarding_emails_opted_out', '', $2, NULL, NULL)`, at, id); err != nil {
			return false, err
		}
	}
	return true, tx.Commit(ctx)
}
