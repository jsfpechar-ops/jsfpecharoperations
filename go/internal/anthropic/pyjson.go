package anthropic

import (
	"fmt"
	"strings"
	"unicode/utf8"
)

// PyJSONString quotes s exactly like Python json.dumps(s, ensure_ascii=False):
// only the quote, the backslash and the control characters below U+0020 are
// escaped; everything else (including U+007F and U+2028) stays as it is.
func PyJSONString(s string) string {
	var b strings.Builder
	b.Grow(len(s) + 2)
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

// EstimateInputTokens is the port of ai.estimate_input_tokens for text-only
// messages: 1 token per 2 characters (code points), rounded up, over the
// system blocks plus json.dumps(messages, ensure_ascii=False). The Python
// image-block branch is not ported: this package sends text only.
func EstimateInputTokens(system []string, messages []Message) int {
	chars := 0
	for _, s := range system {
		chars += utf8.RuneCountInString(s)
	}
	parts := make([]string, 0, len(messages))
	for _, m := range messages {
		parts = append(parts, `{"role": `+PyJSONString(m.Role)+`, "content": `+PyJSONString(m.Content)+`}`)
	}
	chars += utf8.RuneCountInString("[" + strings.Join(parts, ", ") + "]")
	return (chars + 1) / 2
}
