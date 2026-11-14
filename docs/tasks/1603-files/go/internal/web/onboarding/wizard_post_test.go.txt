package onboarding

// Tests of POST /apartments/{id}/setup the golden cannot hold (briefs 1602 and
// 1603): the try-it skip that deletes a demo stay, and the timing normaliser's
// edge values.

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// wizardSkipPost posts the try-it skip for apartment apt as user 1 with a data
// directory, and returns the response.
func wizardSkipPost(t *testing.T, g wizardGoldenFile, pool *pgxpool.Pool, dataDir string, apt int) *httptest.ResponseRecorder {
	t.Helper()
	env := wizardGoldenEnv(g)
	getenv := func(k string) string {
		if k == "UBYHOST_DATA_DIR" {
			return dataDir
		}
		return env(k)
	}
	mux := http.NewServeMux()
	RegisterWizard(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, pool, getenv,
		func() time.Time { return wizardGoldenNow })
	user := int64(1)
	c := wizardGoldenCase{Name: "skip", Method: http.MethodPost, Path: fmt.Sprintf("/apartments/%d/setup", apt), User: &user, CSRF: true,
		Form: map[string]string{"step": "try_it", "action": "skip"}}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, wizardGoldenRequest(t, g, c))
	return rec
}

func wizardCount(t *testing.T, pool *pgxpool.Pool, sql string) int {
	t.Helper()
	var n int
	if err := pool.QueryRow(context.Background(), sql).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

// TestWizardSkipDeletesDemoStay: Python's delete_demo_stay. Apartment 22 has a
// demo stay (106) with one guest (501) that has a photo file; apartment 20 has a
// demo stay (105) without guests. Only the asked-for stay goes, with its alert,
// guest and photo files; real stays and the other demo stay stay.
func TestWizardSkipDeletesDemoStay(t *testing.T) {
	g := wizardLoadGolden(t, "testdata/wizard_golden_post.json")
	pool := testPool(t)
	wizardGoldenSeed(t, pool, g)
	ctx := context.Background()
	if _, err := pool.Exec(ctx, `INSERT INTO alert (level, kind, reservation_id, apartment_id, message, created_at) VALUES ('info', 'x', 106, 22, 'x', '2026-01-01T00:00:00+00:00')`); err != nil {
		t.Fatal(err)
	}
	dataDir := t.TempDir()
	photos := filepath.Join(dataDir, "passport_photos")
	if err := os.MkdirAll(photos, 0o755); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"501.jpg.enc", "501.png", "502.jpg.enc"} { // 502 is another guest
		if err := os.WriteFile(filepath.Join(photos, name), []byte("x"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	rec := wizardSkipPost(t, g, pool, dataDir, 22)
	loc := rec.Header().Get("Location")
	if rec.Code != http.StatusSeeOther || !strings.HasPrefix(loc, WizardURL(22, "done")+"?msg=") {
		t.Fatalf("status %d, location %q", rec.Code, loc)
	}
	if n := wizardCount(t, pool, `SELECT COUNT(*) FROM reservation WHERE id = 106`); n != 0 {
		t.Error("the demo stay is still there")
	}
	if n := wizardCount(t, pool, `SELECT COUNT(*) FROM guest WHERE reservation_id = 106`); n != 0 {
		t.Error("the demo guest is still there")
	}
	if n := wizardCount(t, pool, `SELECT COUNT(*) FROM alert WHERE reservation_id = 106`); n != 0 {
		t.Error("the alert is still there")
	}
	left, _ := os.ReadDir(photos)
	if len(left) != 1 || left[0].Name() != "502.jpg.enc" {
		t.Errorf("photo files left: %v", left)
	}
	if n := wizardCount(t, pool, `SELECT COUNT(*) FROM reservation WHERE id IN (105, 101, 107)`); n != 3 {
		t.Errorf("another stay went too: %d of 3 left", n)
	}
	if n := wizardCount(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'property_setup_step' AND detail = 'apartment=22 step=try_it action=skip'`); n != 1 {
		t.Errorf("audit lines: %d", n)
	}
	// the same button again: nothing to delete, back to the finish page without a message
	rec = wizardSkipPost(t, g, pool, dataDir, 22)
	if loc := rec.Header().Get("Location"); rec.Code != http.StatusSeeOther || loc != WizardURL(22, "done") {
		t.Errorf("second skip: %d %q", rec.Code, loc)
	}
}

// TestWizardSkipNeverDeletesARealStay: a stay of the property whose source is
// not demo is not the property's demo stay; the guard of is_demo_stay holds
// even for a stay id that the property does own.
func TestWizardSkipNeverDeletesARealStay(t *testing.T) {
	g := wizardLoadGolden(t, "testdata/wizard_golden_post.json")
	pool := testPool(t)
	wizardGoldenSeed(t, pool, g)
	s := &wizardServer{pool: pool, getenv: wizardGoldenEnv(g), now: func() time.Time { return wizardGoldenNow }}
	for _, c := range []struct{ apt, stay int64 }{{19, 103}, {20, 106}} { // a host stay; a demo stay of another property
		ok, err := s.wizardDeleteDemoStay(context.Background(), c.apt, c.stay)
		if ok || err != nil {
			t.Errorf("stay %d on apartment %d: %v %v", c.stay, c.apt, ok, err)
		}
	}
	if n := wizardCount(t, pool, `SELECT COUNT(*) FROM reservation`); n != 7 {
		t.Errorf("%d stays left, want 7", n)
	}
}

// TestWizardSkipStopsWhenAPhotoStays: the data directory is missing or the
// photo cannot be removed (a read-only volume): 500, no row is deleted, and
// no audit line is written.
func TestWizardSkipStopsWhenAPhotoStays(t *testing.T) {
	g := wizardLoadGolden(t, "testdata/wizard_golden_post.json")
	pool := testPool(t)
	wizardGoldenSeed(t, pool, g)
	if rec := wizardSkipPost(t, g, pool, "", 22); rec.Code != http.StatusInternalServerError {
		t.Errorf("no data directory: %d", rec.Code)
	}
	dataDir := t.TempDir()
	photos := filepath.Join(dataDir, "passport_photos")
	if err := os.MkdirAll(filepath.Join(photos, "501.jpg.enc"), 0o755); err != nil { // a directory is left alone
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(photos, "501.png"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(photos, 0o555); err != nil { // like a read-only mount
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Chmod(photos, 0o755) })
	if os.Geteuid() != 0 { // root ignores the mode
		if rec := wizardSkipPost(t, g, pool, dataDir, 22); rec.Code != http.StatusInternalServerError {
			t.Errorf("read-only photos: %d", rec.Code)
		}
	}
	if n := wizardCount(t, pool, `SELECT COUNT(*) FROM guest WHERE id = 501`); n != 1 {
		t.Error("the guest went although a file stayed")
	}
	if n := wizardCount(t, pool, `SELECT COUNT(*) FROM audit`); n != 0 {
		t.Errorf("audit lines: %d", n)
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
