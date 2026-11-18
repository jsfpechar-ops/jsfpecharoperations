package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestHousebookPageRouteRegistered checks that GET /housebook reaches its own
// pattern and the existing export routes keep theirs (brief 1704a).
func TestHousebookPageRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/housebook", "GET /housebook"},
		{http.MethodGet, "/housebook.csv", "GET /housebook.csv"},
		{http.MethodGet, "/housebook/pdfs.zip", "GET /housebook/pdfs.zip"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
