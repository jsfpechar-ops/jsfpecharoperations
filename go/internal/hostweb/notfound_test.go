package hostweb

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestWantsHTML(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/payments", nil)
	req.Header.Set("Accept", "text/html")
	if !WantsHTML(req) {
		t.Fatal("expected html")
	}
	req = httptest.NewRequest(http.MethodGet, "/api/command-palette", nil)
	req.Header.Set("Accept", "text/html")
	if WantsHTML(req) {
		t.Fatal("/api/ never wants html")
	}
}

func TestBlockedPageHTML(t *testing.T) {
	rec := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/payments", nil)
	r.Header.Set("Accept", "text/html")
	BlockedPage(rec, r)
	if rec.Code != http.StatusNotFound || !strings.Contains(rec.Body.String(), "Page not found") {
		t.Fatalf("got %d body %q", rec.Code, rec.Body.String())
	}
}

func TestBlockedPageEmpty(t *testing.T) {
	rec := httptest.NewRecorder()
	BlockedPage(rec, httptest.NewRequest(http.MethodPost, "/payments/services", nil))
	if rec.Code != http.StatusNotFound || rec.Body.Len() != 0 {
		t.Fatalf("got %d len %d", rec.Code, rec.Body.Len())
	}
}

func TestNotFoundPageHTML(t *testing.T) {
	rec := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/reservations/999", nil)
	r.Header.Set("Accept", "text/html")
	NotFoundPage(rec, r)
	if rec.Code != http.StatusNotFound || !strings.Contains(rec.Body.String(), "Page not found") {
		t.Fatalf("got %d body %q", rec.Code, rec.Body.String())
	}
}

func TestNotFoundPageEmpty(t *testing.T) {
	rec := httptest.NewRecorder()
	NotFoundPage(rec, httptest.NewRequest(http.MethodPost, "/reservations/999", nil))
	if rec.Code != http.StatusNotFound || rec.Body.Len() != 0 {
		t.Fatalf("got %d len %d", rec.Code, rec.Body.Len())
	}
}

func TestGuestPath(t *testing.T) {
	for _, c := range []struct {
		path string
		want bool
	}{{"/l", true}, {"/l/key/7", true}, {"/login", false}, {"/lorem", false}} {
		if got := GuestPath(httptest.NewRequest(http.MethodGet, c.path, nil)); got != c.want {
			t.Fatalf("%s: got %v want %v", c.path, got, c.want)
		}
	}
}
