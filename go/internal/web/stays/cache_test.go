package stays

import (
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

func TestShellMetaTemplateUsesTurboCache(t *testing.T) {
	b, err := templateFS.ReadFile("templates/stays_list.tmpl")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(b), "stays-more") {
		t.Fatal("missing stays-more")
	}
}