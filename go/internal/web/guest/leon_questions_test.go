package guest

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
)

type leonQuestionsGolden struct {
	Now   string `json:"now"`
	Seed  []any  `json:"seed"`
	Cases []struct {
		Name     string `json:"name"`
		Method   string `json:"method"`
		Path     string `json:"path"`
		Body     string `json:"body"`
		User     int64  `json:"user"`
		Status   int    `json:"status"`
		Location string `json:"location"`
		FlashKey string `json:"flash_key"`
	} `json:"cases"`
}

func loadLeonQuestionsGolden(t *testing.T) leonQuestionsGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/leon_questions_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g leonQuestionsGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestLeonQuestionsGoldenShape(t *testing.T) {
	g := loadLeonQuestionsGolden(t)
	if len(g.Cases) == 0 {
		t.Fatal("no cases")
	}
	for _, c := range g.Cases {
		if c.Status == 0 {
			t.Errorf("%s: status", c.Name)
		}
		if c.Status == http.StatusSeeOther && !strings.HasPrefix(c.Location, "/") {
			t.Errorf("%s: location %q", c.Name, c.Location)
		}
	}
}

func TestLeonQuestionsSignedOutGolden(t *testing.T) {
	g := loadLeonQuestionsGolden(t)
	var found bool
	for _, c := range g.Cases {
		if c.Name == "signed_out_questions" {
			found = true
			if c.Status != http.StatusSeeOther || c.Location != "/login" {
				t.Fatalf("signed out: %+v", c)
			}
		}
	}
	if !found {
		t.Fatal("missing signed_out_questions case")
	}
}
