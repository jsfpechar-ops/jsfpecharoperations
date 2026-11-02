package mail

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// TestCancelledWithGuestsMatchesPython compares each golden case written by
// App/scripts/mail_golden.py with the Go builder, byte for byte.
func TestCancelledWithGuestsMatchesPython(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join(goldenDir, "cancelled_cases.json"))
	if err != nil {
		t.Fatal(err)
	}
	cases := parseCancelledCases(t, raw)
	if len(cases) == 0 {
		t.Fatal("no cancelled golden cases")
	}
	for _, c := range cases {
		got, err := BuildCancelledWithGuests(goldenAppBase, goldenPublicBase, "en", c.PropertyName, c.DateFrom, c.Variant, c.ReservationID)
		if err != nil {
			t.Fatalf("%s: %v", c.Name, err)
		}
		want := map[string]string{
			".subject.txt": got.Subject,
			".text.txt":    got.Text,
			".html":        got.HTML,
		}
		for suffix, value := range want {
			file := filepath.Join(goldenDir, c.Name+suffix)
			expected, err := os.ReadFile(file)
			if err != nil {
				t.Fatal(err)
			}
			if string(expected) != value {
				t.Errorf("%s%s differs from Python", c.Name, suffix)
			}
		}
	}
}

// TestCancelledWithGuestsRefusesUnknownVariant keeps the variant list closed.
func TestCancelledWithGuestsRefusesUnknownVariant(t *testing.T) {
	if _, err := BuildCancelledWithGuests(goldenAppBase, goldenPublicBase, "en", "Byt", "2026-05-06", "gone", 1); err != ErrCancelledVariant {
		t.Fatalf("want ErrCancelledVariant, got %v", err)
	}
	if _, err := BuildCancelledWithGuests(goldenAppBase, goldenPublicBase, "cs", "Byt", "2026-05-06", "cancelled", 1); err != ErrLanguage {
		t.Fatalf("want ErrLanguage, got %v", err)
	}
}

type cancelledCase struct {
	Name          string `json:"name"`
	Variant       string `json:"variant"`
	PropertyName  string `json:"property_name"`
	DateFrom      string `json:"date_from"`
	ReservationID int64  `json:"reservation_id"`
}

func parseCancelledCases(t *testing.T, raw []byte) []cancelledCase {
	t.Helper()
	var cases []cancelledCase
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	return cases
}
