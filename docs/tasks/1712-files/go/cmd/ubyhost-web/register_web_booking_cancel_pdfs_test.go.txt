package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestBookingCancelPDFsRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodPost, "/p/slug/b/1/tok/cancel", "POST /p/{slug}/b/{booking_id}/{token}/cancel"},
		{http.MethodGet, "/p/slug/b/1/tok/invoice.pdf", "GET /p/{slug}/b/{booking_id}/{token}/invoice.pdf"},
		{http.MethodGet, "/p/slug/b/1/tok/correction.pdf", "GET /p/{slug}/b/{booking_id}/{token}/correction.pdf"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
