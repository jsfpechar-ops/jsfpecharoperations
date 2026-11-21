package public

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestSampleAirbnbHandler(t *testing.T) {
	mux := http.NewServeMux()
	fixed := time.Date(2026, 11, 14, 12, 0, 0, 0, time.UTC)
	RegisterUtility(mux, DepsUtility{Now: func() time.Time { return fixed }}, func(_ string, h http.HandlerFunc) http.Handler { return h })

	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/sample-airbnb.ics", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	ct := rec.Header().Get("Content-Type")
	if !strings.HasPrefix(ct, "text/calendar") {
		t.Fatalf("content-type %q", ct)
	}
	if !strings.Contains(rec.Body.String(), "BEGIN:VCALENDAR") {
		t.Fatal("missing calendar body")
	}
}
