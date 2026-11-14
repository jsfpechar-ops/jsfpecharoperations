package ical

import (
	"os"
	"testing"
	"time"
)

// testdata/sample_airbnb_20261114.golden is what App/app/sample_calendar.py
// sample_airbnb_ics returns when the Czech date is 2026-11-14 (Python 3.12).
func TestSampleAirbnbICSMatchesPython(t *testing.T) {
	want, err := os.ReadFile("testdata/sample_airbnb_20261114.golden")
	if err != nil {
		t.Fatal(err)
	}
	// the time of day and the zone do not matter, only the date
	for _, today := range []time.Time{
		time.Date(2026, 11, 14, 0, 0, 0, 0, time.UTC),
		time.Date(2026, 11, 14, 23, 59, 59, 0, time.FixedZone("CET", 3600)),
	} {
		if got := SampleAirbnbICS(today); got != string(want) {
			t.Errorf("sample calendar differs from Python for %v:\n%s", today, got)
		}
	}
}

// Across a year end the dates roll over and all ten events are written.
func TestSampleAirbnbICSYearEnd(t *testing.T) {
	events := SampleAirbnbICS(time.Date(2026, 12, 30, 0, 0, 0, 0, time.UTC))
	if n := countOf(events, "BEGIN:VEVENT"); n != 10 {
		t.Errorf("%d events, want 10", n)
	}
	if !contains(events, "DTSTART;VALUE=DATE:20270213") { // 2026-12-30 + 45 days across the year end
		t.Error("year end not handled")
	}
}

func countOf(s, sub string) int {
	n := 0
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			n++
		}
	}
	return n
}

func contains(s, sub string) bool { return countOf(s, sub) > 0 }
