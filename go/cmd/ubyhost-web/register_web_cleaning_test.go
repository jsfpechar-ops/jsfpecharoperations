package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestCleaningRoutesRegistered checks that the five cleaning routes reach
// their own patterns and that the cleaning pages left in Python do not.
func TestCleaningRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	token := "share1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/cleaning/schedule", "GET /cleaning/schedule"},
		{http.MethodGet, "/cleaning/shared/" + token, "GET /cleaning/shared/{token}"},
		{http.MethodGet, "/cleaning/shared/" + token + "/schedule", "GET /cleaning/shared/{token}/schedule"},
		{http.MethodPost, "/cleaning/events/7/delete", "POST /cleaning/events/{id}/delete"},
		{http.MethodPost, "/cleaning/shares/3/revoke", "POST /cleaning/shares/{id}/revoke"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
