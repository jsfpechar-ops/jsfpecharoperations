package ubyport

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"unicode/utf8"
)

const goldenDir = "../../../App/tests/golden/ubyport"

type goldenCase struct {
	Name        string      `json:"name"`
	Apartment   Apartment   `json:"apartment"`
	Reservation Reservation `json:"reservation"`
	Guests      []Guest     `json:"guests"`
	WSA         bool        `json:"wsa"`
}

// build renders one golden case the way the Python golden script does.
func build(c goldenCase) string {
	guests := make([]map[string]any, 0, len(c.Guests))
	for _, g := range c.Guests {
		guests = append(guests, GuestFields(g, c.Reservation))
	}
	return BuildZapisUbytovane(Header(c.Apartment), guests, "GOLDEN-AUTH", c.WSA)
}

// firstDiff reports the first differing byte offset with the bytes around it.
func firstDiff(t *testing.T, got, want string) {
	t.Helper()
	i := 0
	for i < len(got) && i < len(want) && got[i] == want[i] {
		i++
	}
	lo := max(0, i-30)
	show := func(s string) string {
		hi := min(len(s), i+30)
		if lo >= hi {
			return ""
		}
		return s[lo:hi]
	}
	t.Errorf("first difference at byte %d\n got: %q\nwant: %q", i, show(got), show(want))
}

func TestGoldenEnvelopesMatchByteForByte(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join(goldenDir, "cases.json"))
	if err != nil {
		t.Fatal(err)
	}
	var cases []goldenCase
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) == 0 {
		t.Fatal("no golden cases loaded")
	}
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			want, err := os.ReadFile(filepath.Join(goldenDir, c.Name+".xml"))
			if err != nil {
				t.Fatal(err)
			}
			got := build(c)
			if got != string(want) {
				firstDiff(t, got, string(want))
			}
		})
	}
}

func TestUpperSharpSBecomesSS(t *testing.T) {
	f := GuestFields(Guest{Nationality: "ßa"}, Reservation{})
	if f["cNati"] != "SSA" {
		t.Fatalf("cNati = %v, want SSA", f["cNati"])
	}
}

func TestHeaderNameCutToThirtyFiveRunes(t *testing.T) {
	name := strings.Repeat("Č", 40)
	h := Header(Apartment{UbyName: name})
	got := h["uName"]
	if got == nil {
		t.Fatal("uName is nil")
	}
	if n := utf8.RuneCountInString(*got); n != 35 {
		t.Fatalf("uName has %d runes, want 35", n)
	}
	if *got != strings.Repeat("Č", 35) {
		t.Fatalf("uName = %q", *got)
	}
}

func TestEscapingOfAmpersandAngleBrackets(t *testing.T) {
	g := GuestFields(Guest{Surname: `A&<>"'B`}, Reservation{})
	out := BuildZapisUbytovane(map[string]*string{}, []map[string]any{g}, "K&<", false)
	if !strings.Contains(out, `<d:cSurN>A&amp;&lt;&gt;"'B</d:cSurN>`) {
		t.Fatalf("surname not escaped as expected in %s", out)
	}
	if !strings.Contains(out, "<AutentificationCode>K&amp;&lt;</AutentificationCode>") {
		t.Fatal("auth code not escaped as expected")
	}
}

func TestControlCharBecomesSpace(t *testing.T) {
	g := GuestFields(Guest{Surname: "a\x01b\x7f"}, Reservation{})
	out := BuildZapisUbytovane(map[string]*string{}, []map[string]any{g}, "X", false)
	if !strings.Contains(out, "<d:cSurN>a b </d:cSurN>") {
		t.Fatalf("control characters not replaced by spaces in %s", out)
	}
}

func TestPurposeDigitsOnly(t *testing.T) {
	if got := GuestFields(Guest{Purpose: "10 "}, Reservation{})["cPurp"]; got != "10" {
		t.Fatalf(`purpose "10 " gave %v, want 10`, got)
	}
	if got := GuestFields(Guest{Purpose: "1a"}, Reservation{})["cPurp"]; got != nil {
		t.Fatalf(`purpose "1a" gave %v, want nil`, got)
	}
}

func TestEmptyStayFromFallsBackToReservation(t *testing.T) {
	f := GuestFields(Guest{}, Reservation{DateFrom: "2026-10-01", DateTo: "2026-10-04"})
	if f["cFrom"] != "2026-10-01T00:00:00" {
		t.Fatalf("cFrom = %v", f["cFrom"])
	}
	if f["cUntil"] != "2026-10-04T00:00:00" {
		t.Fatalf("cUntil = %v", f["cUntil"])
	}
}
