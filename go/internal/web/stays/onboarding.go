package stays

import (
	"context"
	"errors"
	"strconv"
	"strings"
	"unicode"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Banner is onboarding_banner(onboarding) on the stays list.
type Banner struct {
	Show       bool
	URL        string
	ReturnPath string
}

func onboardingBanner(ctx context.Context, pool *pgxpool.Pool, workspace int64, path string) (Banner, error) {
	b := Banner{ReturnPath: path}
	if workspace != 0 {
		var v *string
		err := pool.QueryRow(ctx, `SELECT value FROM settings WHERE key = $1`,
			"onboarding_dismissed_"+strconv.FormatInt(workspace, 10)).Scan(&v)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return b, err
		}
		if v != nil && *v == "1" {
			return b, nil
		}
	}
	var id, feeds int64
	var house, zip, obec string
	err := pool.QueryRow(ctx,
		`SELECT a.id, COALESCE(a.addr_house_no, ''), COALESCE(a.addr_zip, ''), COALESCE(a.addr_obec, ''),
		  (SELECT COUNT(*) FROM ical_feed f WHERE f.apartment_id = a.id AND f.active = 1)
		 FROM apartment a WHERE a.archived_at IS NULL AND a.owner_user_id IS NOT DISTINCT FROM $1 ORDER BY a.id LIMIT 1`, workspace).
		Scan(&id, &house, &zip, &obec, &feeds)
	if errors.Is(err, pgx.ErrNoRows) {
		return Banner{Show: true, URL: "/apartments/new", ReturnPath: path}, nil
	}
	if err != nil {
		return b, err
	}
	base := "/apartments/" + strconv.FormatInt(id, 10)
	if !addrComplete(house, zip, obec) {
		return Banner{Show: true, URL: base + "?view=settings&section=property#address", ReturnPath: path}, nil
	}
	if feeds == 0 {
		var manual int64
		if err := pool.QueryRow(ctx,
			`SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = $1 AND r.status = 'active' AND r.source = 'manual'`, id).Scan(&manual); err != nil {
			return b, err
		}
		if manual == 0 {
			return Banner{Show: true, URL: base + "?view=bookings#calendars", ReturnPath: path}, nil
		}
	}
	return b, nil
}

func addrComplete(house, zip, obec string) bool {
	if strip(house) == "" || strip(zip) == "" || strip(obec) == "" {
		return false
	}
	n := 0
	for _, r := range zip {
		if unicode.IsDigit(r) {
			n++
		}
	}
	return n == 5
}

func strip(s string) string {
	return strings.TrimSpace(s)
}
