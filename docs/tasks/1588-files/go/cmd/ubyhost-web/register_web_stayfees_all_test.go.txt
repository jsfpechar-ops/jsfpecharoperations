package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestStayFeesAllRoutesRegistered lists the 16 routes of
// App/app/routes/stay_fees.py and checks that newMux serves each one from the
// Go pattern named here. A route that is missing falls to the catch-all (or to
// another pattern) and fails the test.
func TestStayFeesAllRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct{ method, path, want string }{
		{http.MethodGet, "/stay-fees", "GET /stay-fees"},
		{http.MethodGet, "/stay-fees/pdfs.zip", "GET /stay-fees/pdfs.zip"},
		{http.MethodGet, "/stay-fees/7", "GET /stay-fees/{apartment_id}"},
		{http.MethodGet, "/stay-fees/7/pdf", "GET /stay-fees/{apartment_id}/pdf"},
		{http.MethodGet, "/stay-fees/7/csv", "GET /stay-fees/{apartment_id}/csv"},
		{http.MethodPost, "/stay-fees/7/guest-pay-preview", "POST /stay-fees/{apartment_id}/guest-pay-preview"},
		{http.MethodPost, "/stay-fees/7/adjustment", "POST /stay-fees/{apartment_id}/adjustment"},
		{http.MethodPost, "/stay-fees/7/adjustment/3/undo", "POST /stay-fees/{apartment_id}/adjustment/{adjustment_id}/undo"},
		{http.MethodPost, "/stay-fees/guest-decision", "POST /stay-fees/guest-decision"},
		{http.MethodPost, "/stay-fees/7/scope-ruling", "POST /stay-fees/{apartment_id}/scope-ruling"},
		{http.MethodPost, "/stay-fees/confirm-ready", "POST /stay-fees/confirm-ready"},
		{http.MethodPost, "/stay-fees/7/copy-setup", "POST /stay-fees/{apartment_id}/copy-setup"},
		{http.MethodPost, "/stay-fees/7/finalize", "POST /stay-fees/{apartment_id}/finalize"},
		{http.MethodPost, "/stay-fees/7/paid", "POST /stay-fees/{apartment_id}/paid"},
		{http.MethodPost, "/stay-fees/7/filings/9/sent", "POST /stay-fees/{apartment_id}/filings/{filing_id}/sent"},
		{http.MethodPost, "/stay-fees/7/filings/9/paid", "POST /stay-fees/{apartment_id}/filings/{filing_id}/paid"},
	}
	if len(cases) != 16 {
		t.Fatalf("%d cases, want the 16 routes of stay_fees.py", len(cases))
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.want {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.want)
		}
	}
}
