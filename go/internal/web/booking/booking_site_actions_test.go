package booking

import (
	"encoding/json"
	"os"
	"testing"
)

func TestBookingSiteActionsGoldenShape(t *testing.T) {
	raw, err := os.ReadFile("testdata/booking_site_actions_golden.json")
	if err != nil {
		t.Fatal(err)
	}
	var doc struct {
		Routes []string `json:"routes"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	if len(doc.Routes) != 4 {
		t.Fatalf("routes: %v", doc.Routes)
	}
}
