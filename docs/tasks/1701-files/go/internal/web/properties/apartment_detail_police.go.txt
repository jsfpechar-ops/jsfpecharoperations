package properties

// police_check.findings_for (A4) for the property page: warnings, never
// blocks, about the saved police details. The letter-paste findings of the
// POST re-render (letter_findings) do not exist on a GET and are not ported.
// Nothing here stores or logs a value; the password never enters it.

import (
	"context"
	"strings"

	"github.com/jackc/pgx/v5"
	"golang.org/x/text/unicode/norm"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// detailFinding is one {"code", "field", "text"} of police_check.findings_for.
type detailFinding struct{ Code, Field, Text string }

// detailPoliceFields is FIELD_LABELS: the four values a letter and the form can disagree on.
var detailPoliceFields = []string{"uby_ws_user", "uby_idub", "uby_mark", "uby_name"}

// policeFold is police_check._fold: lower case, no diacritics, only letters
// and digits, single spaces.
func policeFold(value string) string {
	var b strings.Builder
	for _, r := range norm.NFKD.String(value) {
		if norm.NFC.PropertiesString(string(r)).CCC() != 0 {
			continue
		}
		b.WriteRune(r)
	}
	text := strings.ReplaceAll(strings.ToLower(b.String()), "ß", "ss")
	text = strings.Map(func(r rune) rune {
		if (r >= '0' && r <= '9') || (r >= 'a' && r <= 'z') {
			return r
		}
		return ' '
	}, text)
	return strings.Join(strings.Fields(text), " ")
}

// detailPoliceFindings is police_check.findings_for(lang, apartment).
func (s *Pages) detailPoliceFindings(ctx context.Context, lang string, a *detailApt) ([]detailFinding, error) {
	var accepted int
	err := s.pool.QueryRow(ctx, `SELECT 1 FROM submission WHERE apartment_id = $1 AND state IN ('ok', 'ok_duplicate', 'partial') LIMIT 1`, a.ID).Scan(&accepted)
	pending := err == pgx.ErrNoRows
	if err != nil && !pending {
		return nil, err
	}
	form := map[string]string{"uby_ws_user": pyStrip(a.UbyWSUser), "uby_idub": pyStrip(a.UbyIDUB), "uby_mark": pyStrip(a.UbyMark),
		"uby_name": pyStrip(a.UbyName), "addr_street": pyStrip(a.AddrStreet), "addr_house_no": pyStrip(a.AddrHouseNo)}
	var out []detailFinding
	add := func(code, field string, in ...any) {
		out = append(out, detailFinding{Code: code, Field: field, Text: detailT(lang, "police_check."+code, in...)})
	}
	login, mark, name := form["uby_ws_user"], form["uby_mark"], form["uby_name"]
	upper := strings.ToUpper(login)
	if login != "" && !strings.HasPrefix(upper, "UBY-WS") && !strings.HasPrefix(upper, "UBY-TWS") {
		add("login_prefix", "uby_ws_user")
	}
	if suffix := validation.MarkFromWSUser(login); pending && suffix != "" && strings.ToUpper(mark) == suffix {
		add("mark_is_login_suffix", "uby_mark", "mark", suffix)
	}
	street, house := form["addr_street"], form["addr_house_no"]
	if name != "" && (street != "" || house != "") {
		folded := policeFold(name)
		if (street != "" && !strings.Contains(folded, policeFold(street))) || (house != "" && !strings.Contains(folded, policeFold(house))) {
			add("name_address", "uby_name")
		}
	}
	if pending {
		all := true
		for _, f := range detailPoliceFields {
			if form[f] == "" {
				all = false
			}
		}
		if all {
			add("first_filing", "")
		}
	}
	return out, nil
}
