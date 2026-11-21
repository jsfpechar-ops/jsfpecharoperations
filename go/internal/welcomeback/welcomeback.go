// Package welcomeback mirrors App/app/welcome_back.py (0275).
package welcomeback

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const awayDays = 14

// KeysFor returns settings keys check reads (welcome_back.py keys_for).
func KeysFor(userID int64) (seen, line string) {
	return fmt.Sprintf("last_seen_%d", userID), fmt.Sprintf("welcome_back_%d", userID)
}

// Check records today's visit in settings (last_seen_*). It matches Python's
// welcome_back.check side effects on every authenticated dashboard load.
func Check(ctx context.Context, pool *pgxpool.Pool, userID, ownerID int64, today time.Time) error {
	if userID == 0 {
		return nil
	}
	seenKey, lineKey := KeysFor(userID)
	lastSeen, err := getSetting(ctx, pool, seenKey)
	if err != nil {
		return err
	}
	parsed := parseDate(lastSeen)
	todayISO := today.Format("2006-01-02")
	if parsed == nil || parsed.Format("2006-01-02") != todayISO {
		if err := setSetting(ctx, pool, seenKey, todayISO); err != nil {
			return err
		}
	}
	if parsed != nil && int(today.Sub(*parsed).Hours()/24) >= awayDays {
		val := fmt.Sprintf("%s|%s", parsed.Format("2006-01-02"), todayISO)
		if err := setSetting(ctx, pool, lineKey, val); err != nil {
			return err
		}
	}
	_ = ownerID
	return nil
}

func getSetting(ctx context.Context, pool *pgxpool.Pool, key string) (string, error) {
	var v *string
	err := pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`, key).Scan(&v)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	if v == nil {
		return "", nil
	}
	return *v, nil
}

func setSetting(ctx context.Context, pool *pgxpool.Pool, key, value string) error {
	_, err := pool.Exec(ctx,
		`INSERT INTO settings (key, value) VALUES ($1, $2)
		 ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value`, key, value)
	return err
}

func parseDate(raw string) *time.Time {
	raw = strings.TrimSpace(raw)
	if len(raw) < 10 {
		return nil
	}
	t, err := time.Parse("2006-01-02", raw[:10])
	if err != nil {
		return nil
	}
	return &t
}
