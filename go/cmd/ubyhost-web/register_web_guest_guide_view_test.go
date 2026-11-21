package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGuestGuideViewRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct{ method, path, pattern string }{
		{http.MethodGet, "/g/abcdefghijklmnop", "GET /g/{token}"},
		{http.MethodGet, "/g/abcdefghijklmnop/photos/1/2", "GET /g/{token}/photos/{item_id}/{photo_id}"},
		{http.MethodGet, "/l/tok/9/guide", "GET /l/{token}/{reservation_id}/guide"},
		{http.MethodGet, "/l/tok/9/guide/photos/1/2", "GET /l/{token}/{reservation_id}/guide/photos/{item_id}/{photo_id}"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
