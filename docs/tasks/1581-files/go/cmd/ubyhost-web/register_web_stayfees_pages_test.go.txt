package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestStayFeesListPageRegistered checks that the stay fee list reaches its own
// pattern next to the routes of brief 1330 (the detail page follows in brief 1582).
func TestStayFeesListPageRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/stay-fees", "GET /stay-fees"},
		{http.MethodGet, "/stay-fees/7/csv", "GET /stay-fees/{apartment_id}/csv"},
		{http.MethodPost, "/stay-fees/7/paid", "POST /stay-fees/{apartment_id}/paid"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
