package properties

import (
	"context"
	"crypto/rand"
	"errors"
	"fmt"
	"math/big"
	"regexp"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/text/unicode/norm"
)

// permalinkAlphabet is auth.PERMALINK_ALPHABET.
const permalinkAlphabet = "abcdefghijkmnopqrstuvwxyz23456789"

// Guest slug limits: guest_slug.CODE_LENGTH, READABLE_MAX, FALLBACK_READABLE.
const (
	codeLength       = 6
	readableMax      = 40
	fallbackReadable = "stay"
)

// reservedReadable is guest_slug.RESERVED.
var reservedReadable = map[string]bool{
	"pin": true, "privacy": true, "claim": true, "confirm": true,
	"party": true, "another": true, "new": true, "edit": true, "save": true,
}

// foldExtra is guest_slug._FOLD_EXTRA: letters NFKD does not split.
var foldExtra = strings.NewReplacer(
	"ß", "ss", "æ", "ae", "Æ", "ae", "œ", "oe", "Œ", "oe", "ø", "o", "Ø", "o",
	"ł", "l", "Ł", "l", "đ", "d", "Đ", "d", "ð", "d", "þ", "th", "ı", "i",
)

var notSlug = regexp.MustCompile(`[^a-z0-9]+`)

// fold is guest_slug.fold.
func fold(text string) string {
	value := norm.NFKD.String(foldExtra.Replace(text))
	var b strings.Builder
	for _, r := range value {
		if norm.NFD.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		b.WriteRune(r)
	}
	value = notSlug.ReplaceAllString(strings.ToLower(b.String()), "-")
	return strings.Trim(value, "-")
}

// readablePart is guest_slug.readable_part.
func readablePart(text string) string {
	value := fold(text)
	if len(value) > readableMax {
		head := value[:readableMax+1]
		switch {
		case strings.HasSuffix(head, "-"):
			value = head[:len(head)-1]
		case strings.Contains(head[:readableMax], "-"):
			cut := head[:readableMax]
			value = cut[:strings.LastIndex(cut, "-")]
		default:
			value = value[:readableMax]
		}
	}
	return strings.Trim(value, "-")
}

// generatedReadable is guest_slug._generated_readable.
func generatedReadable(name string) string {
	readable := readablePart(name)
	if readable == "" || reservedReadable[readable] {
		return fallbackReadable
	}
	return readable
}

// randomIndex is secrets.randbelow(n).
func randomIndex(n int64) (int64, error) {
	v, err := rand.Int(rand.Reader, big.NewInt(n))
	if err != nil {
		return 0, err
	}
	return v.Int64(), nil
}

// randomString is "".join(secrets.choice(PERMALINK_ALPHABET) for _ in range(n)).
func randomString(n int) (string, error) {
	out := make([]byte, n)
	for i := range out {
		v, err := randomIndex(int64(len(permalinkAlphabet)))
		if err != nil {
			return "", err
		}
		out[i] = permalinkAlphabet[v]
	}
	return string(out), nil
}

// newPermalinkToken is auth.new_permalink_token: 20 characters.
func newPermalinkToken() (string, error) { return randomString(20) }

// newPermalinkPIN is auth.new_permalink_pin: six digits.
func newPermalinkPIN() (string, error) {
	v, err := randomIndex(1_000_000)
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%06d", v), nil
}

const (
	slugLockSQL    = `SELECT pg_advisory_xact_lock(hashtext($1), $2)`
	slugCurrentSQL = `SELECT slug FROM apartment_slug WHERE apartment_id = $1 AND is_current = 1`
	slugNameSQL    = `SELECT internal_name FROM apartment WHERE id = $1`
	slugDeleteSQL  = `DELETE FROM apartment_slug WHERE apartment_id = $1`
	slugTakenSQL   = `SELECT 1 FROM apartment_slug WHERE slug = $1`
	slugInsertSQL  = `INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at) VALUES ($1, $2, 1, $3)`
)

// rotateSlug is guest_slug.rotate(apartment_id): inside one transaction that
// holds the apartment_slug advisory lock, drop every slug of the apartment and
// issue one current slug with a new code. The readable part is kept from the
// current slug, or made from the apartment name when there is none.
func rotateSlug(ctx context.Context, pool *pgxpool.Pool, apartmentID int64, at time.Time) error {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if _, err := tx.Exec(ctx, slugLockSQL, "apartment_slug", apartmentID); err != nil {
		return err
	}
	var current string
	err = tx.QueryRow(ctx, slugCurrentSQL, apartmentID).Scan(&current)
	hasCurrent := err == nil
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	var readable string
	if hasCurrent {
		// readable_of: slug.rsplit("-", 1)[0]
		readable = current
		if i := strings.LastIndex(current, "-"); i >= 0 {
			readable = current[:i]
		}
	} else {
		var name *string
		err := tx.QueryRow(ctx, slugNameSQL, apartmentID).Scan(&name)
		if err != nil && !errors.Is(err, pgx.ErrNoRows) {
			return err
		}
		text := ""
		if name != nil {
			text = *name
		}
		readable = generatedReadable(text)
	}
	if _, err := tx.Exec(ctx, slugDeleteSQL, apartmentID); err != nil {
		return err
	}
	for i := 0; i < 8; i++ {
		code, err := randomString(codeLength)
		if err != nil {
			return err
		}
		slug := readable + "-" + code
		var one int
		err = tx.QueryRow(ctx, slugTakenSQL, slug).Scan(&one)
		if err == nil {
			continue
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return err
		}
		if _, err := tx.Exec(ctx, slugInsertSQL, slug, apartmentID, stamp(at)); err != nil {
			return err
		}
		return tx.Commit(ctx)
	}
	return errors.New("could not find a free guest link code")
}
