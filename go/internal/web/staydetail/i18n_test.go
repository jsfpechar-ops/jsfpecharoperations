package staydetail

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

var staydetailKeyRE = regexp.MustCompile(`"((?:stay|guest|common|confirm|status|hint|host|nav|reports|invoice|guide|workflows?|archive)\.[a-z0-9_.]+)"`)

func TestEveryKeyTheCodeReadsIsInTheCatalog(t *testing.T) {
	for _, lang := range []string{"en", "cs"} {
		for _, file := range staydetailSourceFiles(t) {
			raw, err := os.ReadFile(file)
			if err != nil {
				t.Fatal(err)
			}
			for _, m := range staydetailKeyRE.FindAllStringSubmatch(string(raw), -1) {
				key := m[1]
				if strings.HasSuffix(key, ".") {
					continue
				}
				if staydetailDynamicKey(key) {
					continue
				}
				if _, ok := catalog[lang][key]; !ok {
					t.Errorf("%s: %q is not in the %s catalog; add to i18n_keys.txt and regenerate", filepath.Base(file), key, lang)
				}
			}
		}
	}
	if catalog.T("cs", "stays.title", nil) == "stays.title" {
		t.Error("Czech staydetail catalog is empty")
	}
}

func staydetailDynamicKey(key string) bool {
	return strings.HasPrefix(key, "stays.filter.state.") ||
		strings.HasPrefix(key, "guest.doc_type.") ||
		strings.HasPrefix(key, "stay.detail.settings.state.") ||
		strings.HasPrefix(key, "flash.error.") ||
		strings.HasPrefix(key, "send_controls.send_hint_key")
}

func staydetailSourceFiles(t *testing.T) []string {
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
