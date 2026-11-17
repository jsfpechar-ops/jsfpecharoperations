package guestcontract

import (
	_ "embed"
	"encoding/json"
	"reflect"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// guest_form_golden.json is written by App/scripts/guest_form_golden.py from
// the real Python with the clock pinned to 2026-11-01. Regenerate it, never
// edit it by hand.
//
//go:embed testdata/guest_form_golden.json
var guestFormGolden []byte

type goldenIssue struct {
	Field    string `json:"field"`
	Message  string `json:"message"`
	Severity string `json:"severity"`
}

type goldenCase struct {
	Name           string            `json:"name"`
	Form           map[string]string `json:"form"`
	Stay           Stay              `json:"stay"`
	DefaultPurpose string            `json:"default_purpose"`
	Values         map[string]string `json:"values"`
	Issues         []goldenIssue     `json:"issues"`
}

func loadGolden(t *testing.T) (time.Time, []goldenCase) {
	t.Helper()
	var g struct {
		Today string       `json:"today"`
		Cases []goldenCase `json:"cases"`
	}
	if err := json.Unmarshal(guestFormGolden, &g); err != nil {
		t.Fatal(err)
	}
	today, err := time.Parse("2006-01-02", g.Today)
	if err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 30 {
		t.Fatalf("golden has %d cases, want at least 30", len(g.Cases))
	}
	return today, g.Cases
}

func formOf(m map[string]string) GuestForm {
	return GuestForm{
		Surname: m["surname"], FirstName: m["first_name"], BirthDate: m["birth_date"],
		Nationality: m["nationality"], DocNumber: m["doc_number"], VisaNumber: m["visa_number"],
		ResStreet: m["res_street"], ResCity: m["res_city"], ResCountry: m["res_country"],
		Purpose: m["purpose"], Note: m["note"], ParentDocNumber: m["parent_doc_number"],
		Signature: m["signature"], PartySize: m["party_size"], LegalAck: m["legal_ack"] != "",
		ChildSignRole: m["child_sign_role"], SignedBy: m["signed_by"],
	}
}

func valuesOf(g validation.GuestRow) map[string]string {
	return map[string]string{
		"surname": g.Surname, "first_name": g.FirstName, "birth_date": g.BirthDate,
		"nationality": g.Nationality, "doc_number": g.DocNumber, "visa_number": g.VisaNumber,
		"res_street": g.ResStreet, "res_city": g.ResCity, "res_country": g.ResCountry,
		"purpose": g.Purpose, "note": g.Note,
	}
}

func TestNormaliseGuestMatchesPython(t *testing.T) {
	today, cases := loadGolden(t)
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			raw := validation.GuestFormRaw(formOf(c.Form).Fields(), c.DefaultPurpose)
			got := valuesOf(validation.NormaliseGuest(raw, today))
			if !reflect.DeepEqual(got, c.Values) {
				t.Errorf("values\nwant %q\ngot  %q", c.Values, got)
			}
		})
	}
}

func TestCheckNewGuestMatchesPython(t *testing.T) {
	today, cases := loadGolden(t)
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			cfg := FormConfig{DefaultPurpose: c.DefaultPurpose, Stays: []Stay{c.Stay}}
			got := []goldenIssue{}
			for _, i := range CheckNewGuest(formOf(c.Form), cfg, c.Stay, today) {
				got = append(got, goldenIssue{i.Field, i.Message, i.Severity})
			}
			want := c.Issues
			if want == nil {
				want = []goldenIssue{}
			}
			if !reflect.DeepEqual(got, want) {
				t.Errorf("issues\nwant %+v\ngot  %+v", want, got)
			}
		})
	}
}
