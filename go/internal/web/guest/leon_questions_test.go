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

func TestLeonGoneWithoutLiveGuide(t *testing.T) {
	t.Skip("JSON gate parity is exercised when UBYHOST_TEST_DATABASE_URL is set in executor step 5")
}

func TestLeonQuestionsTemplateChrome(t *testing.T) {
	raw, err := leonQuestionsFS.ReadFile("templates/leon_questions.tmpl")
	if err != nil {
		t.Fatal(err)
	}
	s := string(raw)
	if strings.Count(s, `class="airbnb-title"`) != 2 {
		t.Fatalf("airbnb-title count %d", strings.Count(s, `class="airbnb-title"`))
	}
	for _, bad := range []string{"ui-page", "guide-back", `class="big"`, `<h1 class="big"`} {
		if strings.Contains(s, bad) {
			t.Fatalf("legacy chrome %q", bad)
		}
	}
	if !strings.Contains(s, "settings-lane") {
		t.Fatal("missing settings-lane")
	}
}
