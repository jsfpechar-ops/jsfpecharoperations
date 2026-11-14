package palette

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
)

// LinkKey is guest_slug.link_key for the other Go packages (brief 1595): the
// apartment's current slug, created from its name by ensure when it has none,
// else its permanent token. An apartment without a permanent token gets "".
// It only wraps linkKey; the palette's own behaviour does not change.
func LinkKey(ctx context.Context, pool *pgxpool.Pool, apartmentID int64, internalName, permalinkToken string) (string, error) {
	return linkKey(ctx, pool, apartment{id: apartmentID, internalName: internalName, permalinkToken: permalinkToken})
}
