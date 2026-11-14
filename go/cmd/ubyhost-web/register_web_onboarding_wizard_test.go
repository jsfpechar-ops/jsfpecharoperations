package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestWizardRoutesRegistered checks that the setup wizard routes of briefs
// 1599 to 1602 reach their own patterns.
func TestWizardRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/apartments/7/setup", "GET /apartments/{id}/setup"},
		{http.MethodGet, "/apartments/7/setup/calendar", "GET /apartments/{id}/setup/{step}"},
		{http.MethodGet, "/apartments/7/setup/done", "GET /apartments/{id}/setup/{step}"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
