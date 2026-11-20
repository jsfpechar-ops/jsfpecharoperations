package guest

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ruian"
)

func TestRuianUsableQueryParity(t *testing.T) {
	if got := ruian.UsableQuery("ab"); got != "" {
		t.Fatalf("short %q", got)
	}
	if got := ruian.UsableQuery("  Praha  "); got != "Praha" {
		t.Fatalf("trim %q", got)
	}
}

func TestPrivacyTemplateRenders(t *testing.T) {
	view := PrivacyView{
		Page:             Page{Lang: "en", Token: "tok", GuestEndonyms: GuestEndonyms, PrivacyURL: "/l/tok/privacy"},
		BackURL:          "/l/tok",
		NoticeVersion:    "1.0",
		CookieInventory:  guestCookieInventory,
		SoftwareOperator: SoftwareOperator{Name: "UbyHost s.r.o.", ICO: "123"},
		MailEnabled:      true,
	}
	var buf strings.Builder
	if err := privacySet.ExecuteTemplate(&buf, "guest.base", view); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(buf.String(), "Privacy notice") {
		t.Fatal("missing title")
	}
}

func TestRuianSuggestRoutePattern(t *testing.T) {
	mux := http.NewServeMux()
	now := func() time.Time { return time.Unix(0, 0) }
	getenv := func(string) string { return "" }
	RegisterShell(mux, nil, getenv, now, func(_ string, h http.HandlerFunc) http.Handler { return h })
	req := httptest.NewRequest(http.MethodGet, "/l/tok/ruian-suggest?q=Praha", nil)
	_, pattern := mux.Handler(req)
	if pattern != "GET /l/{token}/ruian-suggest" {
		t.Fatalf("pattern %q", pattern)
	}
}
