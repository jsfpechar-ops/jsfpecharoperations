package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestPrivacyRoutesRegistered checks that the three privacy request routes
// of routes/privacy_requests.py reach their own patterns (brief 1615).
func TestPrivacyRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/privacy-requests", "GET /privacy-requests"},
		{http.MethodPost, "/privacy-requests", "POST /privacy-requests"},
		{http.MethodPost, "/privacy-requests/12", "POST /privacy-requests/{id}"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
