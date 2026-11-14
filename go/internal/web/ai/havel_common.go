package ai

// havel_common.go: the small Python behaviours the Havel and Leon ports share.
// Everything here is prefixed `havel` so it cannot clash with another file of
// package ai.
//
// Python's re module is Unicode-aware and has look-around; Go's RE2 has neither.
// havelFold maps a text to one ASCII byte per rune so that RE2's ASCII \w \d \s
// \b see what Python sees: a non-ASCII letter or number becomes '_' (a word
// character that is no ASCII letter or digit), a non-ASCII decimal digit
// becomes '0', whitespace becomes ' ', anything else '~'. The offsets of a
// match on the folded text are rune offsets of the original.

import (
	"encoding/json"
	"regexp"
	"strings"
	"unicode"
	"unicode/utf8"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
)

// havelIsSpace is Python str.isspace for one character.
func havelIsSpace(r rune) bool {
	switch r {
	case '\t', '\n', '\v', '\f', '\r', ' ', 0x1c, 0x1d, 0x1e, 0x1f, 0x85, 0xa0, 0x1680, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000:
		return true
	}
	return r >= 0x2000 && r <= 0x200a
}

// havelStrip is str.strip().
func havelStrip(s string) string { return strings.TrimFunc(s, havelIsSpace) }

// havelFields is str.split() with no argument.
func havelFields(s string) []string { return strings.FieldsFunc(s, havelIsSpace) }

// havelClip is s[:n] on code points.
func havelClip(s string, n int) string {
	if n <= 0 {
		return ""
	}
	if utf8.RuneCountInString(s) <= n {
		return s
	}
	return string([]rune(s)[:n])
}

// havelLen is len(s) on code points.
func havelLen(s string) int { return utf8.RuneCountInString(s) }

// havelFold returns the folded text and the runes of the original.
func havelFold(s string) (string, []rune) {
	runes := []rune(s)
	b := make([]byte, len(runes))
	for i, r := range runes {
		switch {
		case r < 0x80:
			switch {
			case r == '\v' || (r >= 0x1c && r <= 0x1f):
				b[i] = ' '
			default:
				b[i] = byte(r)
			}
		case havelIsSpace(r):
			b[i] = ' '
		case unicode.Is(unicode.Nd, r):
			b[i] = '0'
		case unicode.IsLetter(r) || unicode.IsNumber(r):
			b[i] = '_'
		default:
			b[i] = '~'
		}
	}
	return string(b), runes
}

// havelMatches is re.finditer on the folded text: [start, end) rune offsets.
// RE2 gives the same leftmost-first matches as Python for the patterns used.
func havelMatches(re *regexp.Regexp, s string) [][2]int {
	folded, _ := havelFold(s)
	found := re.FindAllStringIndex(folded, -1)
	out := make([][2]int, len(found))
	for i, f := range found {
		out[i] = [2]int{f[0], f[1]}
	}
	return out
}

// havelSub is re.sub(pattern, repl, s) with a function replacement.
func havelSub(re *regexp.Regexp, s string, repl func(match string) string) string {
	folded, runes := havelFold(s)
	found := re.FindAllStringIndex(folded, -1)
	if len(found) == 0 {
		return s
	}
	var b strings.Builder
	last := 0
	for _, f := range found {
		b.WriteString(string(runes[last:f[0]]))
		b.WriteString(repl(string(runes[f[0]:f[1]])))
		last = f[1]
	}
	b.WriteString(string(runes[last:]))
	return b.String()
}

// havelFindAll is re.findall for a pattern without groups.
func havelFindAll(re *regexp.Regexp, s string) []string {
	_, runes := havelFold(s)
	var out []string
	for _, m := range havelMatches(re, s) {
		out = append(out, string(runes[m[0]:m[1]]))
	}
	return out
}

// havelSearch is re.search(...) is not None.
func havelSearch(re *regexp.Regexp, s string) bool {
	folded, _ := havelFold(s)
	return re.MatchString(folded)
}

// havelPyString is json.dumps(s, ensure_ascii=False).
func havelPyString(s string) string { return anthropic.PyJSONString(s) }

// havelPyInt is the _int helper: an int from the model's JSON (a json.Number
// without a fraction or exponent), never a bool. Python ints have no limit; a
// value that does not fit int64 reports false.
func havelPyInt(v any) (int64, bool) {
	n, ok := v.(json.Number)
	if !ok || strings.ContainsAny(string(n), ".eE") {
		return 0, false
	}
	i, err := n.Int64()
	return i, err == nil
}

// havelPyStr is str(v) for a value out of the model's JSON; only the shapes
// that can reach a regular expression matter.
func havelPyStr(v any) string {
	switch t := v.(type) {
	case string:
		return t
	case nil:
		return "None"
	case bool:
		if t {
			return "True"
		}
		return "False"
	case json.Number:
		return string(t)
	}
	return "<object>"
}
