package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestPostCenikMethodNotAllowed(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodPost, "/cenik", nil))
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("POST /cenik: status=%d", rec.Code)
	}
	allow := rec.Header().Get("Allow")
	for _, want := range []string{"GET", "HEAD"} {
		if !strings.Contains(allow, want) {
			t.Fatalf("Allow=%q missing %s", allow, want)
		}
	}
}

func TestUnknownPathStill404(t *testing.T) {
	mux := newMux(&metrics{counts: map[key]int64{}}, nil)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/nope-not-a-route-2031", nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("GET unknown: status=%d", rec.Code)
	}
}
