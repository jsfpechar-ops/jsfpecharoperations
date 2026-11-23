package guest

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func TestLeonEntryCodePointerInCatalog(t *testing.T) {
	raw, err := os.ReadFile("../ai/leon_guest_entry_code_i18n.json")
	if err != nil {
		t.Fatal(err)
	}
	var cat map[string]map[string]string
	if err := json.Unmarshal(raw, &cat); err != nil {
		t.Fatal(err)
	}
	for _, lang := range []string{"en", "cs", "de", "es", "fr", "uk"} {
		msg, ok := cat[lang]["leon_entry_code_pointer"]
		if !ok || msg == "" {
			t.Fatalf("%s: missing leon_entry_code_pointer", lang)
		}
	}
	if !strings.Contains(cat["en"]["leon_entry_code_pointer"], "entry codes") {
		t.Fatal("en text")
	}
}

func TestLeonGoneWithoutLiveGuide(t *testing.T) {
	if os.Getenv("UBYHOST_TEST_DATABASE_URL") == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	// Minimal handler: unknown token -> 404 JSON
	s := &lqServer{pool: nil}
	rec := httptest.NewRecorder()
	s.leonGone(rec)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "not_found") {
		t.Fatalf("body %q", rec.Body.String())
	}
}
