package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/stayfees"
)

// TestStayFeesPagesRegistered checks that the list and the detail page reach
// their own patterns next to the routes of brief 1330, and that the detail
// pattern does not shadow the literal /stay-fees/pdfs.zip or the csv route.
func TestStayFeesPagesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	for _, c := range []struct{ method, path, pattern string }{
		{http.MethodGet, "/stay-fees", "GET /stay-fees"},
		{http.MethodGet, "/stay-fees/7", "GET /stay-fees/{apartment_id}"},
		{http.MethodGet, "/stay-fees/7/csv", "GET /stay-fees/{apartment_id}/csv"},
		{http.MethodPost, "/stay-fees/7/paid", "POST /stay-fees/{apartment_id}/paid"},
	} {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}

	// The mux keeps a more specific literal away from the detail pattern: with
	// a stand-in for GET /stay-fees/pdfs.zip next to the pages, the stand-in wins.
	local := http.NewServeMux()
	for _, r := range stayfees.PageRoutes(nil, func(string) string { return "" }, time.Now) {
		local.Handle(r.Pattern, r.Handler)
	}
	local.HandleFunc("GET /stay-fees/pdfs.zip", func(http.ResponseWriter, *http.Request) {})
	_, pattern := local.Handler(httptest.NewRequest(http.MethodGet, "/stay-fees/pdfs.zip", nil))
	if pattern != "GET /stay-fees/pdfs.zip" {
		t.Errorf("GET /stay-fees/pdfs.zip: pattern %q, the detail page shadows it", pattern)
	}
}
