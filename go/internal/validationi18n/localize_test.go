package validationi18n

import (
	"encoding/json"
	"os"
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
