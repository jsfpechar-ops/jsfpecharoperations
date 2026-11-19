package ical

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

// ExpireOnCancel is claim.expire_on_cancel: it locks the guest link of a
// cancelled stay and fails its queued mail; nothing happens without a claim
// row. It only calls expireOnCancel (reconcile.go).
func ExpireOnCancel(ctx context.Context, pool *pgxpool.Pool, reservationID int64) error {
	return expireOnCancel(ctx, pool, reservationID)
}
