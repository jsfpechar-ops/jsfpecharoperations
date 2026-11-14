package onboarding

// wizard_slug.go: guest_slug.link_key and guest_slug.ensure
// (App/app/guest_slug.py 143-195) for the wizard. Python creates a property's
// readable slug the first time a page asks for its link, and the wizard asks
// on every step; Go does the same. The helpers are copies of the unexported
// ones in go/internal/web/properties/slug.go (brief 1300), which this package
// cannot reach. Brief 1599.

import (
	"context"
	"errors"
	"regexp"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"golang.org/x/text/unicode/norm"
)

// auth.PERMALINK_ALPHABET and guest_slug.CODE_LENGTH, READABLE_MAX, FALLBACK_READABLE.
const (
	wizardSlugAlphabet = "abcdefghijkmnopqrstuvwxyz23456789"
	wizardSlugCode     = 6
	wizardSlugMax      = 40
	wizardSlugFallback = "stay"
)

// wizardSlugReserved is guest_slug.RESERVED.
var wizardSlugReserved = map[string]bool{
	"pin": true, "privacy": true, "claim": true, "confirm": true,
	"party": true, "another": true, "new": true, "edit": true, "save": true,
}

// wizardFoldExtra is guest_slug._FOLD_EXTRA: letters NFKD does not split.
var wizardFoldExtra = strings.NewReplacer(
	"ß", "ss", "æ", "ae", "Æ", "ae", "œ", "oe", "Œ", "oe", "ø", "o", "Ø", "o",
	"ł", "l", "Ł", "l", "đ", "d", "Đ", "d", "ð", "d", "þ", "th", "ı", "i",
)

var wizardNotSlug = regexp.MustCompile(`[^a-z0-9]+`)

// wizardFold is guest_slug.fold.
func wizardFold(text string) string {
	value := norm.NFKD.String(wizardFoldExtra.Replace(text))
	var b strings.Builder
	for _, r := range value {
		if norm.NFD.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		b.WriteRune(r)
	}
	return strings.Trim(wizardNotSlug.ReplaceAllString(strings.ToLower(b.String()), "-"), "-")
}

// wizardReadable is guest_slug._generated_readable (readable_part, then the fallback).
func wizardReadable(name string) string {
	value := wizardFold(name)
	if len(value) > wizardSlugMax {
		head := value[:wizardSlugMax+1]
		switch {
		case strings.HasSuffix(head, "-"):
			value = head[:len(head)-1]
		case strings.Contains(head[:wizardSlugMax], "-"):
			cut := head[:wizardSlugMax]
			value = cut[:strings.LastIndex(cut, "-")]
		default:
			value = value[:wizardSlugMax]
		}
	}
	value = strings.Trim(value, "-")
	if value == "" || wizardSlugReserved[value] {
		return wizardSlugFallback
	}
	return value
}

// wizardSlugCodeText is guest_slug.new_code: six letters of the permalink alphabet.
func wizardSlugCodeText() (string, error) {
	out := make([]byte, wizardSlugCode)
	for i := range out {
		n, err := wizardRandBelow(int64(len(wizardSlugAlphabet)))
		if err != nil {
			return "", err
		}
		out[i] = wizardSlugAlphabet[n]
	}
	return string(out), nil
}

const wizardSlugCurrentSQL = `SELECT slug FROM apartment_slug WHERE apartment_id = $1 AND is_current = 1`

// wizardLinkKey is guest_slug.link_key: the current slug (made from the name
// when there is none yet), else the permanent token; "" without a token.
func (s *wizardServer) wizardLinkKey(ctx context.Context, a *wizardApt, at time.Time) (string, error) {
	if a.PermalinkToken == "" {
		return "", nil
	}
	slug, err := s.wizardEnsureSlug(ctx, a, at)
	if err != nil {
		return "", err
	}
	if slug == "" {
		return a.PermalinkToken, nil
	}
	return slug, nil
}

// wizardEnsureSlug is guest_slug.ensure: read the current slug; else, under
// the apartment_slug lock of db.lock_key, read again and insert a new one,
// retrying a code clash up to eight times. A concurrent insert that wins the
// unique index is read back, as Python does on an integrity error.
func (s *wizardServer) wizardEnsureSlug(ctx context.Context, a *wizardApt, at time.Time) (string, error) {
	var slug string
	err := s.pool.QueryRow(ctx, wizardSlugCurrentSQL, a.ID).Scan(&slug)
	if err == nil {
		return slug, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return "", err
	}
	slug, err = s.wizardInsertSlug(ctx, a, at)
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23505" {
		err = s.pool.QueryRow(ctx, wizardSlugCurrentSQL, a.ID).Scan(&slug)
		if errors.Is(err, pgx.ErrNoRows) {
			return "", nil
		}
	}
	return slug, err
}

func (s *wizardServer) wizardInsertSlug(ctx context.Context, a *wizardApt, at time.Time) (string, error) {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return "", err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "apartment_slug", a.ID); err != nil {
		return "", err
	}
	var slug string
	err = tx.QueryRow(ctx, wizardSlugCurrentSQL, a.ID).Scan(&slug)
	if err == nil {
		return slug, tx.Commit(ctx)
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return "", err
	}
	readable := wizardReadable(a.InternalName)
	for i := 0; i < 8; i++ {
		code, err := wizardSlugCodeText()
		if err != nil {
			return "", err
		}
		slug = readable + "-" + code
		var one int
		err = tx.QueryRow(ctx, `SELECT 1 FROM apartment_slug WHERE slug = $1`, slug).Scan(&one)
		if err == nil {
			continue
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return "", err
		}
		if _, err := tx.Exec(ctx, `INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at) VALUES ($1, $2, 1, $3)`,
			slug, a.ID, stamp(at)); err != nil {
			return "", err
		}
		return slug, tx.Commit(ctx)
	}
	return "", errors.New("could not find a free guest link code")
}
