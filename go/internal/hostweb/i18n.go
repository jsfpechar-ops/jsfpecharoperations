package hostweb

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"strings"
)

//go:embed i18n.json
var hostJSON []byte

// HostStrings is the host catalog generated from App/app/host_i18n.py by
// App/scripts/go_host_i18n.py.
var HostStrings = Load(hostJSON)

// Catalog maps a language code to its key and text table.
type Catalog map[string]map[string]string

// Load parses an i18n.json catalog. The files are embedded at build time, so
// bad JSON is a programming error and panics.
func Load(data []byte) Catalog {
	var c Catalog
	if err := json.Unmarshal(data, &c); err != nil {
		panic("hostweb: bad i18n.json: " + err.Error())
	}
	return c
}

// T is host_i18n.translate with lookup(): an unknown language uses the default
// table, a missing key falls back to the default table and then to the key
// itself, and placeholders that do not match the params return the raw text.
func (c Catalog) T(lang, key string, params map[string]any) string {
	text, ok := c[normalise(lang)][key]
	if !ok {
		text, ok = c[DefaultLanguage][key]
	}
	if !ok {
		text = key
	}
	if len(params) == 0 {
		return text
	}
	out, ok := format(text, params)
	if !ok {
		return text
	}
	return out
}

// format fills %(name)s and %% the way Python does with a mapping. Any other
// conversion, or a name without a value, reports false so the raw text is used.
func format(text string, params map[string]any) (string, bool) {
	var b strings.Builder
	for i := 0; i < len(text); i++ {
		if text[i] != '%' {
			b.WriteByte(text[i])
			continue
		}
		if i+1 < len(text) && text[i+1] == '%' {
			b.WriteByte('%')
			i++
			continue
		}
		if i+1 >= len(text) || text[i+1] != '(' {
			return "", false
		}
		closeAt := strings.IndexByte(text[i:], ')')
		if closeAt < 0 || i+closeAt+1 >= len(text) {
			return "", false
		}
		value, ok := params[text[i+2:i+closeAt]]
		if !ok {
			return "", false
		}
		switch text[i+closeAt+1] {
		case 's':
			if value == nil {
				b.WriteString("None")
			} else {
				b.WriteString(fmt.Sprint(value))
			}
		case 'd':
			switch value.(type) {
			case int, int64:
				b.WriteString(fmt.Sprint(value))
			default:
				return "", false
			}
		default:
			return "", false
		}
		i += closeAt + 1
	}
	return b.String(), true
}
