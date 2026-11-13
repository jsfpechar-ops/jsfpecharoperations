package pages

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"math"
	"strconv"
	"strings"
)

// node is one decoded JSON value with object keys kept in order, so a
// rewrite of the payment_services setting keeps what Python's json.loads and
// json.dumps keep: every item's keys, in their order.
type node struct {
	kind  byte // 's' string, 'n' number, 'b' bool, 'z' null, 'a' array, 'o' object
	str   string
	num   string // the number literal as written
	b     bool
	items []*node
	keys  []string
	vals  []*node
}

// parseJSON is json.loads for a whole document. A duplicate key keeps its
// first position and its last value, as a Python dict does.
func parseJSON(raw string) (*node, error) {
	dec := json.NewDecoder(strings.NewReader(raw))
	dec.UseNumber()
	n, err := parseNode(dec)
	if err != nil {
		return nil, err
	}
	if _, err := dec.Token(); err != io.EOF {
		return nil, errors.New("trailing data")
	}
	return n, nil
}

func parseNode(dec *json.Decoder) (*node, error) {
	tok, err := dec.Token()
	if err != nil {
		return nil, err
	}
	switch v := tok.(type) {
	case json.Delim:
		switch v {
		case '[':
			n := &node{kind: 'a'}
			for dec.More() {
				item, err := parseNode(dec)
				if err != nil {
					return nil, err
				}
				n.items = append(n.items, item)
			}
			if _, err := dec.Token(); err != nil {
				return nil, err
			}
			return n, nil
		case '{':
			n := &node{kind: 'o'}
			for dec.More() {
				kt, err := dec.Token()
				if err != nil {
					return nil, err
				}
				key, ok := kt.(string)
				if !ok {
					return nil, errors.New("object key")
				}
				val, err := parseNode(dec)
				if err != nil {
					return nil, err
				}
				if i := n.index(key); i >= 0 {
					n.vals[i] = val
				} else {
					n.keys = append(n.keys, key)
					n.vals = append(n.vals, val)
				}
			}
			if _, err := dec.Token(); err != nil {
				return nil, err
			}
			return n, nil
		}
		return nil, errors.New("unexpected delimiter")
	case string:
		return &node{kind: 's', str: v}, nil
	case json.Number:
		return &node{kind: 'n', num: string(v)}, nil
	case bool:
		return &node{kind: 'b', b: v}, nil
	case nil:
		return &node{kind: 'z'}, nil
	}
	return nil, errors.New("unexpected token")
}

func (n *node) index(key string) int {
	for i, k := range n.keys {
		if k == key {
			return i
		}
	}
	return -1
}

// get is dict.get: the value under key, or nil.
func (n *node) get(key string) *node {
	if n == nil || n.kind != 'o' {
		return nil
	}
	if i := n.index(key); i >= 0 {
		return n.vals[i]
	}
	return nil
}

// isFloat reports whether the literal is a Python float (has . e or E).
func (n *node) isFloat() bool { return strings.ContainsAny(n.num, ".eE") }

// truthy is Python's bool() of the loaded value.
func (n *node) truthy() bool {
	if n == nil {
		return false
	}
	switch n.kind {
	case 's':
		return n.str != ""
	case 'n':
		if n.isFloat() {
			f, _ := strconv.ParseFloat(n.num, 64)
			return f != 0
		}
		return strings.Trim(n.num, "-0") != ""
	case 'b':
		return n.b
	case 'a':
		return len(n.items) > 0
	case 'o':
		return len(n.keys) > 0
	}
	return false
}

// text is what Jinja prints for the value: str() for scalars. A list or an
// object prints as its JSON (Python prints its repr; only hand-edited
// settings can hold one).
func (n *node) text() string {
	if n == nil {
		return "" // a missing key is Jinja's undefined
	}
	switch n.kind {
	case 's':
		return n.str
	case 'n':
		return pyNumber(n)
	case 'b':
		if n.b {
			return "True"
		}
		return "False"
	case 'z':
		return "None"
	}
	var b bytes.Buffer
	n.dump(&b)
	return b.String()
}

// dump writes json.dumps(value, ensure_ascii=False): ", " and ": "
// separators, non-ASCII kept, no HTML escaping.
func (n *node) dump(b *bytes.Buffer) {
	switch n.kind {
	case 's':
		dumpString(b, n.str)
	case 'n':
		b.WriteString(pyNumber(n))
	case 'b':
		if n.b {
			b.WriteString("true")
		} else {
			b.WriteString("false")
		}
	case 'z':
		b.WriteString("null")
	case 'a':
		b.WriteByte('[')
		for i, item := range n.items {
			if i > 0 {
				b.WriteString(", ")
			}
			item.dump(b)
		}
		b.WriteByte(']')
	case 'o':
		b.WriteByte('{')
		for i, k := range n.keys {
			if i > 0 {
				b.WriteString(", ")
			}
			dumpString(b, k)
			b.WriteString(": ")
			n.vals[i].dump(b)
		}
		b.WriteByte('}')
	}
}

// pyNumber is repr() of the loaded number: an int as its digits, a float
// in Python's shortest repr ("100.0", "1e+16", "1.5e-05").
func pyNumber(n *node) string {
	if !n.isFloat() {
		if i, err := strconv.ParseInt(n.num, 10, 64); err == nil {
			return strconv.FormatInt(i, 10)
		}
		neg := strings.HasPrefix(n.num, "-")
		digits := strings.TrimLeft(strings.TrimPrefix(n.num, "-"), "0")
		if digits == "" {
			return "0"
		}
		if neg {
			return "-" + digits
		}
		return digits
	}
	f, err := strconv.ParseFloat(n.num, 64)
	if err != nil || math.IsInf(f, 0) {
		if f < 0 {
			return "-Infinity"
		}
		return "Infinity"
	}
	return pyFloat(f)
}

func pyFloat(f float64) string {
	if f == 0 {
		if math.Signbit(f) {
			return "-0.0"
		}
		return "0.0"
	}
	s := strconv.FormatFloat(f, 'e', -1, 64) // d.ddde±XX
	mant, expText, _ := strings.Cut(s, "e")
	exp, _ := strconv.Atoi(expText)
	neg := strings.HasPrefix(mant, "-")
	digits := strings.Replace(strings.TrimPrefix(mant, "-"), ".", "", 1)
	sign := ""
	if neg {
		sign = "-"
	}
	if exp < -4 || exp >= 16 {
		m := digits[:1]
		if len(digits) > 1 {
			m += "." + digits[1:]
		}
		es := "+"
		if exp < 0 {
			es = "-"
			exp = -exp
		}
		e := strconv.Itoa(exp)
		if len(e) < 2 {
			e = "0" + e
		}
		return sign + m + "e" + es + e
	}
	if exp < 0 {
		return sign + "0." + strings.Repeat("0", -exp-1) + digits
	}
	if len(digits) <= exp+1 {
		return sign + digits + strings.Repeat("0", exp+1-len(digits)) + ".0"
	}
	return sign + digits[:exp+1] + "." + digits[exp+1:]
}

// dumpString is json.dumps of a str with ensure_ascii=False.
func dumpString(b *bytes.Buffer, s string) {
	const hexDigits = "0123456789abcdef"
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
				b.WriteString(`\u00`)
				b.WriteByte(hexDigits[r>>4])
				b.WriteByte(hexDigits[r&15])
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
}
