package guest

// form_issues.go is the guest form's two passes over validation.py's sentences,
// in Python's order: guest.py:2518
//
//     issues = _localize_issues(_name_latin_issues(issues, lang), lang)
//
// The validator writes English; the guest reads Czech or Ukrainian. Keeping the
// two rules separate mirrors Python, where each has its own reason: one names
// the field that holds another alphabet, the other words the sentence for a
// guest and turns the "note" refusal into a request for the person's own
// document number.

import (
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validationi18n"
)

// latinFieldLabels is guest._LATIN_FIELD_LABELS: field → the catalog key of the
// label the guest sees next to it.
var latinFieldLabels = map[string]string{
	"surname":    "surname",
	"first_name": "first_name",
	"res_street": "res_street",
	"res_city":   "res_city",
}

// guestIssueFields is guest._GUEST_ISSUE_FIELDS: the field the refusal is shown
// under, which is not always the field the validator named.
var guestIssueFields = map[string]string{"note": "doc_number"}

// guestIssueMessages is guest._GUEST_ISSUE_MESSAGES: a refusal worded for the
// guest, keyed by the field validation.py used.
var guestIssueMessages = map[string]map[string]string{
	"note": {
		"en": "Enter this person's own passport or ID card number.",
		"cs": "Zadejte číslo vlastního pasu nebo občanského průkazu této osoby.",
		"de": "Geben Sie die Nummer des eigenen Reisepasses oder Personalausweises dieser Person ein.",
		"es": "Introduzca el número del pasaporte o documento de identidad propio de esta persona.",
		"fr": "Saisissez le numéro du passeport ou de la carte d'identité de cette personne.",
		"uk": "Введіть номер власного паспорта або посвідчення особи цієї людини.",
	},
}

// nameLatinIssues is guest._name_latin_issues: a sentence for another alphabet
// now names the field it is about. Validation is not relaxed — the same fields
// fail for the same input.
func nameLatinIssues(issues []validation.Issue, lang string) []validation.Issue {
	if len(issues) == 0 {
		return issues
	}
	out := make([]validation.Issue, 0, len(issues))
	for _, issue := range issues {
		if key, ok := latinFieldLabels[issue.Field]; ok && issue.Message == validation.NON_LATIN_MESSAGE {
			issue.Message = stringsCatalog.T(lang, "latin_only_error", map[string]any{
				"field": stringsCatalog.T(lang, key, nil),
			})
		}
		out = append(out, issue)
	}
	return out
}

// localizeIssues is guest._localize_issues: each sentence in the guest's
// language, then the field override.
func localizeIssues(issues []validation.Issue, lang string) []validation.Issue {
	if len(issues) == 0 {
		return issues
	}
	out := make([]validation.Issue, 0, len(issues))
	for _, issue := range validationi18n.GuestLocalizeIssues(issues, lang) {
		// Python returns the issue untouched unless the field has an override,
		// so a sentence with none keeps the field validation.py named.
		if override, ok := guestIssueMessages[issue.Field]; ok {
			message := override[lang]
			if message == "" {
				message = override["en"]
			}
			issue.Message = message
			if renamed, ok := guestIssueFields[issue.Field]; ok {
				issue.Field = renamed
			}
		}
		out = append(out, issue)
	}
	return out
}
