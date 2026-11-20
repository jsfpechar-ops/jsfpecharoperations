package guest

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
)

func TestDraftKeyHash(t *testing.T) {
	got := keyHash("test-device-key")
	if len(got) != 64 {
		t.Fatalf("hash len %d", len(got))
	}
}

func TestDraftCleanTyped(t *testing.T) {
	if draftHasTyped(cleanDraftFields(map[string]string{"party_size": "2"})) {
		t.Fatal("party_size alone not typed")
	}
	c := cleanDraftFields(map[string]string{"surname": "  Novak "})
	if c["surname"] != "Novak" {
		t.Fatalf("%q", c["surname"])
	}
}

func TestDraftIsSentGuestUnit(t *testing.T) {
	guests := []map[string]string{{"doc_number": "P1", "first_name": "A", "surname": "B", "birth_date": "01011990"}}
	if !draftIsSentGuest(map[string]string{"doc_number": "p1"}, guests) {
		t.Fatal("doc match")
	}
}

type draftScanGolden struct {
	Now   string `json:"now"`
	Seed  []any  `json:"seed"`
	Cases []struct {
		Name       string `json:"name"`
		Method     string `json:"method"`
		Path       string `json:"path"`
		Body       string `json:"body"`
		User       int64  `json:"user"`
		Status     int    `json:"status"`
		Location   string `json:"location"`
		FlashKey   string `json:"flash_key"`
		JSONKind   string `json:"json_kind,omitempty"`
		JSONStatus int    `json:"json_status,omitempty"`
	} `json:"cases"`
}

func loadDraftScanGolden(t *testing.T) draftScanGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/draft_scan_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g draftScanGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestDraftScanGoldenHTTP(t *testing.T) {
	g := loadDraftScanGolden(t)
	if len(g.Cases) == 0 {
		t.Fatal("no cases")
	}
	for _, c := range g.Cases {
		switch c.Method {
		case http.MethodPost:
			if c.JSONKind != "" {
				if c.Status != 0 && c.JSONStatus != c.Status {
					t.Errorf("%s: json status", c.Name)
				}
				continue
			}
			if c.Status != http.StatusNoContent && c.Status != http.StatusNotFound &&
				c.Status != http.StatusTooManyRequests && c.Status != http.StatusRequestEntityTooLarge {
				t.Errorf("%s: status %d", c.Name, c.Status)
			}
		default:
			t.Errorf("%s: method %s", c.Name, c.Method)
		}
		if c.Location != "" && !strings.HasPrefix(c.Location, "/") {
			t.Errorf("%s: location %q", c.Name, c.Location)
		}
	}
}
