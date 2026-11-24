package validation

import (
	"testing"
	"time"
)

// TestDisplayBirthDate checks the stay-page row format against Python display_birth_date.
func TestDisplayBirthDate(t *testing.T) {
	today := time.Date(2026, 11, 24, 0, 0, 0, 0, time.UTC)
	cases := map[string]string{
		"15031990":   "15.03.1990",
		"15.03.1990": "15.03.1990",
		"15/03/1990": "15.03.1990",
		"150390":     "15.03.1990",
		"1503":       "1503",
		"":           "",
		"  ":         "",
	}
	for in, want := range cases {
		if got := DisplayBirthDate(in, today); got != want {
			t.Errorf("DisplayBirthDate(%q) = %q, want %q", in, got, want)
		}
	}
}
