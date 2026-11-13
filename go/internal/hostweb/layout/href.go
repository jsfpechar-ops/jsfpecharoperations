package layout

import (
	"html/template"
	"strings"
)

// unsafeHref is what html/template writes for a URL it will not emit.
const unsafeHref = "#ZgotmplZ"

// safeHref is an href a macro builds, escaped for the attribute: a relative
// URL (no scheme) or an http, https or mailto one. Any other scheme
// (javascript:, data:, vbscript: ...) becomes "#ZgotmplZ", as html/template
// does for its own URL attributes. The macros build their markup as strings,
// so html/template never sees these hrefs; this is the check it would make.
// Browsers drop ASCII whitespace and control characters inside a scheme, so
// the check does too. Jinja has no such check: a safe href renders the same.
func safeHref(v any) string {
	s := pyStr(v)
	if h, ok := v.(template.HTML); ok {
		s = string(h)
	}
	var b strings.Builder
	for _, r := range s {
		if r > 0x20 && r != 0x7f {
			b.WriteRune(r)
		}
	}
	probe := strings.ToLower(b.String())
	if i := strings.IndexAny(probe, ":/?#"); i >= 0 && probe[i] == ':' {
		switch probe[:i] {
		case "http", "https", "mailto":
		default:
			return unsafeHref
		}
	}
	return esc(v)
}

// href is the argument through safeHref, "" when missing.
func (a args) href(k string) string {
	if x, ok := a.vals[k]; ok {
		return safeHref(x)
	}
	return ""
}
