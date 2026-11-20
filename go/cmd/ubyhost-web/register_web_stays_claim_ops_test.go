package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestClaimOpsRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodPost, "/reservations/7/reopen-guest", "POST /reservations/{reservation_id}/reopen-guest"},
		{http.MethodPost, "/reservations/7/resend-claim", "POST /reservations/{reservation_id}/resend-claim"},
		{http.MethodPost, "/reservations/7/release-claim", "POST /reservations/{reservation_id}/release-claim"},
		{http.MethodPost, "/reservations/7/filed-by-hand", "POST /reservations/{reservation_id}/filed-by-hand"},
		{http.MethodPost, "/reservations/7/filed-by-hand/undo", "POST /reservations/{reservation_id}/filed-by-hand/undo"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
