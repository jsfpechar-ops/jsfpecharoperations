package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestLeonQuestionsRoutesRegistered(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	cases := []struct{ method, path, pattern string }{
		{http.MethodGet, "/l/staytok/42/guide/leon", "GET /l/{token}/{reservation_id}/guide/leon"},
		{http.MethodPost, "/l/staytok/42/guide/leon", "POST /l/{token}/{reservation_id}/guide/leon"},
		{http.MethodGet, "/g/qrtok/leon", "GET /g/{token}/leon"},
		{http.MethodPost, "/g/qrtok/leon", "POST /g/{token}/leon"},
		{http.MethodGet, "/apartments/9/guide/questions", "GET /apartments/{apartment_id}/guide/questions"},
		{http.MethodGet, "/apartments/9/guide/questions/3", "GET /apartments/{apartment_id}/guide/questions/{question_id}"},
		{http.MethodPost, "/apartments/9/guide/questions/3", "POST /apartments/{apartment_id}/guide/questions/{question_id}"},
		{http.MethodPost, "/apartments/9/guide/questions/3/dismiss", "POST /apartments/{apartment_id}/guide/questions/{question_id}/dismiss"},
		{http.MethodPost, "/apartments/9/guide/questions/3/card", "POST /apartments/{apartment_id}/guide/questions/{question_id}/card"},
	}
	for _, c := range cases {
		_, pattern := mux.Handler(httptest.NewRequest(c.method, c.path, nil))
		if pattern != c.pattern {
			t.Errorf("%s %s: pattern %q, want %q", c.method, c.path, pattern, c.pattern)
		}
	}
}
