package session

import (
	"fmt"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"
)

// pyField is one key of a payload written in a fixed (Python dict) order.
type pyField struct {
	key   string
	value any
}

// pyCompact is json.dumps(fields, separators=(",", ":")), the itsdangerous
// _CompactJSON encoding, for the value types auth payloads hold.
func pyCompact(fields []pyField) string {
	var b strings.Builder
	b.WriteByte('{')
	for i, f := range fields {
		if i > 0 {
			b.WriteByte(',')
		}
		b.WriteString(pyString(f.key))
		b.WriteByte(':')
		b.WriteString(pyValue(f.value, ","))
	}
	b.WriteByte('}')
	return b.String()
}

// pyValue encodes one value; sep is the list separator ("," compact, ", " default).
func pyValue(v any, sep string) string {
	switch x := v.(type) {
	case nil:
		return "null"
	case bool:
		if x {
			return "true"
		}
		return "false"
	case int64:
		return strconv.FormatInt(x, 10)
	case string:
		return pyString(x)
	case []int64:
		parts := make([]string, len(x))
		for i, n := range x {
			parts[i] = strconv.FormatInt(n, 10)
		}
		return "[" + strings.Join(parts, sep) + "]"
	case []string:
		parts := make([]string, len(x))
		for i, s := range x {
			parts[i] = pyString(s)
		}
		return "[" + strings.Join(parts, sep) + "]"
	}
	panic(fmt.Sprintf("pyValue: unsupported %T", v))
}

// pyDumpsList is json.dumps(list_of_str) with the default ", " separator.
func pyDumpsList(items []string) string {
	return pyValue(items, ", ")
}

// pyString is json.dumps(s, ensure_ascii=False), as itsdangerous's
// _CompactJSON writes it: only '"', '\\' and control characters below U+0020
// are escaped (\uXXXX in lower-case hex); everything else stays UTF-8.
func pyString(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		default:
			if r < 0x20 {
				fmt.Fprintf(&b, `\u%04x`, r)
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
	return b.String()
}

// pyQuote is urllib.parse.quote(s, safe=safe): UTF-8 bytes, letters, digits
// and "_.-~" plus safe stay, everything else is %XX in upper-case hex.
func pyQuote(s, safe string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < utf8.RuneSelf && (c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' ||
			strings.IndexByte("_.-~", c) >= 0 || strings.IndexByte(safe, c) >= 0) {
			b.WriteByte(c)
			continue
		}
		fmt.Fprintf(&b, "%%%02X", c)
	}
	return b.String()
}

// pySpace is str.isspace(): Go's unicode.IsSpace plus the ASCII separators
// U+001C to U+001F, which Python also counts as whitespace.
func pySpace(r rune) bool {
	return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f)
}

// pyStrip is str.strip() with no argument.
func pyStrip(s string) string {
	return strings.TrimFunc(s, pySpace)
}

// pyRemoveSpace is re.sub(r"\s+", "", s) on a str.
func pyRemoveSpace(s string) string {
	return strings.Map(func(r rune) rune {
		if pySpace(r) {
			return -1
		}
		return r
	}, s)
}

// isASCII is str.isascii().
func isASCII(s string) bool {
	for i := 0; i < len(s); i++ {
		if s[i] >= utf8.RuneSelf {
			return false
		}
	}
	return true
}
