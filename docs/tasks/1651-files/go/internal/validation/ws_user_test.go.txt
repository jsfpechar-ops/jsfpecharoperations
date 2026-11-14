package validation

import (
	"encoding/json"
	"os"
	"testing"
)

// TestMarkFromWSUserMatchesPython runs the cases of testdata/ws_user_golden.json,
// whose answers were produced by App/app/validation.py mark_from_ws_user
// (Python 3.12), including its Unicode case-folding edges.
func TestMarkFromWSUserMatchesPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/ws_user_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct{ In, Out string }
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) < 25 {
		t.Fatalf("only %d cases", len(cases))
	}
	for _, c := range cases {
		if got := MarkFromWSUser(c.In); got != c.Out {
			t.Errorf("MarkFromWSUser(%q) = %q, Python says %q", c.In, got, c.Out)
		}
	}
}
