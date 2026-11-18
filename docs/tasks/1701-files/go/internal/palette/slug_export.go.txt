package palette

import "context"

// EnsureGuestSlug is guest_slug.link_key's slug half for callers outside this
// package (brief 1701, the property page): the apartment's current guest-link
// slug, created from its name when it has none; "" when the property has no
// permanent token. It is ensure, with the apartment value built from the
// arguments, so there is one slug generator.
func EnsureGuestSlug(ctx context.Context, pool pgxPool, apartmentID int64, permalinkToken, internalName string) (string, error) {
	return ensure(ctx, pool, apartment{id: apartmentID, internalName: internalName, permalinkToken: permalinkToken})
}
