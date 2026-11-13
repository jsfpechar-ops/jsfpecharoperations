package booking

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func testMux(t *testing.T, g golden, now time.Time, dataDir string) *http.ServeMux {
	t.Helper()
	pool := testPool(t)
	seed(t, pool, g)
	env := map[string]string{"UBYHOST_SECRET_KEY": g.Secret, "UBYHOST_DATA_DIR": dataDir}
	getenv := func(k string) string { return env[k] }
	clock := func() time.Time { return now }
	mux := http.NewServeMux()
	mux.Handle("GET /p/{slug}/{file}", ICalFeedHandler(pool, getenv, clock))
	mux.Handle("GET /p/{slug}/b/{booking_id}/{token}/calendar.ics", StayCalendarHandler(pool, getenv, clock))
	mux.Handle("GET /photos/property/{name}", PhotoHandler(getenv))
	return mux
}

func get(mux *http.ServeMux, path string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, path, nil)
	req.RemoteAddr = "203.0.113.7:4321"
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

func TestFactoriesDoNotTouchThePool(t *testing.T) {
	getenv := func(string) string { return "" }
	if ICalFeedHandler(nil, getenv, time.Now) == nil || StayCalendarHandler(nil, getenv, time.Now) == nil ||
		PhotoHandler(getenv) == nil {
		t.Fatal("nil handler")
	}
	// A non-.ics file answers 404 before any database call (pool is nil here).
	mux := http.NewServeMux()
	mux.Handle("GET /p/{slug}/{file}", ICalFeedHandler(nil, getenv, time.Now))
	for _, path := range []string{"/p/old-town/thanks", "/p/old-town/.ics", "/p/old-town/x.ICS"} {
		if rec := get(mux, path); rec.Code != http.StatusNotFound {
			t.Errorf("%s: %d, want 404", path, rec.Code)
		}
	}
}

func TestICalFeedRoute(t *testing.T) {
	g := loadGolden(t)
	now := mustTime(t, g.Now)
	mux := testMux(t, g, now, t.TempDir())
	rec := get(mux, "/p/old-town/tok-apt-1.ics")
	if rec.Code != http.StatusOK {
		t.Fatalf("feed: %d %s", rec.Code, rec.Body.String())
	}
	h := rec.Header()
	if h.Get("Content-Type") != "text/calendar; charset=utf-8" || h.Get("Cache-Control") != "private, max-age=300" ||
		h.Get("X-Robots-Tag") != "noindex" {
		t.Errorf("feed headers %v", h)
	}
	// The body itself is compared with Python in TestDatabaseCasesMatchPython.
	if !strings.Contains(rec.Body.String(), "UID:ubyhost-101@ubyhost.cz") || !strings.HasSuffix(rec.Body.String(), "END:VCALENDAR\r\n") {
		t.Errorf("feed body %q", rec.Body.String())
	}
	// A history slug still serves the feed.
	if rec := get(mux, "/p/old-town-2025/tok-apt-1.ics"); rec.Code != http.StatusOK {
		t.Errorf("history slug feed: %d", rec.Code)
	}
	for _, path := range []string{"/p/old-town/wrong.ics", "/p/nope/tok-apt-1.ics", "/p/garden/guess.ics"} {
		if rec := get(mux, path); rec.Code != http.StatusNotFound {
			t.Errorf("%s: %d, want 404", path, rec.Code)
		}
	}
	// 5 requests so far from this address; the 120th in the window is the last allowed.
	for i := 0; i < rateMax-5; i++ {
		get(mux, "/p/old-town/wrong.ics")
	}
	if rec := get(mux, "/p/old-town/tok-apt-1.ics"); rec.Code != http.StatusTooManyRequests || rec.Body.String() != "slow down" {
		t.Errorf("rate limit: %d %q", rec.Code, rec.Body.String())
	}
}

func TestStayCalendarRoute(t *testing.T) {
	g := loadGolden(t)
	now := mustTime(t, g.Now)
	mux := testMux(t, g, now, t.TempDir())
	good := ManageToken(g.Secret, 501)
	rec := get(mux, "/p/old-town/b/501/"+good+"/calendar.ics")
	if rec.Code != http.StatusOK {
		t.Fatalf("stay calendar: %d %s", rec.Code, rec.Body.String())
	}
	h := rec.Header()
	if h.Get("Content-Type") != "text/calendar; charset=utf-8" || h.Get("Cache-Control") != "no-store" ||
		h.Get("X-Robots-Tag") != "noindex" || h.Get("Content-Disposition") != `attachment; filename="stay.ics"` {
		t.Errorf("stay headers %v", h)
	}
	if rec.Body.String() != g.StayICS[0].Body {
		t.Errorf("stay body\n got: %q\nwant: %q", rec.Body.String(), g.StayICS[0].Body)
	}
	for _, path := range []string{
		"/p/old-town/b/501/" + good + "x/calendar.ics",
		"/p/old-town/b/502/" + ManageToken(g.Secret, 502) + "/calendar.ics", // cancelled
		"/p/old-town/b/503/" + ManageToken(g.Secret, 503) + "/calendar.ics", // pending
		"/p/old-town/b/777/" + ManageToken(g.Secret, 777) + "/calendar.ics", // no such booking
		"/p/old-town/b/abc/" + good + "/calendar.ics",
	} {
		if rec := get(mux, path); rec.Code != http.StatusNotFound {
			t.Errorf("%s: %d, want 404", path, rec.Code)
		}
	}
}

func TestPhotoRoute(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "property_photos"), 0o755); err != nil {
		t.Fatal(err)
	}
	name := strings.Repeat("ab", 16) + ".jpg"
	if err := os.WriteFile(filepath.Join(dir, "property_photos", name), []byte("\xff\xd8jpeg"), 0o644); err != nil {
		t.Fatal(err)
	}
	getenv := func(k string) string {
		if k == "UBYHOST_DATA_DIR" {
			return dir
		}
		return ""
	}
	mux := http.NewServeMux()
	mux.Handle("GET /photos/property/{name}", PhotoHandler(getenv))
	rec := get(mux, "/photos/property/"+name)
	if rec.Code != http.StatusOK || rec.Body.String() != "\xff\xd8jpeg" ||
		rec.Header().Get("Content-Type") != "image/jpeg" || rec.Header().Get("Cache-Control") != "public, max-age=86400" {
		t.Errorf("photo: %d %v", rec.Code, rec.Header())
	}
	for _, bad := range []string{strings.Repeat("cd", 16) + ".jpg", strings.Repeat("AB", 16) + ".jpg", "x.jpg",
		strings.Repeat("ab", 16) + ".png"} {
		if rec := get(mux, "/photos/property/"+bad); rec.Code != http.StatusNotFound {
			t.Errorf("%s: %d, want 404", bad, rec.Code)
		}
	}
}
