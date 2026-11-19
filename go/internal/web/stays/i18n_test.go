package stays

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

// Keys the stays list surface may read (templates + handlers + post redirect).
var staysKeyRE = regexp.MustCompile(`"((?:stays|send|host|common|confirm|status|hint|tabs|csv|demo|how|dashboard|nav|calendar|flash|setup|onboarding)\.[a-z0-9_.]+)"`)

func TestEveryKeyTheCodeReadsIsInTheCatalog(t *testing.T) {
	for _, lang := range []string{"en", "cs"} {
		for _, file := range staysSourceFiles(t) {
			raw, err := os.ReadFile(file)
			if err != nil {
				t.Fatal(err)
			}
			for _, m := range staysKeyRE.FindAllStringSubmatch(string(raw), -1) {
				key := m[1]
				if strings.HasSuffix(key, ".") {
					continue
				}
				if staysDynamicKey(key) {
					continue
				}
				if _, ok := catalog[lang][key]; !ok {
					t.Errorf("%s: %q is not in the %s catalog; add to i18n_keys.txt and regenerate", filepath.Base(file), key, lang)
				}
			}
		}
	}
	if catalog.T("cs", "stays.title", nil) == "stays.title" {
		t.Error("Czech stays catalog is empty")
	}
}

func staysDynamicKey(key string) bool {
	return strings.HasPrefix(key, "stays.filter.state.") ||
		strings.HasPrefix(key, "flash.error.")
}

func staysSourceFiles(t *testing.T) []string {
	t.Helper()
	var out []string
	for _, pattern := range []string{"*.go", "templates/*.tmpl"} {
		files, err := filepath.Glob(pattern)
		if err != nil {
			t.Fatal(err)
		}
		for _, f := range files {
			if strings.HasSuffix(f, "_test.go") {
				continue
			}
			out = append(out, f)
		}
	}
	return out
}
