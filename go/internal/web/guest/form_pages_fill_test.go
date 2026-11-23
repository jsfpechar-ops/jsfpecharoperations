package guest

import (
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/guestcontract"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

func TestFormGuestFieldMapFillsEncryptedPII(t *testing.T) {
	enc, err := encryptSaveFields(testDataEnv, map[string]any{
		"birth_date":    "02011990",
		"doc_number":    "C123456",
		"visa_number":   "V9",
		"res_street":    "Dlouha 1",
		"res_city":      "Praha",
		"signature_png": "",
	})
	if err != nil {
		t.Fatal(err)
	}
	now := func() time.Time { return time.Date(2026, 6, 15, 12, 0, 0, 0, time.UTC) }
	g := &formGuestRow{
		firstName: "Erika", surname: "Novak", nationality: "DEU",
		resCountry: "CZE", purpose: "10", note: "late",
	}
	if g.birthDate, err = decryptGuestField(testDataEnv, now, enc["birth_date_enc"].(string), ""); err != nil {
		t.Fatal(err)
	}
	if g.docNumber, err = decryptGuestField(testDataEnv, now, enc["doc_number_enc"].(string), ""); err != nil {
		t.Fatal(err)
	}
	if g.visaNumber, err = decryptGuestField(testDataEnv, now, enc["visa_number_enc"].(string), ""); err != nil {
		t.Fatal(err)
	}
	if g.resStreet, err = decryptGuestField(testDataEnv, now, enc["res_street_enc"].(string), ""); err != nil {
		t.Fatal(err)
	}
	if g.resCity, err = decryptGuestField(testDataEnv, now, enc["res_city_enc"].(string), ""); err != nil {
		t.Fatal(err)
	}

	view := formView{GuestFields: formGuestFieldMap(g)}
	want := map[string]string{
		"first_name": "Erika", "surname": "Novak", "nationality": "DEU",
		"birth_date": "02011990", "doc_number": "C123456", "visa_number": "V9",
		"res_street": "Dlouha 1", "res_city": "Praha", "res_country": "CZE",
		"purpose": "10", "note": "late",
	}
	for field, exp := range want {
		if got := view.Val(field); got != exp {
			t.Errorf("Val(%q)=%q want %q", field, got, exp)
		}
	}
	if got := view.DisplayBirth(view.Val("birth_date")); got != "02.01.1990" {
		t.Errorf("DisplayBirth=%q want 02.01.1990", got)
	}
}

func TestFormGuestFieldMapOmittingPIIWouldBlankEdit(t *testing.T) {
	g := &formGuestRow{firstName: "Erika", birthDate: "02011990", docNumber: "C123456", resStreet: "Dlouha 1"}
	m := formGuestFieldMap(g)
	for _, field := range []string{"birth_date", "doc_number", "res_street"} {
		if m[field] == "" {
			t.Errorf("%s missing from GuestFields; edit form would submit empty and wipe UbyPort identity", field)
		}
	}
}

func TestFormGuestUnder15UsesArrivalDate(t *testing.T) {
	// Police birth dates are DDMMYYYY. Born 31.12.2011; stay 2026-11-23 → still 14.
	if !formGuestUnder15OnStay("31122011", "2026-11-23") {
		t.Fatal("14-year-old on arrival must be under 15")
	}
	from := time.Date(2026, 11, 23, 0, 0, 0, 0, time.UTC)
	if !validation.CertainlyUnderAge("31122011", &from, guestcontract.UnderSignAge) {
		t.Fatal("shared rule disagrees")
	}
	if formGuestUnder15OnStay("22112011", "2026-11-23") {
		t.Fatal("already 15 on arrival must sign")
	}
}
