package exports

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

func TestNoExportReadsEntryCode(t *testing.T) {
	entries, err := os.ReadDir(".")
	if err != nil {
		t.Fatal(err)
	}
	selectStarApartment := regexp.MustCompile(`(?i)SELECT\s+(a\.)?\*\s+FROM\s+apartment`)
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".go") || strings.HasSuffix(e.Name(), "_test.go") {
			continue
		}
		body, err := os.ReadFile(filepath.Join(".", e.Name()))
		if err != nil {
			t.Fatal(err)
		}
		text := string(body)
		if strings.Contains(text, "entry_code") {
			t.Fatalf("%s must not reference entry_code", e.Name())
		}
		if selectStarApartment.MatchString(text) {
			t.Fatalf("%s must not SELECT * FROM apartment", e.Name())
		}
	}
}

func TestNoExportReadsEntryCodeTable(t *testing.T) {
	entries, err := os.ReadDir(".")
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".go") || strings.HasSuffix(e.Name(), "_test.go") {
			continue
		}
		body, err := os.ReadFile(filepath.Join(".", e.Name()))
		if err != nil {
			t.Fatal(err)
		}
		if strings.Contains(string(body), "apartment_entry_code") {
			t.Fatalf("%s must not reference apartment_entry_code", e.Name())
		}
	}
}
