package mailnotify

import (
	"encoding/json"
	"os"
	"testing"
)

type goldenFile struct {
	PublicBaseURL string       `json:"public_base_url"`
	Cases         []goldenCase `json:"cases"`
}

type goldenCase struct {
	Name           string          `json:"name"`
	Kind           string          `json:"kind"`
	GuestLanguages string          `json:"guest_languages"`
	Input          json.RawMessage `json:"input"`
	Output         struct {
		Subject string `json:"subject"`
		Text    string `json:"text"`
		HTML    string `json:"html"`
	} `json:"output"`
}

func loadGolden(t *testing.T) goldenFile {
	t.Helper()
	raw, err := os.ReadFile("testdata/reminders_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var g goldenFile
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

// firstDiff returns the byte offset where a and b part, or -1 when equal.
func firstDiff(a, b string) int {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	for i := 0; i < n; i++ {
		if a[i] != b[i] {
			return i
		}
	}
	if len(a) != len(b) {
		return n
	}
	return -1
}

func sameBytes(t *testing.T, name, part, got, want string) {
	t.Helper()
	if i := firstDiff(got, want); i >= 0 {
		lo := i - 60
		if lo < 0 {
			lo = 0
		}
		t.Errorf("%s %s differs at byte %d\n got: %q\nwant: %q", name, part, i,
			sub(got, lo, i+60), sub(want, lo, i+60))
	}
}

func sub(s string, lo, hi int) string {
	if hi > len(s) {
		hi = len(s)
	}
	if lo > hi {
		return ""
	}
	return s[lo:hi]
}

func TestReminderGolden(t *testing.T) {
	g := loadGolden(t)
	if len(g.Cases) == 0 {
		t.Fatal("golden has no cases")
	}
	for _, c := range g.Cases {
		SetGuestLanguages(c.GuestLanguages)
		var got Content
		switch c.Kind {
		case "guest":
			var in ReminderGuestInput
			if err := json.Unmarshal(c.Input, &in); err != nil {
				t.Fatalf("%s: %v", c.Name, err)
			}
			got = BuildReminderGuest(g.PublicBaseURL, in)
		case "host":
			var in ReminderHostInput
			if err := json.Unmarshal(c.Input, &in); err != nil {
				t.Fatalf("%s: %v", c.Name, err)
			}
			got = BuildReminderHost(g.PublicBaseURL, in)
		default:
			t.Fatalf("%s: unknown kind %q", c.Name, c.Kind)
		}
		sameBytes(t, c.Name, "subject", got.Subject, c.Output.Subject)
		sameBytes(t, c.Name, "text", got.Text, c.Output.Text)
		sameBytes(t, c.Name, "html", got.HTML, c.Output.HTML)
	}
	SetGuestLanguages("")
}

func TestPyFormatEdges(t *testing.T) {
	cases := []struct {
		text string
		args Args
		want string
	}{
		{"%(filled)s of %(expected)s", Args{"filled": 1, "expected": nil}, "1 of None"},
		{"%(expected)d", Args{"expected": nil}, "%(expected)d"},
		{"%(expected)d", Args{"expected": 3}, "3"},
		{"done 100%", Args{"x": 1}, "done 100%"},
		{"100%% %(x)s", Args{"x": "a"}, "100% a"},
		{"%(missing)s", Args{"x": 1}, "%(missing)s"},
		{"no markers", Args{"x": 1}, "no markers"},
	}
	for _, c := range cases {
		if got := lookup(map[string]string{"k": c.text}, nil, "k", c.args); got != c.want {
			t.Errorf("format %q: got %q want %q", c.text, got, c.want)
		}
	}
}

func TestLanguageNormalisation(t *testing.T) {
	SetGuestLanguages("")
	if got := GuestLanguage("SK-sk"); got != "cs" {
		t.Errorf("GuestLanguage(SK-sk) = %q", got)
	}
	if got := GuestLanguage("de"); got != "en" {
		t.Errorf("GuestLanguage(de) with defaults = %q, want en", got)
	}
	SetGuestLanguages("de,fr")
	if got := GuestLanguage("de"); got != "de" {
		t.Errorf("GuestLanguage(de) enabled = %q", got)
	}
	SetGuestLanguages("")
	if got := HostLanguage("VI-vn"); got != "vi" {
		t.Errorf("HostLanguage(VI-vn) = %q", got)
	}
	if got := HostLanguage("de"); got != "en" {
		t.Errorf("HostLanguage(de) = %q", got)
	}
}
