package billing

import (
	"encoding/json"
	"os"
	"testing"
)

type fixtureQuote struct {
	Apartments      int    `json:"apartments"`
	Plan            string `json:"plan"`
	Interval        string `json:"interval"`
	TTLock          bool   `json:"ttlock"`
	Whitelabel      bool   `json:"whitelabel"`
	Founder         bool   `json:"founder"`
	DiscountPercent int    `json:"discount_percent"`
	Expected        Price  `json:"expected"`
}

type fixtureMonthly struct {
	Total    int    `json:"total"`
	Interval string `json:"interval"`
	Expected int    `json:"expected"`
}

type fixtureFile struct {
	Quote   []fixtureQuote   `json:"quote"`
	Monthly []fixtureMonthly `json:"monthly"`
}

func loadFixtures(t *testing.T) fixtureFile {
	t.Helper()
	raw, err := os.ReadFile("testdata/quote_fixtures.json")
	if err != nil {
		t.Fatal(err)
	}
	var f fixtureFile
	if err := json.Unmarshal(raw, &f); err != nil {
		t.Fatal(err)
	}
	return f
}

func TestQuoteMatchesPythonFixtures(t *testing.T) {
	f := loadFixtures(t)
	if len(f.Quote) != 1120 {
		t.Fatalf("expected 1120 quote cases, got %d", len(f.Quote))
	}
	for _, c := range f.Quote {
		got, err := Quote(c.Apartments, c.Plan, c.Interval, c.TTLock, c.Whitelabel, c.Founder, c.DiscountPercent)
		if err != nil {
			t.Fatalf("%+v: %v", c, err)
		}
		if got != c.Expected {
			t.Errorf("%+v: got %+v want %+v", c, got, c.Expected)
		}
	}
}

func TestMonthlyMatchesPythonFixtures(t *testing.T) {
	for _, c := range loadFixtures(t).Monthly {
		if got := Monthly(c.Total, c.Interval); got != c.Expected {
			t.Errorf("%+v: got %d", c, got)
		}
	}
}

func TestQuoteRejectsBadInput(t *testing.T) {
	if _, err := Quote(1, "pro", "month", false, false, false, 0); err == nil {
		t.Error("unknown plan accepted")
	}
	if _, err := Quote(1, "max", "week", false, false, false, 0); err == nil {
		t.Error("unknown interval accepted")
	}
	if _, err := Quote(1, "max", "month", false, false, false, 101); err == nil {
		t.Error("discount above 100 accepted")
	}
}
