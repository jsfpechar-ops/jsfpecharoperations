package booking

// Publishing a property's public page, the Go twin of
// property_page.slug_for, ensure_slug, publish and publish_page
// (App/app/property_page.py 14-115, 192-200). The demo seed (brief 1597) is the
// first caller. Nothing here is a route.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"golang.org/x/text/unicode/norm"
)

const maxSlugName = 48 // property_page._MAX_SLUG_NAME

// NormaliseSlugName is property_page.normalise_name: ASCII-fold (NFKD, drop what
// is not ASCII), lower case, every run of characters outside a-z and 0-9 becomes
// one "-", cut to 48 characters, trim "-".
func NormaliseSlugName(name string) string {
	var ascii strings.Builder
	for _, r := range norm.NFKD.String(name) {
		if r < 0x80 {
			ascii.WriteRune(r)
		}
	}
	var parts []string
	var cur strings.Builder
	for _, r := range strings.ToLower(ascii.String()) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			cur.WriteRune(r)
			continue
		}
		if cur.Len() > 0 {
			parts = append(parts, cur.String())
			cur.Reset()
		}
	}
	if cur.Len() > 0 {
		parts = append(parts, cur.String())
	}
	joined := strings.Join(parts, "-")
	if len(joined) > maxSlugName {
		joined = joined[:maxSlugName]
	}
	return strings.Trim(joined, "-")
}

// SlugFor is property_page.slug_for: name-xxxx, where xxxx is the first four
// hex characters of sha256("apartment:<id>").
func SlugFor(apartmentID int64, name string) string {
	sum := sha256.Sum256([]byte(fmt.Sprintf("apartment:%d", apartmentID)))
	base := NormaliseSlugName(name)
	if base == "" {
		base = "apartment"
	}
	return base + "-" + hex.EncodeToString(sum[:])[:4]
}

// EnsureSlug is property_page.ensure_slug: create the property_slug row, or
// when the name changed move the old slug to property_slug_history and update
// the row. It returns the current slug. An unknown apartment is an error.
func EnsureSlug(ctx context.Context, db DB, apartmentID int64, now time.Time) (string, error) {
	var name string
	err := db.QueryRow(ctx, `SELECT internal_name FROM apartment WHERE id = $1`, apartmentID).Scan(&name)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", fmt.Errorf("apartment %d does not exist", apartmentID)
	}
	if err != nil {
		return "", err
	}
	slug := SlugFor(apartmentID, name)
	stamp := StampAt(now)
	var old string
	err = db.QueryRow(ctx, `SELECT slug FROM property_slug WHERE apartment_id = $1`, apartmentID).Scan(&old)
	switch {
	case errors.Is(err, pgx.ErrNoRows):
		_, err = db.Exec(ctx, `INSERT INTO property_slug (apartment_id, slug, published, created_at, updated_at) VALUES ($1, $2, 0, $3, $3)`,
			apartmentID, slug, stamp)
	case err != nil:
	case old != slug:
		if _, err = db.Exec(ctx, `INSERT INTO property_slug_history (old_slug, apartment_id, created_at) VALUES ($1, $2, $3)`,
			old, apartmentID, stamp); err == nil {
			_, err = db.Exec(ctx, `UPDATE property_slug SET slug = $1, updated_at = $2 WHERE apartment_id = $3`, slug, stamp, apartmentID)
		}
	}
	return slug, err
}

// PublishPage is property_page.publish_page: set published (and published_at, or
// NULL) on the property_page row and on the property_slug row, which is created
// first when missing. A property without a property_page row only gets the slug.
func PublishPage(ctx context.Context, db DB, apartmentID int64, published bool, now time.Time) error {
	stamp := StampAt(now)
	var at any
	flag := 0
	if published {
		at, flag = stamp, 1
	}
	if _, err := db.Exec(ctx, `UPDATE property_page SET published = $1, published_at = $2, updated_at = $3 WHERE apartment_id = $4`,
		flag, at, stamp, apartmentID); err != nil {
		return err
	}
	if _, err := EnsureSlug(ctx, db, apartmentID, now); err != nil {
		return err
	}
	_, err := db.Exec(ctx, `UPDATE property_slug SET published = $1, published_at = $2, updated_at = $3 WHERE apartment_id = $4`,
		flag, at, stamp, apartmentID)
	return err
}
