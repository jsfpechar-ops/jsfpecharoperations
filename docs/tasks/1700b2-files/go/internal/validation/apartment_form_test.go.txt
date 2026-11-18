package validation

import "testing"

// TestApartmentFormNormalisers: expected values written by hand from
// validation.py (normalise_zip, PURPOSE_CODES, normalise_reachback_days).
func TestApartmentFormNormalisers(t *testing.T) {
	if got := NormaliseZip(" 120 00x١"); got != "12000١" {
		t.Errorf("NormaliseZip = %q", got)
	}
	for code, want := range map[string]bool{"10": true, "99": true, "93": true, "20": false, "": false, "1": false} {
		if IsPurposeCode(code) != want {
			t.Errorf("IsPurposeCode(%q) = %v", code, !want)
		}
	}
	if got := Upper("aakß"); got != "AAKSS" {
		t.Errorf("Upper = %q", got)
	}
	n := func(v int64) *int64 { return &v }
	for _, c := range []struct {
		in   *int64
		want int64
	}{{nil, 365}, {n(0), 365}, {n(-4), 365}, {n(1), 1}, {n(30), 30}, {n(3650), 3650}, {n(9999), 3650}} {
		if got := NormaliseReachbackDays(c.in); got != c.want {
			t.Errorf("NormaliseReachbackDays(%v) = %d, want %d", c.in, got, c.want)
		}
	}
}
