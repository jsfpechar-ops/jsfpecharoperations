package hostweb

import (
	"os"
	"regexp"
	"testing"
)

// TestReadOnlyOpenMatchesPython checks the Go exemption list against
// App/app/auth.py, so the two cannot drift apart silently.
func TestReadOnlyOpenMatchesPython(t *testing.T) {
	raw, err := os.ReadFile("../../../App/app/auth.py")
	if err != nil {
		t.Fatalf("read auth.py: %v", err)
	}
	src := string(raw)

	tupleRE := regexp.MustCompile(`_READ_ONLY_OPEN_PREFIXES = \(([^)]*)\)`)
	m := tupleRE.FindStringSubmatch(src)
	if m == nil {
		t.Fatal("_READ_ONLY_OPEN_PREFIXES not found in auth.py")
	}
	var pyPrefixes []string
	for _, q := range regexp.MustCompile(`"([^"]*)"`).FindAllStringSubmatch(m[1], -1) {
		pyPrefixes = append(pyPrefixes, q[1])
	}
	if len(pyPrefixes) != len(readOnlyOpenPrefixes) {
		t.Fatalf("prefixes: auth.py has %v, Go has %v", pyPrefixes, readOnlyOpenPrefixes)
	}
	for i := range pyPrefixes {
		if pyPrefixes[i] != readOnlyOpenPrefixes[i] {
			t.Fatalf("prefix %d: auth.py %q, Go %q", i, pyPrefixes[i], readOnlyOpenPrefixes[i])
		}
	}

	pathRE := regexp.MustCompile(`_READ_ONLY_OPEN_PATHS = re\.compile\(\s*r"([^"]+)"`)
	pm := pathRE.FindStringSubmatch(src)
	if pm == nil {
		t.Fatal("_READ_ONLY_OPEN_PATHS not found in auth.py")
	}
	if pm[1] != readOnlyOpenPaths.String() {
		t.Fatalf("paths regexp: auth.py %q, Go %q", pm[1], readOnlyOpenPaths.String())
	}
}

func TestReadOnlyOpen(t *testing.T) {
	cases := []struct {
		path string
		want bool
	}{
		{"/predplatne", true},
		{"/predplatne/obnovit", true},
		{"/logout", true},
		{"/account/logout-all", true},
		{"/settings/privacy/ad-consent", true},
		{"/exports/x", true},
		{"/reservations/submit-ready", true},
		{"/reservations/12/submit", true},
		{"/guests/7/resend", true},
		{"/reservations/12", false},
		{"/reservations/x/submit", false},
		{"/guests/7", false},
		{"/apartments", false},
		{"/admin/incidents", false},
		{"/", false},
	}
	for _, c := range cases {
		if got := ReadOnlyOpen(c.path); got != c.want {
			t.Errorf("ReadOnlyOpen(%q) = %v, want %v", c.path, got, c.want)
		}
	}
}
