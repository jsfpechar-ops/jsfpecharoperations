package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestCleaningHostSettingsRoutesRegistered checks the property settings and share routes of brief 1572.
func TestCleaningHostSettingsRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/cleaning/properties/3", "GET /cleaning/properties/{id}"},
		{http.MethodPost, "/cleaning/properties/3", "POST /cleaning/properties/{id}"},
		{http.MethodGet, "/cleaning/shares", "GET /cleaning/shares"},
		{http.MethodPost, "/cleaning/shares", "POST /cleaning/shares"},
		{http.MethodPost, "/cleaning/shares/3/revoke", "POST /cleaning/shares/{id}/revoke"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
