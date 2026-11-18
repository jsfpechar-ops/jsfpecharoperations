package ruian

import (
	"strings"
	"unicode"

	"golang.org/x/text/unicode/norm"
)

// Fold lower-cases s, removes the Czech diacritics (and any other combining
// mark) and collapses runs of white space to one space.
func Fold(s string) string {
	var b strings.Builder
	for _, r := range norm.NFD.String(s) {
		if unicode.Is(unicode.Mn, r) {
			continue
		}
		b.WriteRune(unicode.ToLower(r))
	}
	return strings.Join(strings.Fields(b.String()), " ")
}

// SearchText is the folded text a row is found by: "street no/orient part obec zip".
func SearchText(street, houseNo, orientNo, part, obec, zip string) string {
	no := houseNo
	if orientNo != "" {
		no += "/" + orientNo
	}
	var parts []string
	for _, p := range []string{street, no, part, obec, zip} {
		if p != "" {
			parts = append(parts, p)
		}
	}
	return Fold(strings.Join(parts, " "))
}
