package exports

import "testing"

// TestMaskIdentifier checks access.mask_identifier: three bullets and the
// last three characters, three bullets alone for a short value, "" for none.
func TestMaskIdentifier(t *testing.T) {
	for in, want := range map[string]string{
		"AB123456": "•••456", "abcd": "•••bcd", "abc": "•••", "a": "•••", "": "",
		"Žlutý": "•••utý",
	} {
		if got := maskIdentifier(in); got != want {
			t.Errorf("maskIdentifier(%q) = %q, want %q", in, got, want)
		}
	}
}
