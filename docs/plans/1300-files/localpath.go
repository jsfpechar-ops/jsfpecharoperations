package properties

import (
	"net/http"
	"path"
	"strings"
	"unicode"
)

// pyStrip is Python str.strip(): Unicode whitespace plus \x1c-\x1f.
func pyStrip(s string) string {
	return strings.TrimFunc(s, func(r rune) bool {
		return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
	})
}

// formStr is admin_helpers.form_str: the stripped value of a form field, "" when
// it is missing. Starlette keeps the LAST value of a repeated field.
func formStr(r *http.Request, key string) string {
	values := r.PostForm[key]
	if len(values) == 0 {
		return ""
	}
	return pyStrip(values[len(values)-1])
}

// pyUnquote is urllib.parse.unquote: %XX sequences become bytes, read as
// UTF-8 with U+FFFD for bad bytes; a bad sequence such as "%zz" stays as it is.
func pyUnquote(s string) string {
	if !strings.Contains(s, "%") {
		return s
	}
	var b []byte
	for i := 0; i < len(s); i++ {
		if s[i] == '%' && i+2 < len(s) && isHex(s[i+1]) && isHex(s[i+2]) {
			b = append(b, hexVal(s[i+1])<<4|hexVal(s[i+2]))
			i += 2
			continue
		}
		b = append(b, s[i])
	}
	return strings.ToValidUTF8(string(b), "�")
}

func isHex(c byte) bool {
	return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')
}

func hexVal(c byte) byte {
	switch {
	case c >= 'a':
		return c - 'a' + 10
	case c >= 'A':
		return c - 'A' + 10
	}
	return c - '0'
}

// splitURL is urlsplit for a value that starts with "/": no scheme and no
// host, so only the path, query and fragment remain.
func splitURL(raw string) (p, query, fragment string) {
	p = raw
	if i := strings.IndexByte(p, '#'); i >= 0 {
		p, fragment = p[:i], p[i+1:]
	}
	if i := strings.IndexByte(p, '?'); i >= 0 {
		p, query = p[:i], p[i+1:]
	}
	return p, query, fragment
}

func hasControl(s string) bool {
	for _, r := range s {
		if r < 0x20 {
			return true
		}
	}
	return false
}

// safeLocalPath is security.safe_local_path: a normalised same-site path with
// its query, or def for unsafe input. A value that does not start with "/" has
// a scheme or no path in Python's urlsplit, so it is refused here too. (Python
// raises ValueError for a few malformed "//[" hosts; Go answers def.)
func safeLocalPath(value, def string) string {
	raw := pyStrip(value)
	if raw == "" || hasControl(raw) || strings.Contains(raw, "\\") {
		return def
	}
	if !strings.HasPrefix(raw, "/") {
		return def
	}
	// urlsplit reads "//" as the start of a host: "///x" has an empty host and
	// the path "/x", while "//host/x", "//" and "//?q" are refused.
	if strings.HasPrefix(raw, "//") {
		raw = raw[2:]
		if !strings.HasPrefix(raw, "/") {
			return def
		}
	}
	p, query, _ := splitURL(raw)
	decoded := pyUnquote(p)
	if strings.HasPrefix(decoded, "//") || strings.Contains(decoded, "\\") || hasControl(decoded) {
		return def
	}
	clean := path.Clean(p)
	if !strings.HasPrefix(clean, "/") || strings.HasPrefix(clean, "//") {
		return def
	}
	if query != "" {
		return clean + "?" + query
	}
	return clean
}

// fragmentOf is urlsplit(raw).fragment for the values formReturnTo passes: the
// text after the first "#".
func fragmentOf(raw string) string {
	if i := strings.IndexByte(raw, '#'); i >= 0 {
		return raw[i+1:]
	}
	return ""
}

func isFragmentWord(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if !(r == '_' || r == '-' || unicode.IsLetter(r) || unicode.IsNumber(r)) {
			return false
		}
	}
	return true
}

// formReturnTo is admin.py _form_return_to: the posted return_to when it is a
// safe local path (also when it arrives percent-encoded), else def. With
// keepFragment a plain #fragment is kept.
func formReturnTo(r *http.Request, def string, keepFragment bool) string {
	raw := formStr(r, "return_to")
	if raw == "" {
		return def
	}
	fragment := fragmentOf(raw)
	p := safeLocalPath(raw, "")
	if p == "" {
		p = safeLocalPath(pyUnquote(raw), "")
	}
	if p == "" {
		return def
	}
	if keepFragment && fragment != "" && isFragmentWord(fragment) {
		return p + "#" + fragment
	}
	return p
}

// locationQuote is Starlette RedirectResponse's quote(url, safe=":/%#?=@[]!$&'()*+,;"),
// which hostweb.Back does not apply: non-ASCII and unsafe bytes of a posted
// return_to become %XX.
func locationQuote(s string) string {
	const hexDigits = "0123456789ABCDEF"
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case c >= 'a' && c <= 'z', c >= 'A' && c <= 'Z', c >= '0' && c <= '9':
			b.WriteByte(c)
		case strings.IndexByte("_.-~:/%#?=@[]!$&'()*+,;", c) >= 0:
			b.WriteByte(c)
		default:
			b.WriteByte('%')
			b.WriteByte(hexDigits[c>>4])
			b.WriteByte(hexDigits[c&15])
		}
	}
	return b.String()
}
