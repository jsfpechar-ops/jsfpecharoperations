package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestOnboardingDemoRouteRegistered checks that POST /demo/reset reaches its
// own pattern and POST /demo (not in Go yet) still falls to the catch-all
// (brief 1596).
func TestOnboardingDemoRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodPost, "/demo/reset", "POST /demo/reset"},
		{http.MethodPost, "/demo", "/"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
