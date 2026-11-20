package booking

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
)

type bslGolden struct {
	Cases []struct {
		Name     string `json:"name"`
		Method   string `json:"method"`
		Path     string `json:"path"`
		User     int64  `json:"user"`
		Status   int    `json:"status"`
		Location string `json:"location"`
	} `json:"cases"`
}

func loadBSLGolden(t *testing.T) bslGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/booking_sites_list_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g bslGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestBookingSitesListGoldenShape(t *testing.T) {
	g := loadBSLGolden(t)
	if len(g.Cases) < 2 {
		t.Fatalf("cases %d", len(g.Cases))
	}
	for _, c := range g.Cases {
		if c.Method != http.MethodGet {
			t.Errorf("%s: method %s", c.Name, c.Method)
		}
		if c.Status != http.StatusOK && c.Status != http.StatusSeeOther {
			t.Errorf("%s: status %d", c.Name, c.Status)
		}
		if c.Location != "" && !strings.HasPrefix(c.Location, "/") {
			t.Errorf("%s: location %q", c.Name, c.Location)
		}
	}
}

func TestListApartmentsSQLAnchor(t *testing.T) {
	if !strings.Contains(listApartmentsSQL, "property_page") || !strings.Contains(listApartmentsSQL, "active = 1") {
		t.Fatal(listApartmentsSQL)
	}
}
