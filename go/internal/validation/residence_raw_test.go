package validation

import "testing"

// A residence typed in another alphabet is refused with the non-Latin message,
// not "required", on the guest form path (raw input present).
func TestValidateResidenceNonLatinRaw(t *testing.T) {
	issues := validateResidence("", "", "CZ", "Пр", "")
	for _, i := range issues {
		if i.Field == "res_street" && i.Message == nonLatinMessage {
			return
		}
	}
	t.Fatalf("want non-Latin message for res_street, got %+v", issues)
}
