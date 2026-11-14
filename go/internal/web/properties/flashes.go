package properties

// Counted flashes (admin_helpers.flash_plural), brief 1521.

import (
	"net/http"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
)

// pluralFlashKey is host_i18n.plural_key: Ukrainian has its own rule, every
// other language reads 1 as .one and 2 to 4 as .few.
func pluralFlashKey(base string, n int, lang string) string {
	if lang == "uk" {
		switch {
		case n%10 == 1 && n%100 != 11:
			return base + ".one"
		case n%10 >= 2 && n%10 <= 4 && (n%100 < 12 || n%100 > 14):
			return base + ".few"
		}
		return base
	}
	switch {
	case n == 1:
		return base + ".one"
	case n >= 2 && n <= 4:
		return base + ".few"
	}
	return base
}

// pluralFlash is flash_plural(request, key, n, **params): the text of the form
// the count needs, with count and n filled in, raised under the base key.
func pluralFlash(r *http.Request, base string, n int, params map[string]any) hostweb.Flash {
	lang := hostweb.Lang(r)
	p := map[string]any{"count": n, "n": n}
	for k, v := range params {
		p[k] = v
	}
	return hostweb.Flash{Text: catalog.T(lang, pluralFlashKey(base, n, lang), p), Key: base, Count: n}
}
