package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func withPaymentsHidden(on bool) {
	if on {
		os.Setenv("UBYHOST_PAYMENTS_HIDDEN", "1")
	} else {
		os.Unsetenv("UBYHOST_PAYMENTS_HIDDEN")
	}
}

func TestPaymentsHiddenRoutesBlocked(t *testing.T) {
	withPaymentsHidden(true)
	t.Cleanup(func() { withPaymentsHidden(false) })

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

func TestPaymentsHiddenOffDoesNotGate(t *testing.T) {
	withPaymentsHidden(false)
	t.Cleanup(func() { withPaymentsHidden(false) })
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
