package guideimport

// Small ports of the Python string and value rules that the trim and verify
// code depends on. Go and Python differ on whitespace, truthiness and float
// text, so each rule is spelled out here and pinned by the golden file.

import (
	"encoding/json"
	"math"
	"math/big"
	"strconv"
	"strings"
	"unicode"
)

// isSpace is Python str.isspace for one character: Go's unicode.IsSpace plus
// the four separators U+001C to U+001F.
func isSpace(r rune) bool { return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f) }

// pyStrip is str.strip().
func pyStrip(s string) string { return strings.TrimFunc(s, isSpace) }

// pyTrimRight is str.rstrip() on runes.
func pyTrimRight(r []rune) []rune {
	for len(r) > 0 && isSpace(r[len(r)-1]) {
		r = r[:len(r)-1]
	}
	return r
}

// pyCollapse is " ".join(s.split()).
func pyCollapse(s string) string {
	return strings.Join(strings.FieldsFunc(s, isSpace), " ")
}

// pyTruthy is Python truthiness for a decoded JSON value.
func pyTruthy(v any) bool {
	switch x := v.(type) {
	case nil:
		return false
	case bool:
		return x
	case string:
		return x != ""
	case json.Number:
		f, err := strconv.ParseFloat(string(x), 64)
		return err != nil || f != 0
	case []any:
		return len(x) > 0
	case map[string]any:
		return len(x) > 0
	}
	return true
}

// pyStr is str(value) for a decoded JSON value. Lists and objects (never
// produced by the trimmed data, and forbidden by the model schema) come back
// as their JSON text instead of the Python repr: a documented gap.
func pyStr(v any) string {
	switch x := v.(type) {
	case nil:
		return "None"
	case bool:
		if x {
			return "True"
		}
		return "False"
	case string:
		return x
	case json.Number:
		return pyNumber(string(x))
	}
	b, _ := json.Marshal(v)
	return string(b)
}

// pyNumber is str() of the Python int or float a JSON number decodes to.
func pyNumber(raw string) string {
	if !strings.ContainsAny(raw, ".eE") {
		if n, ok := new(big.Int).SetString(raw, 10); ok {
			return n.String()
		}
		return raw
	}
	f, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return raw
	}
	return pyFloat(f)
}

// pyFloat is repr(float): shortest round-trip digits, fixed notation for
// exponents from -4 up to 15, scientific beyond, and ".0" on whole numbers.
func pyFloat(f float64) string {
	if math.IsInf(f, 0) || math.IsNaN(f) {
		return strconv.FormatFloat(f, 'g', -1, 64)
	}
	if f == 0 {
		if math.Signbit(f) {
			return "-0.0"
		}
		return "0.0"
	}
	sign := ""
	if f < 0 {
		sign, f = "-", -f
	}
	e := strconv.FormatFloat(f, 'e', -1, 64) // d.ddde+XX
	mant, expPart, _ := strings.Cut(e, "e")
	exp, _ := strconv.Atoi(expPart)
	digits := strings.Replace(mant, ".", "", 1)
	decpt := exp + 1
	switch {
	case decpt > 16 || decpt < -3:
		out := digits[:1]
		if len(digits) > 1 {
			out += "." + digits[1:]
		}
		x := decpt - 1
		es := "+"
		if x < 0 {
			es, x = "-", -x
		}
		xs := strconv.Itoa(x)
		if len(xs) < 2 {
			xs = "0" + xs
		}
		return sign + out + "e" + es + xs
	case decpt <= 0:
		return sign + "0." + strings.Repeat("0", -decpt) + digits
	case decpt >= len(digits):
		return sign + digits + strings.Repeat("0", decpt-len(digits)) + ".0"
	}
	return sign + digits[:decpt] + "." + digits[decpt:]
}

// runeSlice is s[:n] on code points.
func runeSlice(s string, n int) string {
	r := []rune(s)
	if len(r) > n {
		r = r[:n]
	}
	return string(r)
}
