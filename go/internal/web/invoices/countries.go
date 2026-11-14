package invoices

// The buyer's country choices: codelists.nationality_options. The police
// code list ("staty") wins when it has at least 150 rows; otherwise the
// bundled ISO list (a copy of go/internal/countries/countries.json, kept in
// step by a test) supplies every country.

import (
	"context"
	_ "embed"
	"encoding/json"
	"sort"
	"strings"
	"unicode"

	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/text/unicode/norm"
)

//go:embed countries.json
var countriesJSON []byte

type countryOption struct{ Code, Label string }

const minCachedCountries = 150

// fold is codelists._fold: accents off, case folded, for sorting only.
func fold(label string) string {
	var b strings.Builder
	for _, r := range norm.NFD.String(label) {
		if unicode.Is(unicode.Mn, r) || unicode.Is(unicode.Mc, r) || unicode.Is(unicode.Me, r) {
			continue
		}
		b.WriteRune(r)
	}
	return strings.ReplaceAll(strings.ToLower(b.String()), "ß", "ss")
}

func sortOptions(options []countryOption) []countryOption {
	sort.SliceStable(options, func(i, j int) bool { return fold(options[i].Label) < fold(options[j].Label) })
	return options
}

func bundled() (map[string]map[string]string, []map[string]string, error) {
	var list []map[string]string
	if err := json.Unmarshal(countriesJSON, &list); err != nil {
		return nil, nil, err
	}
	byCode := make(map[string]map[string]string, len(list))
	for _, c := range list {
		byCode[c["code"]] = c
	}
	return byCode, list, nil
}

// countryOptions is codelists.nationality_options(lang) (_all_countries).
func countryOptions(ctx context.Context, pool *pgxpool.Pool, lang string) ([]countryOption, error) {
	byCode, list, err := bundled()
	if err != nil {
		return nil, err
	}
	rows, err := pool.Query(ctx, `SELECT code, COALESCE(text_cs,''), COALESCE(text_en,'') FROM codelist WHERE kind = 'staty' ORDER BY code`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	type police struct{ code, cs, en string }
	var cached []police
	for rows.Next() {
		var p police
		if err := rows.Scan(&p.code, &p.cs, &p.en); err != nil {
			return nil, err
		}
		cached = append(cached, p)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	var out []countryOption
	if len(cached) >= minCachedCountries {
		for _, p := range cached {
			var label string
			if lang == "en" || lang == "cs" {
				label = p.cs
				if lang == "en" {
					label = p.en
				}
				if label == "" {
					label = p.cs
				}
				if label == "" {
					label = p.code
				}
			} else {
				label = byCode[p.code][lang]
				if label == "" {
					label = p.en
				}
				if label == "" {
					label = p.cs
				}
				if label == "" {
					label = p.code
				}
			}
			out = append(out, countryOption{p.code, label})
		}
		return sortOptions(out), nil
	}
	key := "en"
	switch lang {
	case "cs", "de", "es", "fr", "uk":
		key = lang
	}
	for _, c := range list {
		label := c[key]
		if label == "" {
			label = c["en"]
		}
		out = append(out, countryOption{c["code"], label})
	}
	return sortOptions(out), nil
}
