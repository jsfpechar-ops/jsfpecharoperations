package guest

import (
	"testing"
	"time"
)

func TestBookedLevelWindow(t *testing.T) {
	today := mustDate("2026-06-15")
	cases := []struct {
		from, to, want string
	}{
		{"2026-06-17", "2026-06-19", "everyone"},
		{"2026-06-16", "2026-06-18", "booked"},
		{"2026-06-15", "2026-06-17", "booked"},
		{"2026-06-13", "2026-06-15", "booked"},
		{"2026-06-12", "2026-06-14", "everyone"},
		{"", "", "everyone"},
	}
	for _, c := range cases {
		if got := BookedLevel(c.from, c.to, today); got != c.want {
			t.Fatalf("%s..%s got %q want %q", c.from, c.to, got, c.want)
		}
	}
}

func mustDate(s string) time.Time {
	t, err := time.Parse("2006-01-02", s)
	if err != nil {
		panic(err)
	}
	return t
}
