package ai

import (
	"net/http"
	"os"
	"regexp"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

func TestGuideParseID(t *testing.T) {
	cases := []struct {
		in   string
		want int64
		ok   bool
	}{
		{"12", 12, true}, {" 7 ", 7, true}, {"+3", 3, true}, {"1_000", 1000, true}, {"5.0", 5, true},
		{"abc", 0, false}, {"", 0, false}, {"1.5", 0, false}, {"1__0", 0, false},
		{"99999999999999999999", 0, true}, // past int64: a valid int that matches no row
	}
	for _, c := range cases {
		got, ok := guideParseID(c.in)
		if got != c.want || ok != c.ok {
			t.Errorf("guideParseID(%q) = %d, %v; want %d, %v", c.in, got, ok, c.want, c.ok)
		}
	}
}

func TestGuideStamp(t *testing.T) {
	if got := guideStamp(guideTestNow); got != "2026-11-13T10:00:00+00:00" {
		t.Errorf("guideStamp = %q", got)
	}
}

// The routes of every guide brief together: no pattern twice, and building the
// list never touches the pool.
func TestGuideRoutesUniqueAndPoolFree(t *testing.T) {
	routes := GuideRoutes(nil, os.Getenv, os.LookupEnv, guideTestClock)
	seen := map[string]bool{}
	for _, r := range routes {
		if seen[r.Pattern] {
			t.Errorf("pattern registered twice: %s", r.Pattern)
		}
		seen[r.Pattern] = true
	}
	mux := http.NewServeMux()
	for _, r := range routes {
		mux.Handle(r.Pattern, r.Handler) // panics on a conflicting pattern
	}
}

var guideStaticKey = regexp.MustCompile(`\(?\bt "([a-z0-9_.]+)"`)

// Every literal t "key" of the guide templates has text in the guide or the
// layout catalog, in English and Czech (a key built at run time is checked by
// the key lists in guide/i18n_keys.txt).
func TestGuideTemplatesUseKnownKeys(t *testing.T) {
	entries, err := guideTemplateFiles.ReadDir("guide/templates")
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range entries {
		raw, err := guideTemplateFiles.ReadFile("guide/templates/" + e.Name())
		if err != nil {
			t.Fatal(err)
		}
		for _, m := range guideStaticKey.FindAllStringSubmatch(string(raw), -1) {
			key := m[1]
			if !strings.Contains(key, ".") {
				continue
			}
			for _, lang := range []string{"en", "cs"} {
				_, inGuide := guideCatalog[lang][key]
				_, inLayout := layout.Strings[lang][key]
				if !inGuide && !inLayout {
					t.Errorf("%s: key %q has no %s text", e.Name(), key, lang)
				}
			}
		}
	}
}

// Every key of guide/i18n_keys.txt that is not a prefix line is in the catalog.
func TestGuideCatalogHasEveryKey(t *testing.T) {
	raw, err := os.ReadFile("guide/i18n_keys.txt")
	if err != nil {
		t.Fatal(err)
	}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") || strings.HasSuffix(line, ".*") {
			continue
		}
		for _, lang := range []string{"en", "cs"} {
			if _, ok := guideCatalog[lang][line]; !ok {
				t.Errorf("key %q has no %s text", line, lang)
			}
		}
	}
	for _, prefix := range []string{"guest_guide.kind.checkin.title", "guest_guide.topic.arrival", "flash.guest_guide.saved", "flash.error.guide_too_long", "leon_page.title"} {
		if _, ok := guideCatalog["en"][prefix]; !ok {
			t.Errorf("wildcard key %q missing", prefix)
		}
	}
}
