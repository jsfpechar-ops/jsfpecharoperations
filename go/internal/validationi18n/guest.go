package validationi18n

// guest.go is App/app/validation_i18n.guest_localize: the same sentences as the
// guest form shows them, which is not the same table as the host's.
//
// A guest language with its own table (de, es, fr, uk) falls back to the English
// guest table and then to the sentence itself — the guest catalogs have no host
// table behind them. Czech and English use their guest tables and then
// Localize, so a sentence with no guest entry still reaches the host's Czech.
//
// The tables are guest_messages.json, written by App/scripts/go_validation_i18n.py
// from App/app/validation_i18n.py; testdata/guest_localize_golden.json pins
// Python's answers for every sentence and the edge cases.

import (
	_ "embed"
	"encoding/json"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

//go:embed guest_messages.json
var guestMessagesJSON []byte

var (
	guestByLang map[string]map[string]string
	guestEN     map[string]string
	guestCS     map[string]string
)

func init() {
	var t struct {
		Guest map[string]map[string]string `json:"guest"`
		EN    map[string]string            `json:"en"`
		CS    map[string]string            `json:"cs"`
	}
	if err := json.Unmarshal(guestMessagesJSON, &t); err != nil {
		panic("validationi18n: guest_messages.json: " + err.Error())
	}
	guestByLang, guestEN, guestCS = t.Guest, t.EN, t.CS
}

// GuestLocalize is validation_i18n.guest_localize(message, lang): the sentence
// as the guest form should read it, in the guest's language.
func GuestLocalize(message, lang string) string {
	if message == "" {
		return message
	}
	if table, ok := guestByLang[lang]; ok {
		if translated := table[message]; translated != "" {
			return translated
		}
		if translated := guestEN[message]; translated != "" {
			return translated
		}
		return message
	}
	table := guestEN
	if lang == "cs" {
		table = guestCS
	}
	if translated := table[message]; translated != "" {
		return translated
	}
	return Localize(message, lang)
}

// GuestLocalizeIssues is validation_i18n.guest_localize_issues.
func GuestLocalizeIssues(issues []validation.Issue, lang string) []validation.Issue {
	if len(issues) == 0 {
		return issues
	}
	out := make([]validation.Issue, 0, len(issues))
	for _, issue := range issues {
		out = append(out, validation.Issue{
			Field:    issue.Field,
			Message:  GuestLocalize(issue.Message, lang),
			Severity: issue.Severity,
		})
	}
	return out
}
