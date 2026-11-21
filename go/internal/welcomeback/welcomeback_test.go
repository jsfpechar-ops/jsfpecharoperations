package welcomeback

import "testing"

func TestKeysFor(t *testing.T) {
	s, l := KeysFor(7)
	if s != "last_seen_7" || l != "welcome_back_7" {
		t.Fatalf("keys %q %q", s, l)
	}
}