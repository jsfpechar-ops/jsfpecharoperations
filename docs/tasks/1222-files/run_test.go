package billingjob

// Tests of the run's helpers that need no database. Expected values were produced
// by the Python in App/app (billing_trial.period_end, activation_dates,
// billing._whole_months, json.dumps(sort_keys=True)).

import (
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
)

func isoDay(t *testing.T, s string) time.Time {
	t.Helper()
	d, err := time.Parse(isoDate, s)
	if err != nil {
		t.Fatal(err)
	}
	return d
}

func TestPeriodEnd(t *testing.T) {
	for _, c := range []struct{ start, interval, want string }{
		{"2026-01-31", "month", "2026-02-28"}, // 31 January runs to the end of February
		{"2026-01-30", "month", "2026-02-28"},
		{"2026-12-15", "month", "2027-01-14"},
		{"2024-02-29", "year", "2025-02-28"},
		{"2026-11-13", "year", "2027-11-12"},
		{"2026-01-29", "month", "2026-02-28"},
		{"2026-05-31", "month", "2026-06-30"},
		{"2025-12-31", "month", "2026-01-30"},
	} {
		if got := periodEnd(isoDay(t, c.start), c.interval).Format(isoDate); got != c.want {
			t.Errorf("periodEnd(%s, %s) = %s, want %s", c.start, c.interval, got, c.want)
		}
	}
}

func TestActivationDates(t *testing.T) {
	for _, c := range []struct{ stamp, first, last string }{
		{"2026-10-14T23:30:00+00:00", "2026-10-15", "2026-11-14"},
		{"2026-03-28T23:30:00+00:00", "2026-03-29", "2026-04-28"},
		{"2026-03-01T10:00:00", "2026-03-01", "2026-03-31"},
		{"2026-10-20", "2026-10-20", "2026-11-19"},
		{"2026-10-20 10:00:00+02:00", "2026-10-20", "2026-11-19"},
		{"2026-10-20T10:00:00.123456+00:00", "2026-10-20", "2026-11-19"},
		{"2026-10-20T10:00:00Z", "2026-10-20", "2026-11-19"},
	} {
		first, last, err := activationDates(c.stamp)
		if err != nil {
			t.Fatalf("%s: %v", c.stamp, err)
		}
		if first.Format(isoDate) != c.first || last.Format(isoDate) != c.last {
			t.Errorf("activationDates(%s) = %s %s, want %s %s", c.stamp, first.Format(isoDate), last.Format(isoDate), c.first, c.last)
		}
	}
	if _, _, err := activationDates("not a date"); err == nil {
		t.Error("a bad stamp must be an error")
	}
}

func TestPendingDumpAndReads(t *testing.T) {
	p, err := parsePending(`{"x": "č", "plan": "max", "apartments": 3, "addon_ttlock": 1}`)
	if err != nil {
		t.Fatal(err)
	}
	if got, want := p.dump(), "{\"addon_ttlock\": 1, \"apartments\": 3, \"plan\": \"max\", \"x\": \"\\u010d\"}"; got != want {
		t.Errorf("dump = %s, want %s", got, want)
	}
	if !p.equalsInt("apartments", 3) || p.equalsInt("apartments", 2) || p.equalsInt("missing", 0) {
		t.Error("equalsInt")
	}
	fallback := "standard"
	if got, _ := p.text("plan", &fallback); got == nil || *got != "max" {
		t.Error("text must read the pending plan")
	}
	if got, _ := p.text("billing_interval", &fallback); got == nil || *got != "standard" {
		t.Error("text must fall back to the account")
	}
	if got, _ := p.flag("addon_ttlock", false); got != 1 {
		t.Error("flag must read the pending add-on")
	}
	if got, _ := p.flag("addon_whitelabel", true); got != 1 {
		t.Error("flag must fall back to the account")
	}
	empty, _ := parsePending("")
	if empty.dump() != "{}" {
		t.Errorf("empty dump = %s", empty.dump())
	}
	if _, err := parsePending("[1]"); err == nil {
		t.Error("a pending list is an error")
	}
}

func TestWholeMonths(t *testing.T) {
	for _, c := range []struct {
		start, end string
		want       int64
	}{
		{"2026-11-13", "2027-02-28", 3},
		{"2026-11-13", "2027-08-31", 9},
		{"2026-11-30", "2026-12-20", 0},
		{"2026-11-13", "2026-11-12", 0},
	} {
		if got := wholeMonths(isoDay(t, c.start), isoDay(t, c.end)); got != c.want {
			t.Errorf("wholeMonths(%s, %s) = %d, want %d", c.start, c.end, got, c.want)
		}
	}
}

func TestBillingEnabledAndCounts(t *testing.T) {
	for value, want := range map[string]bool{"": false, "0": false, "no": false, "1": true, "TRUE": true, "Yes": true, " 1": false} {
		t.Setenv("UBYHOST_BILLING_ENABLED", value)
		if BillingEnabled() != want {
			t.Errorf("BillingEnabled(%q) = %v", value, !want)
		}
	}
	c := Counts{Rolled: 1, Invoiced: 2, Apartments: 3, Errors: 9, TrialStarted: 1, DunningPaused: 1}
	if c.Total() != 8 || c.Map()["errors"] != 9 || c.Map()["dunning_paused"] != 1 {
		t.Errorf("Counts %+v", c)
	}
	if Today(time.Date(2026, 11, 13, 23, 59, 0, 0, time.FixedZone("x", 7200))) != isoDay(t, "2026-11-13") {
		t.Error("Today must keep the calendar date of the given zone")
	}
}

func TestBillingMails(t *testing.T) {
	trial := mail.BuildBillingTrial("https://app.example.test", "https://www.example.test", "ops@example.test", 3, "16.11.2026")
	if trial.Subject != "Zkušební doba UbyHost končí za 3 dny" || !strings.Contains(trial.Text, "končí 16.11.2026.") ||
		!strings.Contains(trial.Text, "Vybrat plán: https://app.example.test/predplatne") ||
		!strings.Contains(trial.HTML, `<html lang="cs">`) {
		t.Errorf("trial mail: %q", trial.Text)
	}
	paused := mail.BuildBillingOverdue("https://app.example.test", "https://www.example.test", "ops@example.test",
		"paused", "UBY-2026-0001", 12345, "06.11.2026", "13.11.2026")
	if paused.Subject != "Účet UbyHost je jen pro čtení" || !strings.Contains(paused.Text, "faktury UBY-2026-0001 na 12 345 Kč jsme do 13.11.2026") {
		t.Errorf("paused mail: %q %q", paused.Subject, paused.Text)
	}
	monthly := mail.BuildBillingOverdue("https://app.example.test", "https://www.example.test", "ops@example.test",
		"monthly1", "UBY-2026-0002", 149, "06.11.2026", "13.11.2026")
	if monthly.Subject != "Připomínka: faktura UBY-2026-0002" || !strings.Contains(monthly.Text, "byla splatná 06.11.2026") {
		t.Errorf("monthly mail: %q %q", monthly.Subject, monthly.Text)
	}
}
