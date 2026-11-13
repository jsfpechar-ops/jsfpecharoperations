package layout

// pagefuncs.go: what page packages asked for in 1381: the language Render
// uses, page funcs at parse time, and small generic template helpers.

import (
	"fmt"
	"html/template"
	"io/fs"
	"net/http"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// Lang is the language Render resolves for this request and host: a
// signed-in host falls back to English, a visitor to Czech, public pages are
// en or cs only. A non-empty Page.Lang (en, cs, vi) still wins inside Render.
// Pages call it to translate Page.Title before Render.
func Lang(r *http.Request, host *session.Host) string {
	return resolveLang(r, host != nil, Page{})
}

// ParseFuncs is Parse with page funcs added to the layout's. A page func may
// not reuse a layout func name (t, csrf, ui_button, seq ...): that is an error.
// Page funcs are not bound to the request; take what they need as arguments.
func ParseFuncs(cat hostweb.Catalog, funcs template.FuncMap, fsys fs.FS, patterns ...string) (*Templates, error) {
	base := &reqCtx{lang: hostweb.DefaultLanguage, page: cat, layout: Strings}
	layoutFuncs := base.funcs()
	for name := range funcs {
		if _, taken := layoutFuncs[name]; taken {
			return nil, fmt.Errorf("layout: page func %q overrides a layout func", name)
		}
	}
	master, err := template.New("layout").Funcs(layoutFuncs).Funcs(funcs).ParseFS(shellFS, "shell.html")
	if err != nil {
		return nil, err
	}
	if len(patterns) > 0 {
		if master, err = master.ParseFS(fsys, patterns...); err != nil {
			return nil, err
		}
	}
	return &Templates{cat: cat, master: master}, nil
}

// MustParseFuncs is ParseFuncs that panics, for package-level vars.
func MustParseFuncs(cat hostweb.Catalog, funcs template.FuncMap, fsys fs.FS, patterns ...string) *Templates {
	t, err := ParseFuncs(cat, funcs, fsys, patterns...)
	if err != nil {
		panic("layout: " + err.Error())
	}
	return t
}

// seq is Python's range: seq n is 0..n-1, seq a b is a..b-1.
func seq(bounds ...any) ([]int, error) {
	var lo, hi int
	switch len(bounds) {
	case 1:
		hi = toInt(bounds[0])
	case 2:
		lo, hi = toInt(bounds[0]), toInt(bounds[1])
	default:
		return nil, fmt.Errorf("seq: want 1 or 2 arguments, got %d", len(bounds))
	}
	out := []int{}
	for i := lo; i < hi; i++ {
		out = append(out, i)
	}
	return out, nil
}

func add(a, b any) int { return toInt(a) + toInt(b) }
func sub(a, b any) int { return toInt(a) - toInt(b) }

// dflt is Jinja's default filter for Go data, written {{default "x" .V}}:
// def when v is missing (nil, as a missing map key reads) or the empty
// string; any other value, false and 0 included, is kept.
func dflt(def, v any) any {
	if v == nil {
		return def
	}
	if s, ok := v.(string); ok && s == "" {
		return def
	}
	return v
}
