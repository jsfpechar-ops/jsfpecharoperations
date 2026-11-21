// Package ops ports App/scripts maintenance commands to Go (brief 1780).
package ops

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

// Keys loads Fernet keys the same way the app does. Refuses a minted key.
func Keys(getenv func(string) string) (*secure.MultiFernet, error) {
	return secure.LoadDataKeys(getenv)
}

// RequireSecret is config.require_secret_key for migration scripts.
func RequireSecret(getenv func(string) string) error {
	_, err := secure.LoadSecret(getenv)
	if err != nil {
		return fmt.Errorf("refusing to run: %w. Point UBYHOST_SECRET_KEY or UBYHOST_DATA_DIR at the key the app uses", err)
	}
	_, err = secure.LoadDataKeys(getenv)
	return err
}

// Pool connects with UBYHOST_DATABASE_URL.
func Pool(ctx context.Context, getenv func(string) string) (*pgxpool.Pool, error) {
	url := getenv("UBYHOST_DATABASE_URL")
	if url == "" {
		return nil, errors.New("UBYHOST_DATABASE_URL is required")
	}
	return pgxpool.New(ctx, url)
}

// GuestTable checks to_regclass('public.guest') like migrate_encrypt_doc_fields on PG.
func GuestTable(ctx context.Context, pool *pgxpool.Pool) error {
	var reg *string
	if err := pool.QueryRow(ctx, "SELECT to_regclass('public.guest')::text").Scan(&reg); err != nil {
		return err
	}
	if reg == nil || *reg == "" {
		return errors.New("the PostgreSQL database has no guest table")
	}
	return nil
}

// DataDir is UBYHOST_DATA_DIR with the same default as the app.
func DataDir(getenv func(string) string) string {
	if d := getenv("UBYHOST_DATA_DIR"); d != "" {
		return d
	}
	return "data"
}

// Now is injectable time for tests.
var Now = func() time.Time { return time.Now().UTC() }
