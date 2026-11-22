package validationi18n

// purpose.go is App/app/validation.purpose_label and App/app/codelists.purpose_options:
// the purpose-of-stay select on the guest form, which the guest reads in their own
// language. The host app asks for the English list, so this table is only the guest
// side's business.
//
// purpose_labels.json is written by App/scripts/go_validation_i18n.py from
// App/app/validation.py; testdata/purpose_golden.json pins Python's answers for every
// language and code, plus the codes the bundle does not carry.

import (
	_ "embed"
	"encoding/json"
	"sort"
	"strings"
)

//go:embed purpose_labels.json
var purposeLabelsJSON []byte

var purposeByLang map[string]map[string]string

func init() {
	if err := json.Unmarshal(purposeLabelsJSON, &purposeByLang); err != nil {
		panic("validationi18n: purpose_labels.json: " + err.Error())
	}
	for _, code := range purposeOrder {
		if purposeByLang["en"][code] == "" {
			panic("validationi18n: purpose " + code + " is missing from purpose_labels.json")
		}
	}
}

// PurposeLabel is validation.purpose_label(code, lang): the purpose as a person
// reads it — no police code, sentence case. An unknown code answers itself.
func PurposeLabel(code, lang string) string {
	if label := purposeByLang[lang][code]; label != "" {
		return label
	}
	if label := purposeByLang["en"][code]; label != "" {
		return label
	}
	return code
}

// PurposeRow is one UbyPort codelist row: the code the police issued, the code the
// service calls it (extra when it has one), and its two texts.
type PurposeRow struct {
	Code   string
	Extra  string
	TextCS string
	TextEN string
}

// PurposeOption is one select choice: the code submitted, the label shown.
type PurposeOption struct {
	Code  string
	Label string
}

// PurposeOptions is codelists.purpose_options(lang). The bundled sentence-case label
// is the label source; the fetched police text_cs/text_en is only a fallback for a
// code the bundle does not carry. With no rows it answers the bundled list, which is
// what the audit's seed produces.
func PurposeOptions(lang string, rows []PurposeRow) []PurposeOption {
	if len(rows) == 0 {
		out := make([]PurposeOption, 0, len(purposeOrder))
		for _, code := range purposeOrder {
			out = append(out, PurposeOption{Code: code, Label: PurposeLabel(code, lang)})
		}
		return out
	}
	out := make([]PurposeOption, 0, len(rows))
	for _, row := range rows {
		code := strings.TrimSpace(row.Extra)
		if code == "" {
			code = row.Code
		}
		label := firstText(purposeByLang[lang][code], purposeByLang["en"][code],
			row.TextEN, row.TextCS, code)
		if lang == "cs" {
			// Czech reads its own label first and never borrows the English one.
			label = firstText(purposeByLang["cs"][code], row.TextCS, row.TextEN, code)
		}
		out = append(out, PurposeOption{Code: code, Label: label})
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].Code < out[j].Code })
	return out
}

// purposeOrder is validation.PURPOSES' own code sequence: the codes are not
// alphabetical (10 follows 07, 27 comes after 13), and the select renders in it.
var purposeOrder = []string{
	"00", "01", "02", "03", "04", "05", "06", "07", "10", "11", "12", "13", "27", "93", "99",
}

func firstText(parts ...string) string {
	for _, part := range parts {
		if strings.TrimSpace(part) != "" {
			return part
		}
	}
	return ""
}
