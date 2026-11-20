package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGuestDraftScanRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodPost, "/l/tok/7/draft", "POST /l/{token}/{reservation_id}/draft"},
		{http.MethodPost, "/l/tok/7/scan", "POST /l/{token}/{reservation_id}/scan"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
