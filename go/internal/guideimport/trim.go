package guideimport

import (
	"encoding/json"
	"slices"
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
)

// Caps of guest_guide_import.py.
const (
	maxStoredBytes = 64 * 1024
	maxText        = 4000
	maxListItems   = 80
	maxItemText    = 200
)

var textFields = map[string][]string{
	"booking": {"name", "description", "checkIn", "checkOut"},
	"airbnb":  {"title", "description", "subDescription", "propertyType", "roomType"},
}

var listFields = map[string][]string{
	"booking": {},
	"airbnb":  {"amenities", "houseRules", "locationDescriptions", "highlights"},
}

// Entry is one key of the trimmed listing: Value is a string or a []string.
type Entry struct {
	Key   string
	Value any
}

// Trimmed is the ordered dict trim() returns. The order is the order Python
// inserts keys, and it is the order of the stored JSON.
type Trimmed []Entry

// Get returns the value of key, or nil.
func (t Trimmed) Get(key string) any {
	for _, e := range t {
		if e.Key == key {
			return e.Value
		}
	}
	return nil
}

// JSON is json.dumps(data, ensure_ascii=False): ", " and ": " separators.
func (t Trimmed) JSON() string {
	var b strings.Builder
	b.WriteByte('{')
	for i, e := range t {
		if i > 0 {
			b.WriteString(", ")
		}
		b.WriteString(anthropic.PyJSONString(e.Key))
		b.WriteString(": ")
		switch v := e.Value.(type) {
		case string:
			b.WriteString(anthropic.PyJSONString(v))
		case []string:
			b.WriteByte('[')
			for j, s := range v {
				if j > 0 {
					b.WriteString(", ")
				}
				b.WriteString(anthropic.PyJSONString(s))
			}
			b.WriteByte(']')
		}
	}
	b.WriteByte('}')
	return b.String()
}

// pyText is _text(): empty for None, objects and lists; else the whitespace
// collapsed str() cut to limit code points.
func pyText(v any, limit int) string {
	switch v.(type) {
	case nil, map[string]any, []any:
		return ""
	}
	return runeSlice(pyCollapse(pyStr(v)), limit)
}

// flatten is _flatten(): the short strings of a nested list or dict.
func flatten(v any, out *[]string, depth int) {
	if len(*out) >= maxListItems || depth > 6 {
		return
	}
	switch x := v.(type) {
	case string:
		if text := pyText(x, maxItemText); text != "" && !slices.Contains(*out, text) {
			*out = append(*out, text)
		}
	case []any:
		for _, item := range x {
			flatten(item, out, depth+1)
		}
	case map[string]any:
		if b, ok := x["available"].(bool); ok && !b {
			return
		}
		for _, key := range []string{"title", "content", "subtitle", "values", "additional", "general"} {
			if val, ok := x[key]; ok {
				flatten(val, out, depth+1)
			}
		}
	}
}

// Trim is trim(): named text fields, lists and the address, size capped.
// item is the first dataset item decoded with UseNumber. A source with no
// entry in the field tables yields only the source key, as in Python.
func Trim(source string, item map[string]any) Trimmed {
	if item == nil {
		return Trimmed{}
	}
	out := Trimmed{{Key: "source", Value: source}}
	for _, key := range textFields[source] {
		if text := pyText(item[key], maxText); text != "" {
			out = append(out, Entry{key, text})
		}
	}
	for _, key := range listFields[source] {
		var lines []string
		flatten(item[key], &lines, 0)
		if len(lines) > 0 {
			out = append(out, Entry{key, lines})
		}
	}
	switch a := item["address"].(type) {
	case map[string]any:
		pick := a["full"]
		if !pyTruthy(pick) {
			pick = a["street"]
		}
		if text := pyText(pick, 300); text != "" {
			out = append(out, Entry{"address", text})
		}
	case string:
		out = append(out, Entry{"address", pyText(a, 300)})
	}
	// Halve every list and every string over 50 characters until the stored
	// JSON fits. Python loops forever when nothing can shrink; Go stops.
	for len(out.JSON()) > maxStoredBytes {
		changed := false
		for i, e := range out {
			switch v := e.Value.(type) {
			case []string:
				n := max(1, len(v)/2)
				if n < len(v) {
					changed = true
				}
				out[i].Value = v[:n]
			case string:
				if r := []rune(v); len(r) > 50 {
					out[i].Value = string(r[:len(r)/2])
					changed = true
				}
			}
		}
		if !changed {
			break
		}
	}
	return out
}

// DecodeItem decodes one Apify dataset item (or any JSON object) with numbers
// kept as text, so str() of a number can follow Python.
func DecodeItem(raw []byte) (map[string]any, error) {
	dec := json.NewDecoder(strings.NewReader(string(raw)))
	dec.UseNumber()
	var m map[string]any
	if err := dec.Decode(&m); err != nil {
		return nil, err
	}
	return m, nil
}
