package palette

// Port of App/app/guest_slug.py: the readable guest link /l/{readable}-{code}
// and ensure(), which creates the current slug the first time the palette
// copies a property link.

import (
	"context"
	"crypto/rand"
	"errors"
	"math/big"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
)

const (
	codeLength        = 6
	readableMax       = 40
	fallbackReadable  = "stay"
	permalinkAlphabet = "abcdefghijkmnopqrstuvwxyz23456789"
	insertAttempts    = 8
)

// reservedReadable is guest_slug.RESERVED: path segments under /l/{key}/.
var reservedReadable = map[string]bool{
	"pin": true, "privacy": true, "claim": true, "confirm": true, "party": true,
	"another": true, "new": true, "edit": true, "save": true,
}

// foldExtra is guest_slug._FOLD_EXTRA: letters NFKD does not split.
var foldExtra = map[rune]string{
	'ß': "ss", 'æ': "ae", 'Æ': "ae", 'œ': "oe", 'Œ': "oe", 'ø': "o", 'Ø': "o",
	'ł': "l", 'Ł': "l", 'đ': "d", 'Đ': "d", 'ð': "d", 'þ': "th", 'ı': "i",
}

// latinBase holds what NFKD gives for the Latin-1 Supplement and Latin
// Extended-A letters (and a few compatibility forms): the base letters with the
// accent removed. Other scripts and other diacritics are not folded (see the
// 0680 report).
var latinBase = buildLatinBase([]struct{ base, runes string }{
	{"a", "àáâãäåÀÁÂÃÄÅāĀăĂąĄª"},
	{"o", "òóôõöÒÓÔÕÖōŌŏŎőŐº"},
	{"c", "çÇćĆĉĈċĊčČ"},
	{"d", "ďĎ"},
	{"e", "èéêëÈÉÊËēĒĕĔėĖęĘěĚ"},
	{"g", "ĝĜğĞġĠģĢ"},
	{"h", "ĥĤ"},
	{"i", "ìíîïÌÍÎÏĩĨīĪĭĬįĮİ"},
	{"j", "ĵĴ"},
	{"k", "ķĶ"},
	{"l", "ĺĹļĻľĽ"},
	{"n", "ñÑńŃņŅňŇ"},
	{"r", "ŕŔŗŖřŘ"},
	{"s", "śŚŝŜşŞšŠſ"},
	{"t", "ţŢťŤ"},
	{"u", "ùúûüÙÚÛÜũŨūŪŭŬůŮűŰųŲ"},
	{"w", "ŵŴ"},
	{"y", "ýÝÿŷŶŸ"},
	{"z", "źŹżŻžŽ"},
	{"ij", "ĳĲ"},
	{"l·", "ŀĿ"},
	{"ʼn", "ŉ"},
})

func buildLatinBase(groups []struct{ base, runes string }) map[rune]string {
	out := map[rune]string{}
	for _, g := range groups {
		for _, r := range g.runes {
			out[r] = g.base
		}
	}
	return out
}

// fold is guest_slug.fold: "Vinohrady – Studio Žižkov" -> "vinohrady-studio-zizkov".
func fold(text string) string {
	var b strings.Builder
	for _, r := range text {
		if s, ok := foldExtra[r]; ok {
			b.WriteString(s)
			continue
		}
		if r >= 0x0300 && r <= 0x036F { // combining marks left by decomposed input
			continue
		}
		if s, ok := latinBase[r]; ok {
			b.WriteString(s)
			continue
		}
		b.WriteRune(r)
	}
	var out strings.Builder
	dash := false
	for _, r := range strings.ToLower(b.String()) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			out.WriteRune(r)
			dash = false
			continue
		}
		if !dash {
			out.WriteByte('-')
			dash = true
		}
	}
	return strings.Trim(out.String(), "-")
}

