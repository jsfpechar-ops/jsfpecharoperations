package ical

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// golden renders a parse result the way App/scripts/ical_golden.py does:
// sorted keys, two-space indent, no HTML escaping, trailing newline.
func golden(text string) ([]byte, error) {
	var generic any
	events, err := ParseEvents(text)
	if err != nil {
		generic = map[string]any{"error": true}
	} else {
		raw, err := json.Marshal(events)
		if err != nil {
			return nil, err
		}
		if err := json.Unmarshal(raw, &generic); err != nil {
			return nil, err
		}
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "  ")
	if err := enc.Encode(generic); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

func TestGoldenFixtures(t *testing.T) {
	names, err := filepath.Glob("testdata/*.ics")
	if err != nil {
		t.Fatal(err)
	}
	if len(names) < 14 {
		t.Fatalf("want at least 14 fixtures, got %d", len(names))
	}
	for _, ics := range names {
		src, err := os.ReadFile(ics)
		if err != nil {
			t.Fatal(err)
		}
		want, err := os.ReadFile(strings.TrimSuffix(ics, ".ics") + ".json")
		if err != nil {
			t.Fatal(err)
		}
		got, err := golden(string(src))
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(got, want) {
			t.Errorf("%s:\ngot:\n%s\nwant:\n%s", ics, got, want)
		}
	}
}

func TestIsBlock(t *testing.T) {
	cases := []struct {
		summary string
		want    bool
	}{
		{"Reserved", false},
		{"Airbnb (Not available)", true},
		{"CLOSED - Not available", false},
		{"closed", true},
		{"Busy", true},
		{"Busy Bee", false},
		{"  reserved  ", false},
		{"Nedostupné", true},
		{"Blokováno", true},
		{"Owner block", true},
		{"Maintenance", true},
		{"Preparation day", true},
	}
	for _, c := range cases {
		if got := IsBlock(c.summary); got != c.want {
			t.Errorf("IsBlock(%q) = %v, want %v", c.summary, got, c.want)
		}
	}
}

func TestPlatformOf(t *testing.T) {
	cases := []struct {
		url, text, want string
	}{
		{"https://www.airbnb.com/ical/x.ics", "", "airbnb"},
		{"", "PRODID: Booking.com", "booking"},
		{"https://example.com/cal.ics", "x", "ical"},
		{"", strings.Repeat("a", 800) + "airbnb", "ical"},
		{"", "ICS for ECHALUPY", "echalupy"},
		{"https://calendar.google.com/x", "", "google"},
	}
	for _, c := range cases {
		if got := PlatformOf(c.url, c.text); got != c.want {
			t.Errorf("PlatformOf(%q, %q) = %q, want %q", c.url, c.text, got, c.want)
		}
	}
}
