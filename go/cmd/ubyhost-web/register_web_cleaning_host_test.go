package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestCleaningHostRoutesRegistered checks that the cleaning host routes of
// briefs 1570 and after reach their own patterns (brief 1570: four GET pages).
func TestCleaningHostRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/cleaning", "GET /cleaning"},
		{http.MethodGet, "/cleaning/new", "GET /cleaning/new"},
		{http.MethodGet, "/cleaning/events/7/edit", "GET /cleaning/events/{id}/edit"},
		{http.MethodGet, "/cleaning/properties", "GET /cleaning/properties"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
