package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestSubmitRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodPost, "/reservations/submit-ready", "POST /reservations/submit-ready"},
		{http.MethodPost, "/reservations/7/submit", "POST /reservations/{reservation_id}/submit"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
