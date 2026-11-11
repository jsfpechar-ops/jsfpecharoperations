package headcount

import (
	"encoding/json"
	"os"
	"testing"
)

type ruleCase struct {
	Name     string `json:"name"`
	Override *int64 `json:"override"`
	Declared *int64 `json:"declared"`
	Reduced  *int64 `json:"reduced"`
	Want     *int64 `json:"want"`
}

// TestExpectedSharedTable reads the table App/tests/test_headcount_1095.py reads.
func TestExpectedSharedTable(t *testing.T) {
	raw, err := os.ReadFile("testdata/cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []ruleCase
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) < 12 {
		t.Fatalf("the shared table has %d rows, want at least 12", len(cases))
	}
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			got := Expected(c.Override, c.Declared, c.Reduced)
			switch {
			case c.Want == nil && got != nil:
				t.Fatalf("want no count, got %d", *got)
			case c.Want != nil && (got == nil || *got != *c.Want):
				t.Fatalf("want %d, got %v", *c.Want, got)
			}
		})
	}
}
