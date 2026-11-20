package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestStaysEditPostsRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct {
		method, path, pattern string
	}{
		{http.MethodPost, "/reservations/7/quick-edit", "POST /reservations/{reservation_id}/quick-edit"},
		{http.MethodPost, "/reservations/7/remove-empty-slot", "POST /reservations/{reservation_id}/remove-empty-slot"},
		{http.MethodPost, "/reservations/7/archive", "POST /reservations/{reservation_id}/archive"},
		{http.MethodPost, "/reservations/7/unarchive", "POST /reservations/{reservation_id}/unarchive"},
		{http.MethodPost, "/reservations/7/delete-demo", "POST /reservations/{reservation_id}/delete-demo"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
