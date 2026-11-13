package layout

import (
	"fmt"
	"html/template"
)

// args holds a macro call's arguments by parameter name, the way Jinja binds
// positional and keyword arguments.
type args struct {
	macro string
	vals  map[string]any
}

// bind binds a call: positional values fill params in order, and a trailing
// map[string]any (from kv) gives keyword values. "caller" is always accepted
// as a keyword: it stands in for the Jinja call block.
func bind(macro string, params []string, in []any) (args, error) {
	a := args{macro: macro, vals: map[string]any{}}
	if n := len(in); n > 0 {
		if kw, ok := in[n-1].(map[string]any); ok {
			in = in[:n-1]
			for k, v := range kw {
				if !hasParam(params, k) && k != "caller" {
					return a, fmt.Errorf("%s: unknown argument %q", macro, k)
				}
				a.vals[k] = v
			}
		}
	}
	if len(in) > len(params) {
		return a, fmt.Errorf("%s: %d positional arguments, at most %d", macro, len(in), len(params))
	}
	for i, v := range in {
		if _, dup := a.vals[params[i]]; dup {
			return a, fmt.Errorf("%s: %q given twice", macro, params[i])
		}
		a.vals[params[i]] = v
	}
	return a, nil
}

func hasParam(params []string, k string) bool {
	for _, p := range params {
		if p == k {
			return true
		}
	}
	return false
}

func (a args) has(k string) bool { _, ok := a.vals[k]; return ok }

// v is the raw value, or def when the argument was not given.
func (a args) v(k string, def any) any {
	if x, ok := a.vals[k]; ok {
		return x
	}
	return def
}

// s is the argument as Python's str(), def when missing.
func (a args) s(k, def string) string {
	if x, ok := a.vals[k]; ok {
		return pyStr(x)
	}
	return def
}

// e is the argument escaped for HTML ("{{ x }}"), def (escaped) when missing.
func (a args) e(k, def string) string {
	if x, ok := a.vals[k]; ok {
		return esc(x)
	}
	return escText(def)
}

// b is the argument's truth, def when missing.
func (a args) b(k string, def bool) bool {
	if x, ok := a.vals[k]; ok {
		return truthy(x)
	}
	return def
}

// raw is a "| safe" argument, "" when missing.
func (a args) raw(k string) string {
	if x, ok := a.vals[k]; ok {
		return safe(x)
	}
	return ""
}

// kv builds the keyword map: kv "href" "/x" "primary" true.
func kv(pairs ...any) (map[string]any, error) {
	if len(pairs)%2 != 0 {
		return nil, fmt.Errorf("kv: odd number of arguments")
	}
	m := make(map[string]any, len(pairs)/2)
	for i := 0; i < len(pairs); i += 2 {
		k, ok := pairs[i].(string)
		if !ok {
			return nil, fmt.Errorf("kv: key %v is not a string", pairs[i])
		}
		m[k] = pairs[i+1]
	}
	return m, nil
}

func html(s string) template.HTML { return template.HTML(s) }
