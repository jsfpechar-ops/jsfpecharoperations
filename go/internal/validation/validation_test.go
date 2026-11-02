package validation

import (
	_ "embed"
	"encoding/json"
	"testing"
	"time"
)

// golden.json is written by App/scripts/validation_golden.py from the Python
// functions with the clock pinned to 2026-11-01.
//
//go:embed testdata/golden.json
var goldenJSON []byte

type goldenGuest struct {
	Name     string            `json:"name"`
	Guest    map[string]string `json:"guest"`
	DateFrom string            `json:"date_from"`
	DateTo   string            `json:"date_to"`
	Raw      map[string]string `json:"raw"`
	Issues   [][3]string       `json:"issues"`
	Complete bool              `json:"complete"`
}

type goldenApartment struct {
	Name   string            `json:"name"`
	Row    map[string]string `json:"row"`
	Issues [][3]string       `json:"issues"`
}

type golden struct {
	Today     string            `json:"today"`
	Guest     []goldenGuest     `json:"guest"`
	Apartment []goldenApartment `json:"apartment"`
}

func compareIssues(t *testing.T, got []Issue, want [][3]string) {
	t.Helper()
	if len(got) != len(want) {
		t.Fatalf("got %d issues, want %d\ngot:  %+v\nwant: %q", len(got), len(want), got, want)
	}
	for i, w := range want {
		if got[i].Field != w[0] || got[i].Message != w[1] || got[i].Severity != w[2] {
			t.Errorf("issue %d:\ngot:  %q %q %q\nwant: %q %q %q",
				i, got[i].Field, got[i].Message, got[i].Severity, w[0], w[1], w[2])
		}
	}
}

func TestGuestGolden(t *testing.T) {
	var gd golden
	if err := json.Unmarshal(goldenJSON, &gd); err != nil {
		t.Fatal(err)
	}
	today, err := time.Parse("2006-01-02", gd.Today)
	if err != nil {
		t.Fatal(err)
	}
	if len(gd.Guest) < 80 {
		t.Fatalf("golden has %d guest cases, want at least 80", len(gd.Guest))
	}
	for _, c := range gd.Guest {
		t.Run(c.Name, func(t *testing.T) {
			m := c.Guest
			row := GuestRow{
				Surname: m["surname"], FirstName: m["first_name"], BirthDate: m["birth_date"],
				Nationality: m["nationality"], DocNumber: m["doc_number"], VisaNumber: m["visa_number"],
				ResStreet: m["res_street"], ResCity: m["res_city"], ResCountry: m["res_country"],
				Purpose: m["purpose"], Note: m["note"], StayFrom: m["stay_from"],
				StayTo: m["stay_to"], SignaturePNG: m["signature_png"],
			}
			if c.Raw != nil {
				from, to := stayDates(row, c.DateFrom, c.DateTo)
				got := validateGuest(row, from, to, today, c.Raw)
				compareIssues(t, got, c.Issues)
				if complete := len(ErrorsOnly(got)) == 0; complete != c.Complete {
					t.Errorf("complete: got %v, want %v", complete, c.Complete)
				}
				return
			}
			compareIssues(t, GuestIssues(row, c.DateFrom, c.DateTo, today), c.Issues)
			if complete := GuestIsComplete(row, c.DateFrom, c.DateTo, today); complete != c.Complete {
				t.Errorf("complete: got %v, want %v", complete, c.Complete)
			}
		})
	}
}

func TestApartmentGolden(t *testing.T) {
	var gd golden
	if err := json.Unmarshal(goldenJSON, &gd); err != nil {
		t.Fatal(err)
	}
	if len(gd.Apartment) < 25 {
		t.Fatalf("golden has %d apartment cases, want at least 25", len(gd.Apartment))
	}
	for _, c := range gd.Apartment {
		t.Run(c.Name, func(t *testing.T) {
			compareIssues(t, ValidateApartment(c.Row), c.Issues)
		})
	}
}
