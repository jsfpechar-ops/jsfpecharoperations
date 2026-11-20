package stays

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"
)

func TestSubmitPluralKey(t *testing.T) {
	if got := submitPluralKey("flash.error.rejected", 1, "en"); got != "flash.error.rejected.one" {
		t.Fatalf("one = %q", got)
	}
	if got := submitPluralKey("flash.error.rejected", 3, "en"); got != "flash.error.rejected.few" {
		t.Fatalf("few = %q", got)
	}
}

type submitGolden struct {
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

func loadSubmitGolden(t *testing.T) submitGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/submit_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g submitGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestSubmitGoldenHTTP(t *testing.T) {
	g := loadSubmitGolden(t)
	if len(g.Cases) == 0 {
		t.Fatal("no cases")
	}
	if g.Now != "" {
		if _, err := time.Parse(time.RFC3339, g.Now); err != nil {
			t.Fatalf("now: %v", err)
		}
	}
	for _, c := range g.Cases {
		if c.Status != http.StatusSeeOther {
			t.Errorf("%s: want %d, got %d", c.Name, http.StatusSeeOther, c.Status)
		}
		if !strings.HasPrefix(c.Location, "/") {
			t.Errorf("%s: location %q", c.Name, c.Location)
		}
		if c.FlashKey != "" && !strings.HasPrefix(c.FlashKey, "flash.") {
			t.Errorf("%s: flash_key %q", c.Name, c.FlashKey)
		}
	}
}
