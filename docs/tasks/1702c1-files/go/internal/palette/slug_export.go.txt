package palette

import (
	"context"
	"errors"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

// EnsureGuestSlug is guest_slug.link_key's slug half for callers outside this
// package (brief 1701, the property page): the apartment's current guest-link
// slug, created from its name when it has none; "" when the property has no
// permanent token. It is ensure, with the apartment value built from the
// arguments, so there is one slug generator.
func EnsureGuestSlug(ctx context.Context, pool pgxPool, apartmentID int64, permalinkToken, internalName string) (string, error) {
	return ensure(ctx, pool, apartment{id: apartmentID, internalName: internalName, permalinkToken: permalinkToken})
}

// FollowGuestSlugName is guest_slug.follow_name (brief 1702c): after a save
// that renamed the property, the readable part of the guest link follows the
// new name and keeps the code; every earlier slug keeps redirecting. It is
// ensure, then guest_slug.rename. A property without a permanent token, or a
// name whose slug another property holds (rare), keeps its link unchanged.
func FollowGuestSlugName(ctx context.Context, pool pgxPool, apartmentID int64, permalinkToken, internalName string) error {
	existing, err := ensure(ctx, pool, apartment{id: apartmentID, internalName: internalName, permalinkToken: permalinkToken})
	if err != nil || existing == "" {
		return err
	}
	target := generatedReadable(internalName) + existing[strings.LastIndex(existing, "-"):]
	if target == existing {
		return nil
	}
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx) //nolint:errcheck // no-op after a successful commit
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "apartment_slug", apartmentID); err != nil {
		return err
	}
	var owner int64
	err = tx.QueryRow(ctx, `SELECT apartment_id FROM apartment_slug WHERE slug = $1`, target).Scan(&owner)
	found := err == nil
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	if found && owner != apartmentID {
		return nil
	}
	if _, err := tx.Exec(ctx, `UPDATE apartment_slug SET is_current = 0 WHERE apartment_id = $1 AND is_current = 1`, apartmentID); err != nil {
		return err
	}
	if found {
		_, err = tx.Exec(ctx, `UPDATE apartment_slug SET is_current = 1 WHERE slug = $1`, target)
	} else {
		_, err = tx.Exec(ctx, `INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at) VALUES ($1, $2, 1, $3)`,
			target, apartmentID, utcNowText())
	}
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23505" {
		return nil // db.integrity_errors(): the link stays as it was
	}
	if err != nil {
		return err
	}
	return tx.Commit(ctx)
}
