package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGuestLifecycleRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct{ method, path, pattern string }{
		{http.MethodPost, "/guests/7/archive", "POST /guests/{guest_id}/archive"},
		{http.MethodPost, "/guests/7/unarchive", "POST /guests/{guest_id}/unarchive"},
		{http.MethodPost, "/guests/7/delete", "POST /guests/{guest_id}/delete"},
		{http.MethodPost, "/guests/7/resend", "POST /guests/{guest_id}/resend"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
