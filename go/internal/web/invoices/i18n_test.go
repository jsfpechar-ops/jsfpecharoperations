package invoices

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

var keyRE = regexp.MustCompile(`"((?:invoice|invoices|ares|flash|host|filter|common|nav|stays|month|how|confirm|payments)\.[a-z0-9_.]+)"`)

func TestEveryKeyTheCodeReadsIsInTheCatalog(t *testing.T) {
	for _, lang := range []string{"en", "cs"} {
		for _, file := range sourceFiles(t) {
			raw, err := os.ReadFile(file)
			if err != nil {
				t.Fatal(err)
			}
			for _, m := range keyRE.FindAllStringSubmatch(string(raw), -1) {
				key := m[1]
				if strings.HasSuffix(key, ".") || strings.HasSuffix(key, "_") {
					continue // a prefix: "invoice.kind." + kind
				}
				if _, ok := catalog[lang][key]; !ok && !dynamicKey(key) {
					t.Errorf("%s: %q is not in the %s catalog; add it to i18n_keys.txt and regenerate", filepath.Base(file), key, lang)
				}
			}
		}
	}
	if catalog.T("cs", "invoice.new", nil) == "invoice.new" {
		t.Error("the Czech catalog is empty")
	}
}

func dynamicKey(key string) bool {
	return key == "invoices.filter" || key == "invoices.filter.summary" || key == "invoices.pill"
}

func sourceFiles(t *testing.T) []string {
	t.Helper()
	var out []string
	for _, pattern := range []string{"*.go", "templates/*.tmpl"} {
		files, err := filepath.Glob(pattern)
		if err != nil {
			t.Fatal(err)
		}
		for _, f := range files {
			if !strings.HasSuffix(f, "_test.go") {
				out = append(out, f)
			}
		}
	}
	return out
}
