package validationi18n

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// TestLocalizeGolden replays testdata/localize_golden.json: Python's answer of
// validation_i18n.localize for every table sentence and the edge cases.
func TestLocalizeGolden(t *testing.T) {
	raw, err := os.ReadFile("testdata/localize_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases [][3]string
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) < 200 {
		t.Fatalf("golden has %d cases, want at least 200", len(cases))
	}
	for _, c := range cases {
		if got := Localize(c[1], c[0]); got != c[2] {
			t.Errorf("Localize(%q, %q) = %q, want %q", c[1], c[0], got, c[2])
		}
	}
}

func TestLocalizeTablesLoaded(t *testing.T) {
	if len(csMessages) == 0 || len(viMessages) == 0 || len(patterns) != 2 {
		t.Fatalf("tables: cs %d, vi %d, patterns %d", len(csMessages), len(viMessages), len(patterns))
	}
	if got := Localize("Street is required.", "cs"); got == "Street is required." {
		t.Fatalf("the create form's street sentence has no Czech entry: %q", got)
	}
	if got := Localize("Must be at most 42 characters.", "cs"); got != "Nejvýše 42 znaků." {
		t.Fatalf("pattern: %q", got)
	}
}

// TestGuestLocalizeGolden replays testdata/guest_localize_golden.json: Python's
// answer of validation_i18n.guest_localize for every guest sentence, the host
// sentences that fall through to Localize, and the edge cases.
func TestGuestLocalizeGolden(t *testing.T) {
	raw, err := os.ReadFile("testdata/guest_localize_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases [][3]string
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) < 500 {
		t.Fatalf("golden has %d cases, want at least 500", len(cases))
	}
	for _, c := range cases {
		if got := GuestLocalize(c[1], c[0]); got != c[2] {
			t.Errorf("GuestLocalize(%q, %q) = %q, want %q", c[1], c[0], got, c[2])
		}
	}
}

func TestGuestLocalizeTablesLoaded(t *testing.T) {
	if len(guestByLang) != 4 || len(guestEN) == 0 || len(guestCS) == 0 {
		t.Fatalf("guest tables: %d languages, en %d, cs %d", len(guestByLang), len(guestEN), len(guestCS))
	}
	// The guest form's own wording: "Surname is required." names the field the
	// guest sees, not the host's sentence.
	if got := GuestLocalize("Surname is required.", "uk"); got == "Surname is required." {
		t.Fatalf("uk guest table not used: %q", got)
	}
	// No guest entry for the sentence, a guest language: English, not the sentence.
	if got := GuestLocalize("Street cannot consist of digits only.", "de"); got == "" {
		t.Fatalf("de fallback: %q", got)
	}
	// Czech has no guest entry either, so the host table answers.
	if got := GuestLocalize("Must be at most 42 characters.", "cs"); got != "Nejvýše 42 znaků." {
		t.Fatalf("cs fallthrough to Localize: %q", got)
	}
}

// TestPurposeGolden replays App/app/validation.purpose_label through the guest form's
// select, language by language, including the codes the bundle does not carry.
func TestPurposeGolden(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("testdata", "purpose_golden.json"))
	if err != nil {
		t.Fatal(err)
	}
	var golden struct {
		Options map[string][]struct {
			Code  string `json:"code"`
			Label string `json:"label"`
		} `json:"options"`
		Unknown [][3]string `json:"unknown"`
	}
	if err := json.Unmarshal(raw, &golden); err != nil {
		t.Fatal(err)
	}
	if len(golden.Options) < 8 {
		t.Fatalf("golden has %d languages, want at least 8", len(golden.Options))
	}
	for lang, want := range golden.Options {
		got := PurposeOptions(lang, nil)
		if len(got) != len(want) {
			t.Fatalf("%q: %d options, want %d", lang, len(got), len(want))
		}
		for i := range want {
			if got[i].Code != want[i].Code || got[i].Label != want[i].Label {
				t.Fatalf("%q option %d = %v, want %v", lang, i, got[i], want[i])
			}
		}
	}
	for _, c := range golden.Unknown {
		if got := PurposeLabel(c[1], c[0]); got != c[2] {
			t.Errorf("PurposeLabel(%q, %q) = %q, want %q", c[1], c[0], got, c[2])
		}
	}
	// The fetched codelist rows label a code the bundle does not carry from the
	// police text, and Czech never borrows the English label.
	rows := []PurposeRow{
		{Code: "ZZ", Extra: "77", TextCS: "Nový účel", TextEN: "New purpose"},
		{Code: "10", TextCS: "x", TextEN: "y"},
	}
	if got := PurposeOptions("cs", rows); got[1].Code != "77" || got[1].Label != "Nový účel" || got[0].Label != "Turistika" {
		t.Fatalf("cs rows: %v", got)
	}
	if got := PurposeOptions("de", rows); got[1].Label != "Neuer Zweck" && got[1].Label != "New purpose" {
		t.Fatalf("de rows: %v", got)
	}
	if got := PurposeOptions("de", rows); got[0].Label != "Tourismus" {
		t.Fatalf("de bundled label: %v", got[0])
	}
}
