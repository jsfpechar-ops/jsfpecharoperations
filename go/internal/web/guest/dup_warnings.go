package guest

import (
	"context"
	"strings"
	"unicode"

	"github.com/jackc/pgx/v5/pgxpool"
)

// dupGuest is the part of a guest row the duplicate check reads.
type dupGuest struct {
	ID      int64
	First   string
	Surname string
	Birth   string
	Doc     string
}

// dupDocKey is guest.py _doc_key: upper case, letters and digits only. An empty
// value or INPASS (the child is on a parent's document) never matches.
func dupDocKey(value string) string {
	var b strings.Builder
	for _, r := range strings.ToUpper(value) {
		if (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
		}
	}
	text := b.String()
	if text == "" || text == "INPASS" {
		return ""
	}
	return text
}

// dupPersonKey is guest.py _person_key: name and birth date, each normalised,
// or "" when any part is empty.
func dupPersonKey(g dupGuest) string {
	parts := []string{
		strings.Join(strings.Fields(strings.ToUpper(g.First)), " "),
		strings.Join(strings.Fields(strings.ToUpper(g.Surname)), " "),
		strings.TrimSpace(g.Birth),
	}
	for _, p := range parts {
		if p == "" {
			return ""
		}
	}
	return strings.Join(parts, "|")
}

// dupTitle is Python's str.title() for a name part: the first letter after a
// non-letter is upper case, the rest lower case.
func dupTitle(s string) string {
	var b strings.Builder
	prevCased := false
	for _, r := range s {
		if unicode.IsLetter(r) {
			if prevCased {
				b.WriteRune(unicode.ToLower(r))
			} else {
				b.WriteRune(unicode.ToUpper(r))
			}
			prevCased = true
			continue
		}
		b.WriteRune(r)
		prevCased = false
	}
	return b.String()
}

// dupDisplayName is guest.py _guest_display_name.
func dupDisplayName(first, surname string) string {
	var parts []string
	for _, raw := range []string{first, surname} {
		if part := strings.TrimSpace(raw); part != "" {
			parts = append(parts, dupTitle(part))
		}
	}
	return strings.Join(parts, " ")
}

// dupWarningsFor is guest.py _duplicate_warnings. A guest in owned gets a line
// when another guest in the stay has the same document number or the same name
// and birth date. Nothing else is shown: other people's details never leave the
// server. translate maps a key to its text in the page language.
func dupWarningsFor(guests []dupGuest, owned map[int64]bool, translate func(string) string) []dupWarning {
	docs := map[string]int{}
	people := map[string]int{}
	for _, g := range guests {
		if k := dupDocKey(g.Doc); k != "" {
			docs[k]++
		}
		if k := dupPersonKey(g); k != "" {
			people[k]++
		}
	}
	var out []dupWarning
	for _, g := range guests {
		if !owned[g.ID] {
			continue
		}
		var what []string
		if k := dupDocKey(g.Doc); k != "" && docs[k] > 1 {
			what = append(what, translate("dup_what_doc"))
		}
		if k := dupPersonKey(g); k != "" && people[k] > 1 {
			what = append(what, translate("dup_what_person"))
		}
		if len(what) > 0 {
			out = append(out, dupWarning{
				Name: dupDisplayName(g.First, g.Surname),
				What: strings.Join(what, ", "),
			})
		}
	}
	return out
}

// formPagesDupWarnings loads the live guests of a stay and returns the
// duplicate warnings for the ones this device saved.
func formPagesDupWarnings(ctx context.Context, pool *pgxpool.Pool, resID int64, owned map[int64]bool, lang string) ([]dupWarning, error) {
	rows, err := pool.Query(ctx, `SELECT id, COALESCE(first_name,''), COALESCE(surname,''),
		COALESCE(birth_date::text,''), COALESCE(doc_number,'')
		FROM guest WHERE reservation_id = $1 AND archived_at IS NULL ORDER BY id`, resID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var guests []dupGuest
	for rows.Next() {
		var g dupGuest
		if err := rows.Scan(&g.ID, &g.First, &g.Surname, &g.Birth, &g.Doc); err != nil {
			return nil, err
		}
		guests = append(guests, g)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	p := Page{Lang: lang}
	return dupWarningsFor(guests, owned, func(k string) string { return p.T(k) }), nil
}
