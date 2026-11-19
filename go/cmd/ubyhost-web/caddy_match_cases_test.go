package main

import (
	"encoding/json"
	"os"
	"path"
	"strings"
	"testing"
)

// caddyPathMatch is caddyhttp.MatchPath for one pattern without "%" escapes
// (Caddy v2, modules/caddyhttp/matchers.go): both sides lower-cased; "*" alone
// matches all; "*x*", "*x" and "x*" are substring, suffix and prefix matches
// when those are the only stars; any other pattern goes to path.Match.
func caddyPathMatch(pattern, p string) bool {
	pattern, p = strings.ToLower(pattern), strings.ToLower(p)
	if pattern == "*" {
		return true
	}
	stars := strings.Count(pattern, "*")
	if stars == 2 && strings.HasPrefix(pattern, "*") && strings.HasSuffix(pattern, "*") {
		return strings.Contains(p, pattern[1:len(pattern)-1])
	}
	if stars == 1 && strings.HasPrefix(pattern, "*") {
		return strings.HasSuffix(p, pattern[1:])
	}
	if stars == 1 && strings.HasSuffix(pattern, "*") {
		return strings.HasPrefix(p, pattern[:len(pattern)-1])
	}
	ok, _ := path.Match(pattern, p)
	return ok
}

// The table scripts/go_parity_check.py and App/tests/go_stack.py are tested
// against (App/tests/test_1864_caddy_match.py) must hold for Caddy's own rule.
func TestCaddyMatchCases(t *testing.T) {
	raw, err := os.ReadFile("../../../scripts/caddy_match_cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases [][3]any
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) < 20 {
		t.Fatalf("%d cases, want at least 20", len(cases))
	}
	for _, c := range cases {
		entry, sample, want := c[0].(string), c[1].(string), c[2].(bool)
		if got := caddyPathMatch(entry, sample); got != want {
			t.Errorf("%s vs %s: Caddy gives %v, table says %v", entry, sample, got, want)
		}
	}
}
