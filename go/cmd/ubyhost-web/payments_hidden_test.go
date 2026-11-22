package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestPaymentsHiddenRoutesBlocked(t *testing.T) {
	t.Setenv("UBYHOST_PAYMENTS_HIDDEN", "1")

	m := &metrics{counts: map[key]int64{}}
	mux := newMux(m, nil)

	cases := []struct {
		method, path string
		wantHTML     bool
	}{
		{http.MethodGet, "/payments", true},
		{http.MethodGet, "/payments/new", true},
		{http.MethodPost, "/payments/services", false},
		{http.MethodPost, "/payments/requests/new", false},
		{http.MethodGet, "/payments/connect/start", true},
	}
	for _, c := range cases {
		t.Run(c.method+" "+c.path, func(t *testing.T) {
			req := httptest.NewRequest(c.method, c.path, nil)
			if c.wantHTML {
				req.Header.Set("Accept", "text/html")
			}
			rec := httptest.NewRecorder()
			mux.ServeHTTP(rec, req)
			if rec.Code != http.StatusNotFound {
				t.Fatalf("status %d, want 404", rec.Code)
			}
			if c.wantHTML {
				if !strings.HasPrefix(rec.Header().Get("Content-Type"), "text/html") {
					t.Fatalf("Content-Type %q, want html", rec.Header().Get("Content-Type"))
				}
				if !strings.Contains(rec.Body.String(), "Page not found") && !strings.Contains(rec.Body.String(), "Stránka") {
					t.Fatalf("body lacks not-found copy")
				}
			} else if rec.Body.Len() != 0 {
				t.Fatalf("non-HTML block should be empty body, got %q", rec.Body.String())
			}
		})
	}
}

func TestPaymentsRetiredRoutesBlocked(t *testing.T) {
	t.Setenv("UBYHOST_PAYMENTS_RETIRED", "1")

	m := &metrics{counts: map[key]int64{}}
	mux := newMux(m, nil)

	cases := []struct {
		method, path string
		wantHTML     bool
	}{
		{http.MethodGet, "/p/slug/book", true},
		{http.MethodPost, "/p/slug/book", false},
		{http.MethodPost, "/p/slug/checkout", false},
		{http.MethodGet, "/p/slug/thanks", true},
		{http.MethodGet, "/p/slug/b/1/tok", true},
		{http.MethodGet, "/pay/1/abcd.png", true},
	}
	for _, c := range cases {
		t.Run(c.method+" "+c.path, func(t *testing.T) {
			req := httptest.NewRequest(c.method, c.path, nil)
			if c.wantHTML {
				req.Header.Set("Accept", "text/html")
			}
			rec := httptest.NewRecorder()
			mux.ServeHTTP(rec, req)
			if rec.Code != http.StatusNotFound {
				t.Fatalf("status %d, want 404", rec.Code)
			}
		})
	}
}

func TestPaymentsRetiredDoesNotBlockOpenPaths(t *testing.T) {
	t.Setenv("UBYHOST_PAYMENTS_RETIRED", "1")
	m := &metrics{counts: map[key]int64{}}
	for _, path := range []string{"/p/slug", "/p/slug/feed.ics", "/guide"} {
		h := m.wrap(path, func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusTeapot)
		})
		req := httptest.NewRequest(http.MethodGet, path, nil)
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if rec.Code != http.StatusTeapot {
			t.Fatalf("%s status %d, want handler to run", path, rec.Code)
		}
	}
}

func TestPaymentsHiddenOffDoesNotGate(t *testing.T) {
	t.Setenv("UBYHOST_PAYMENTS_HIDDEN", "0")
	m := &metrics{counts: map[key]int64{}}
	h := m.wrap("/payments", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusTeapot)
	})
	req := httptest.NewRequest(http.MethodGet, "/payments", nil)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusTeapot {
		t.Fatalf("status %d, want handler to run (418)", rec.Code)
	}
}
