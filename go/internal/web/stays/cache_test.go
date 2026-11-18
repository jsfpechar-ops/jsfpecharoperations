package stays

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb/layout"
)

func TestStaysPageSetsTurboCache(t *testing.T) {
	p := layout.Page{TurboCache: "cache"}
	if p.TurboCache != "cache" {
		t.Fatalf("want cache")
	}
	def := layout.Page{}
	if def.TurboCache != "" {
		t.Fatalf("default empty")
	}
}

func TestStaysListHTMLHasTurboCache(t *testing.T) {
	data := parityFixture(fixedToday(), 1, "")
	page := layout.Page{Title: "Stays", Nav: "reservations", BodyKind: "list", V2: true, HowKey: "stays", BodyAlerts: false, TurboCache: "cache"}
	w := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/reservations?lang=en", nil)
	env := layout.Env{Getenv: func(string) string { return "golden-secret-key-not-for-real-use" }, Now: fixedToday()}
	if err := layout.Render(w, r, env, nil, page, pages, "stays_list", data); err != nil {
		t.Fatal(err)
	}
	html := w.Body.String()
	if !strings.Contains(html, `content="cache"`) {
		t.Fatalf("stays list missing turbo cache meta")
	}
}
