package validation_test

import (
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validationi18n"
)

func TestWSUserUnderscoreMark(t *testing.T) {
	cases := []struct {
		in, want string
	}{
		{"UBY-WS_AAKLI", "AAKLI"},
		{"uby-ws_ab1234", "AB1234"},
		{"  UBY-WS_MLJNO  ", "MLJNO"},
		{"UBY-WSab12cd", ""},
		{"uby-tws1ab45", ""},
		{"UBY-WS_OLD", ""},
		{"ub1234567", ""},
		{"", ""},
	}
	for _, tc := range cases {
		if got := validation.WSUserUnderscoreMark(tc.in); got != tc.want {
			t.Errorf("WSUserUnderscoreMark(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

func TestValidateApartmentUnderscoreMarkMatch(t *testing.T) {
	base := func(wsUser, mark string) map[string]string {
		return map[string]string{
			"uby_idub":        "ABCDEFGH1234",
			"uby_mark":        mark,
			"uby_name":        "Penzion U Lesa",
			"uby_contact":     "Jan Novak",
			"addr_okres":      "Praha",
			"addr_obec":       "Praha",
			"addr_street":     "Vinohradska",
			"addr_house_no":   "12",
			"addr_zip":        "12000",
			"uby_ws_user":     wsUser,
			"uby_ws_password": "secret",
			"legal_entity_id": "1",
		}
	}

	hasMismatch := func(issues []validation.Issue) bool {
		for _, is := range issues {
			if is.Field == "uby_mark" && is.Message == validation.MarkMismatchMessage && is.Severity == "error" {
				return true
			}
		}
		return false
	}

	if issues := validation.ErrorsOnly(validation.ValidateApartment(base("UBY-WS_AAKLI", "AAKLI"))); len(issues) != 0 {
		t.Fatalf("matching mark got unexpected errors: %+v", issues)
	}
	if issues := validation.ErrorsOnly(validation.ValidateApartment(base("uby-ws_aakli", "AAKLI"))); len(issues) != 0 {
		t.Fatalf("case-insensitive matching mark got unexpected errors: %+v", issues)
	}
	if issues := validation.ErrorsOnly(validation.ValidateApartment(base("UBY-WS_AAKLI", "WRONG"))); !hasMismatch(issues) {
		t.Fatalf("expected mismatch error for UBY-WS_AAKLI vs WRONG, got: %+v", issues)
	}
	if issues := validation.ErrorsOnly(validation.ValidateApartment(base("UBY-WS_AB1234", "AB1235"))); !hasMismatch(issues) {
		t.Fatalf("expected mismatch error for 6-char UBY-WS_AB1234 vs AB1235, got: %+v", issues)
	}
	if issues := validation.ErrorsOnly(validation.ValidateApartment(base("UBY-WSab12cd", "OTHER"))); hasMismatch(issues) {
		t.Fatalf("non-underscore login should not trigger underscore mismatch error: %+v", issues)
	}
	if issues := validation.ErrorsOnly(validation.ValidateApartment(base("uby-tws1ab45", "OTHER"))); hasMismatch(issues) {
		t.Fatalf("test login should not trigger underscore mismatch error: %+v", issues)
	}

	// Verify localization exists for cs and vi.
	for _, lang := range []string{"cs", "vi"} {
		got := validationi18n.Localize(validation.MarkMismatchMessage, lang)
		if got == "" || got == validation.MarkMismatchMessage {
			t.Errorf("Localize(MarkMismatchMessage, %q) = %q, want translated text", lang, got)
		}
	}
}
