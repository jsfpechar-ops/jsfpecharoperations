package booking

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
)

type pphGolden struct {
	Cases []struct {
		Name     string `json:"name"`
		Method   string `json:"method"`
		Status   int    `json:"status"`
		Location string `json:"location"`
		FlashKey string `json:"flash_key"`
	} `json:"cases"`
}

func loadPPHGolden(t *testing.T) pphGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/property_page_host_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g pphGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestPropertyPageHostGoldenShape(t *testing.T) {
	g := loadPPHGolden(t)
	if len(g.Cases) < 3 {
		t.Fatalf("cases %d", len(g.Cases))
	}
	for _, c := range g.Cases {
		if c.Method == http.MethodPost && c.Status != http.StatusSeeOther && c.Status != http.StatusNotFound {
			t.Errorf("%s: status %d", c.Name, c.Status)
		}
		if c.Location != "" && !strings.HasPrefix(c.Location, "/") && c.Status != http.StatusNotFound {
			t.Errorf("%s: location %q", c.Name, c.Location)
		}
	}
}

func TestAmenitiesTextRoundTrip(t *testing.T) {
	raw := `["Wi‑Fi","Kitchen"]`
	got := amenitiesText(&raw)
	if got != "Wi‑Fi\nKitchen" {
		t.Fatalf("got %q", got)
	}
	back := parseAmenities(got)
	if len(back) != 2 || back[0] != "Wi‑Fi" {
		t.Fatalf("%v", back)
	}
}

func TestMoveHostPhotoOrder(t *testing.T) {
	photos := []string{"/photos/property/a.jpg", "/photos/property/b.jpg"}
	raw, _ := json.Marshal(photos)
	s := string(raw)
	row := &reviewPageRow{PhotosJSON: &s}
	i := indexOf(photosFromJSON(row.PhotosJSON), "/photos/property/b.jpg")
	if i != 1 {
		t.Fatal(i)
	}
}
