package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestCatchAllIsNotPorted pins K-O07: an unmatched path must be 501 with
// X-Ubyhost-Not-Ported so Caddy can fall back to Python on GET/HEAD. A bare
// 404 is wrong (that was the stay-page outage when GO_PATHS listed a path Go
// did not handle).
func TestCatchAllIsNotPorted(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	req := httptest.NewRequest(http.MethodGet, "/no-such-go-route", nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusNotImplemented {
		t.Errorf("code %d, want 501", rec.Code)
	}
	if got := rec.Header().Get("X-Ubyhost-Not-Ported"); got != "1" {
		t.Errorf("X-Ubyhost-Not-Ported %q, want 1", got)
	}
}

// TestStayDetailStillRegistered: numeric stay URLs must hit the staydetail
// pattern, not the catch-all (so a current image never 501s a real stay).
func TestStayDetailStillRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	req := httptest.NewRequest(http.MethodGet, "/reservations/252", nil)
	_, pat := mux.Handler(req)
	if pat != "GET /reservations/{reservation_id}" {
		t.Fatalf("pattern %q, want GET /reservations/{reservation_id}", pat)
	}
}
