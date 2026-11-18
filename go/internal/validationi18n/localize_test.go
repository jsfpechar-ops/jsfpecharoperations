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
