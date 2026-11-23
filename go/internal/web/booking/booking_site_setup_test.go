package booking

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
)

type bssGolden struct {
	Cases []struct {
		Name     string `json:"name"`
		Method   string `json:"method"`
		Status   int    `json:"status"`
		Location string `json:"location"`
		FlashKey string `json:"flash_key"`
	} `json:"cases"`
}

func loadBSSGolden(t *testing.T) bssGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/booking_site_setup_golden.json")
	if err != nil {
		t.Fatalf("golden: %v", err)
	}
	var g bssGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func TestBookingSiteSetupGoldenShape(t *testing.T) {
	g := loadBSSGolden(t)
	if len(g.Cases) < 2 {
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

func TestParseSetupFormNotice(t *testing.T) {
	form := map[string][]string{
		"nightly_price_czk":   {"2500"},
		"cleaning_fee_czk":    {"500"},
		"min_nights":          {"2"},
		"max_guests":          {"4"},
		"cancellation_policy": {"flexible"},
		"notice":              {"0:18"},
	}
	vals, err := ParseSetupForm(form)
	if err != nil {
		t.Fatal(err)
	}
	if vals["advance_notice_days"] != 0 || vals["same_day_cutoff_hour"] != 18 {
		t.Fatalf("%v", vals)
	}
}

func TestNoticeValueSameDay(t *testing.T) {
	s := Settings{AdvanceNoticeDays: 0, SameDayCutoffHour: 15}
	if got := NoticeValue(s); got != "0:15" {
		t.Fatalf("%q", got)
	}
}

func TestBookingSiteSetupTemplateChrome(t *testing.T) {
	raw, err := os.ReadFile("templates/booking_site_setup.tmpl")
	if err != nil {
		t.Fatal(err)
	}
	s := string(raw)
	for _, bad := range []string{`define "booking_site_setup.head"`, `<p class="sub">{{.Apartment}}</p>`} {
		if strings.Contains(s, bad) {
			t.Fatalf("still has %q", bad)
		}
	}
	for _, want := range []string{`define "booking_site_setup.meta"`, `ui_banner "attention"`} {
		if !strings.Contains(s, want) {
			t.Fatalf("missing %q", want)
		}
	}
}
