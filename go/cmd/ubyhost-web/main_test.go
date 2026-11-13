package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func TestParseGoKindsPush(t *testing.T) {
	kinds, err := parseGoKinds("push")
	if err != nil || len(kinds) != 1 || kinds[0] != "push" {
		t.Fatalf("parseGoKinds(push) = %v, %v", kinds, err)
	}
	if goIntervals["push"] != 1 {
		t.Fatalf("push interval %d, want 1 minute", goIntervals["push"])
	}
}

func TestParseGoKindsDeadlines(t *testing.T) {
	kinds, err := parseGoKinds("submit, deadlines")
	if err != nil || len(kinds) != 2 || kinds[1] != "deadlines" {
		t.Fatalf("parseGoKinds(submit, deadlines) = %v, %v", kinds, err)
	}
	if goIntervals["deadlines"] != 30 {
		t.Fatalf("deadlines interval %d, want 30 minutes", goIntervals["deadlines"])
	}
}

func TestWrapSetsHardenHeaders(t *testing.T) {
	m := &metrics{counts: map[key]int64{}}
	h := m.wrap("/test", func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte("ok"))
	})
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/test", nil))
	for _, hv := range hardenHeaders {
		if got := rec.Header().Get(hv[0]); got != hv[1] {
			t.Errorf("%s = %q, want %q", hv[0], got, hv[1])
		}
	}
}

func TestWrapRouteHeaderWins(t *testing.T) {
	m := &metrics{counts: map[key]int64{}}
	h := m.wrap("/test", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Write([]byte("ok"))
	})
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/test", nil))
	if got := rec.Header().Get("Cache-Control"); got != "no-store" {
		t.Errorf("Cache-Control = %q, want no-store", got)
	}
	if got := rec.Header().Get("X-Content-Type-Options"); got != "nosniff" {
		t.Errorf("X-Content-Type-Options = %q, want nosniff", got)
	}
}

func TestCSPMatchesPython(t *testing.T) {
	src, err := os.ReadFile("../../../App/app/main.py")
	if err != nil {
		t.Fatalf("read main.py: %v", err)
	}
	const want = "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
	if !strings.Contains(string(src), want) {
		t.Fatalf("App/app/main.py no longer contains the CSP prefix %q; update hardenHeaders too", want)
	}
}

func TestLaneKindsDisjoint(t *testing.T) {
	filing := filingHandlers(nil)
	for k := range jobHandlers(nil) {
		if _, ok := filing[k]; ok {
			t.Errorf("kind %q is in both register_jobs.go and register_filing.go", k)
		}
	}
}

func TestEveryHandlerHasInterval(t *testing.T) {
	handlers := goHandlers(nil)
	for k := range handlers {
		if goIntervals[k] <= 0 {
			t.Errorf("handler %q has no interval > 0", k)
		}
	}
	for k := range goIntervals {
		if _, ok := handlers[k]; !ok {
			t.Errorf("interval %q has no handler", k)
		}
	}
}
