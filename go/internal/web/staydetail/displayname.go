package staydetail

import (
	"strings"
	"unicode"
)

// displayName title-cases a name stored in capitals (display only). A name that
// already has a lowercase letter is returned unchanged, so "McDonald" and
// "van der Berg" survive.
func displayName(s string) string {
	for _, r := range s {
		if unicode.IsLower(r) {
			return s
		}
	}
	var b strings.Builder
	b.Grow(len(s))
	start := true
	for _, r := range s {
		if start {
			b.WriteRune(unicode.ToUpper(r))
		} else {
			b.WriteRune(unicode.ToLower(r))
		}
		start = unicode.IsSpace(r) || r == '-' || r == '\'' || r == '\u2019'
	}
	return b.String()
}