// readablePart is guest_slug.readable_part: cut at the last word boundary
// inside 40 characters; a single long word is cut hard.
func readablePart(text string) string {
	value := fold(text)
	if len(value) > readableMax {
		head := value[:readableMax+1]
		if strings.HasSuffix(head, "-") {
			value = head[:readableMax]
		} else if i := strings.LastIndex(head[:readableMax], "-"); i >= 0 {
			value = head[:i]
		} else {
			value = value[:readableMax]
		}
	}
	return strings.Trim(value, "-")
}

func isReserved(readable string) bool {
	return reservedReadable[readable]
}

// generatedReadable is guest_slug._generated_readable.
func generatedReadable(name string) string {
	readable := readablePart(name)
	if readable == "" || isReserved(readable) {
		return fallbackReadable
	}
	return readable
}

// newCode is guest_slug.new_code: six characters from the token alphabet, from crypto/rand.
func newCode() (string, error) {
	b := make([]byte, codeLength)
	max := big.NewInt(int64(len(permalinkAlphabet)))
	for i := range b {
		n, err := rand.Int(rand.Reader, max)
		if err != nil {
			return "", err
		}
		b[i] = permalinkAlphabet[n.Int64()]
	}
	return string(b), nil
}

// currentSlug is guest_slug.current: the apartment's current slug, "" if none.
func currentSlug(ctx context.Context, pool pgxPool, apartmentID int64) (string, error) {
	var slug string
	err := pool.QueryRow(ctx,
		`SELECT slug FROM apartment_slug WHERE apartment_id = $1 AND is_current = 1`, apartmentID).Scan(&slug)
	if err == pgx.ErrNoRows {
		return "", nil
	}
	return slug, err
}

// insertCurrent is guest_slug._insert_current inside an open transaction. It
// retries a code clash.
func insertCurrent(ctx context.Context, tx pgx.Tx, apartmentID int64, readable string) (string, error) {
	for i := 0; i < insertAttempts; i++ {
		code, err := newCode()
		if err != nil {
			return "", err
		}
		slug := readable + "-" + code
		var one int
		err = tx.QueryRow(ctx, `SELECT 1 FROM apartment_slug WHERE slug = $1`, slug).Scan(&one)
		if err == nil {
			continue
		}
		if err != pgx.ErrNoRows {
			return "", err
		}
		if _, err := tx.Exec(ctx,
			`INSERT INTO apartment_slug (slug, apartment_id, is_current, created_at) VALUES ($1, $2, 1, $3)`,
			slug, apartmentID, utcNowText()); err != nil {
			return "", err
		}
		return slug, nil
	}
	return "", errors.New("could not find a free guest link code")
}

// utcNowText is db.utcnow(): second precision, ISO 8601 with +00:00.
func utcNowText() string {
	return time.Now().UTC().Truncate(time.Second).Format("2006-01-02T15:04:05+00:00")
}

// ensure is guest_slug.ensure: the current slug, created from the name if the
// apartment has none. Returns "" when the apartment has no permanent token.
func ensure(ctx context.Context, pool pgxPool, a apartment) (string, error) {
	if a.permalinkToken == "" {
		return "", nil
	}
	existing, err := currentSlug(ctx, pool, a.id)
	if err != nil || existing != "" {
		return existing, err
	}
	tx, err := pool.Begin(ctx)
	if err != nil {
		return "", err
	}
	defer tx.Rollback(ctx) //nolint:errcheck // no-op after a successful commit
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "apartment_slug", a.id); err != nil {
		return "", err
	}
	var slug string
	err = tx.QueryRow(ctx,
		`SELECT slug FROM apartment_slug WHERE apartment_id = $1 AND is_current = 1`, a.id).Scan(&slug)
	if err == nil {
		return slug, tx.Commit(ctx)
	}
	if err != pgx.ErrNoRows {
		return "", err
	}
	slug, err = insertCurrent(ctx, tx, a.id, generatedReadable(a.internalName))
	if err != nil {
		// Another request created it between our read and our write.
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23505" {
			return currentSlug(ctx, pool, a.id)
		}
		return "", err
	}
	if err := tx.Commit(ctx); err != nil {
		return "", err
	}
	return slug, nil
}
