package auth

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// TestOperationsRoute: GET /admin/operations is in Routes and answers a
// signed-out visitor as _require_admin does: 303 to the login page, no body
// and no Content-Type (Starlette's RedirectResponse). The page itself is
// tested in package opspage against the Python golden.
func TestOperationsRoute(t *testing.T) {
	pool := testPool(t)
	mux := http.NewServeMux()
	found := 0
	getenv := func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return "test-secret-not-for-real-use-0123456789abcdef"
		}
		return ""
	}
	for _, r := range Routes(pool, getenv, time.Now) {
		if r.Pattern == "GET /admin/operations" {
			found++
			if r.Path != "/admin/operations" {
				t.Errorf("metrics label %q", r.Path)
			}
		}
		mux.Handle(r.Pattern, r.Handler)
	}
	if found != 1 {
		t.Fatalf("GET /admin/operations listed %d times", found)
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/admin/operations", nil))
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/admin/operations" ||
		rec.Header().Get("Content-Type") != "" || rec.Body.Len() != 0 {
		t.Fatalf("signed out: %d %q %q %q", rec.Code, rec.Header().Get("Location"), rec.Header().Get("Content-Type"), rec.Body.String())
	}
}
