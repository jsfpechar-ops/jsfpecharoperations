package invoices

import (
	"net/http"
	"sort"
	"strings"
	"testing"
	"time"
)

func TestRoutesAreListedWithoutAPool(t *testing.T) {
	routes := Routes(nil, testEnv(), time.Now)
	if len(routes) != 8 {
		t.Fatalf("%d routes", len(routes))
	}
	seen := map[string]bool{}
	mux := http.NewServeMux()
	for _, r := range routes {
		if seen[r.Pattern] {
			t.Errorf("pattern %q twice", r.Pattern)
		}
		seen[r.Pattern] = true
		if r.Label == "" || r.Handler == nil || !strings.Contains(r.Pattern, " /") {
			t.Errorf("route %+v", r)
		}
		mux.Handle(r.Pattern, r.Handler) // panics on a conflict
	}
	var patterns []string
	for p := range seen {
		patterns = append(patterns, p)
	}
	sort.Strings(patterns)
	want := []string{"GET /invoice/d/{token}", "GET /invoices", "GET /invoices/new", "GET /invoices/{id}", "POST /invoices", "POST /invoices/preview",
		"POST /invoices/{id}/cancel", "POST /invoices/{id}/paid"}
	for _, w := range want {
		if !seen[w] {
			t.Errorf("route %q missing from %v", w, patterns)
		}
	}
}

func TestSendRouteIsNotThere(t *testing.T) {
	for _, r := range Routes(nil, testEnv(), time.Now) {
		if strings.Contains(r.Pattern, "/send") {
			t.Errorf("%s is blocked on brief 1429 and must stay on Python", r.Pattern)
		}
	}
}

// ---- the string catalog ----
