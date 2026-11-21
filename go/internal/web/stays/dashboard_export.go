package stays

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// PragueToday is the civil date in Europe/Prague at at.
func PragueToday(at time.Time) time.Time { return pragueToday(at) }

// EnrichDashboardRows runs enrichRows for dashboard parity (reporting.dashboard_rows guests).
func EnrichDashboardRows(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, rows []Row, at time.Time) ([]Row, int, error) {
	return enrichRows(ctx, pool, getenv, rows, at)
}
