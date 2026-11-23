package properties

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

const notPortedTestSecret = "notported-test-secret-key-0123456789abcdef"

func TestNotPortedHostPage(t *testing.T) {
	rec := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/entities", nil)
	r.Header.Set("Accept", "text/html")
	env := layout.Env{Pool: nil, Getenv: func(k string) string {
		if k == "UBYHOST_SECRET_KEY" {
			return notPortedTestSecret
		}
		return ""
	}, Now: time.Date(2026, 5, 1, 12, 0, 0, 0, time.UTC)}
	notPorted(rec, r, env, nil, "test branch")
	if rec.Code != http.StatusNotImplemented {
		t.Fatalf("status %d", rec.Code)
	}
	if rec.Header().Get("X-Ubyhost-Not-Ported") != "1" {
		t.Fatal("expected Not-Ported header")
	}
	body := rec.Body.String()
	for _, want := range []string{"This action is not available yet", "support@ubyhost.com", "layout-host", "ui-body-detail"} {
		if !strings.Contains(body, want) {
			t.Fatalf("body missing %q", want)
		}
	}
	if strings.Contains(body, "not served by Go yet") {
		t.Fatal("raw 501 text leaked to HTML")
	}
}

func TestNotPortedNonHTML(t *testing.T) {
	rec := httptest.NewRecorder()
	env := layout.Env{Getenv: func(string) string { return "" }, Now: time.Now()}
	notPorted(rec, httptest.NewRequest(http.MethodPost, "/entities", nil), env, nil, "x")
	if rec.Code != http.StatusNotImplemented || rec.Body.Len() != 0 {
		t.Fatalf("got %d len %d", rec.Code, rec.Body.Len())
	}
}
