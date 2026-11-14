package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestOnboardingPageRouteRegistered checks that GET /onboarding reaches its
// own pattern and the 1290 POST routes keep theirs (brief 1595).
func TestOnboardingPageRouteRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/onboarding", "GET /onboarding"},
		{http.MethodPost, "/onboarding/dismiss", "POST /onboarding/dismiss"},
		{http.MethodPost, "/onboarding/resume", "POST /onboarding/resume"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
