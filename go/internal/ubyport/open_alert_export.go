package ubyport

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

// OpenAlert is alerts.open_alert: an unresolved alert with this dedupe key
// exists. It only calls openAlert (sweep.go).
func OpenAlert(ctx context.Context, pool *pgxpool.Pool, key string) (bool, error) {
	return openAlert(ctx, pool, key)
}
