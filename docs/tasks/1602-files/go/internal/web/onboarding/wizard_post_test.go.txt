package onboarding

// Tests of POST /apartments/{id}/setup the golden cannot hold (brief 1602):
// the try-it skip that would delete a demo stay answers 501 and writes
// nothing, and the timing normaliser's edge values.

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestWizardSkipWithDemoStayIs501(t *testing.T) {
	g := wizardLoadGolden(t, "testdata/wizard_golden_post.json")
	pool := testPool(t)
	wizardGoldenSeed(t, pool, g)
	mux := http.NewServeMux()
	RegisterWizard(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, pool, wizardGoldenEnv(g),
		func() time.Time { return wizardGoldenNow })
	user := int64(1)
	c := wizardGoldenCase{Name: "skip", Method: http.MethodPost, Path: "/apartments/20/setup", User: &user, CSRF: true,
		Form: map[string]string{"step": "try_it", "action": "skip"}}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, wizardGoldenRequest(t, g, c))
	if rec.Code != http.StatusNotImplemented || !strings.Contains(rec.Body.String(), "1603") {
		t.Fatalf("status %d: %s", rec.Code, rec.Body.String())
	}
	var stays, audits int
	ctx := context.Background()
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM reservation WHERE apartment_id = 20 AND source = 'demo'`).Scan(&stays); err != nil || stays != 1 {
		t.Fatalf("demo stays %d (%v)", stays, err)
	}
	if err := pool.QueryRow(ctx, `SELECT COUNT(*) FROM audit`).Scan(&audits); err != nil || audits != 0 {
		t.Fatalf("audit lines %d (%v)", audits, err)
	}
}

func TestWizardAutomationTiming(t *testing.T) {
	form := func(mode, hours string) *http.Request {
		v := url.Values{"automation_mode": {mode}, "submit_after_hours": {hours}}
		r := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(v.Encode()))
		r.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		return r
	}
	for _, c := range []struct {
		mode, hours, err, wantMode string
		wantHours                  int64
	}{
		{"scheduled", "6", "", "scheduled", 6},
		{"scheduled", " 48 ", "", "scheduled", 48},
		{"scheduled", "49", "flash.properties.timing_hours", "", 0},
		{"scheduled", "0", "flash.properties.timing_hours", "", 0},
		{"scheduled", "x", "flash.properties.timing_hours", "", 0},
		{"scheduled", "1_2", "", "scheduled", 12},
		{"manual", "", "", "manual", 24},
		{"manual", "-5", "", "manual", -5},
		{"immediate", "100", "", "immediate", 48},
		{"immediate", "0", "", "immediate", 24},
		{"", "5", "flash.properties.timing_invalid", "", 0},
		{"Manual", "5", "flash.properties.timing_invalid", "", 0},
	} {
		if got := wizardAutomationChoiceError(form(c.mode, c.hours)); got != c.err {
			t.Errorf("%q %q: error %q, want %q", c.mode, c.hours, got, c.err)
			continue
		}
		if c.err != "" {
			continue
		}
		if mode, hours := wizardAutomationTiming(form(c.mode, c.hours)); mode != c.wantMode || hours != c.wantHours {
			t.Errorf("%q %q: %q %d, want %q %d", c.mode, c.hours, mode, hours, c.wantMode, c.wantHours)
		}
	}
}
