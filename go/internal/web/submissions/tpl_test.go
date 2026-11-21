package submissions

import "testing"

func TestGuestCountJSON(t *testing.T) {
	if got := guestCountJSON(""); got != 0 {
		t.Fatalf("empty: %d", got)
	}
	if got := guestCountJSON(`[1,2,3]`); got != 3 {
		t.Fatalf("array: %d", got)
	}
	if got := guestCountJSON(`not json`); got != 0 {
		t.Fatalf("invalid json should yield 0, got %d", got)
	}
}

func TestInitialRune(t *testing.T) {
	if got := initialRune("  chrome "); got != "C" {
		t.Fatalf("got %q", got)
	}
	if got := initialRune("čaj"); got != "Č" {
		t.Fatalf("unicode: got %q", got)
	}
	if got := initialRune(""); got != "?" {
		t.Fatalf("empty: got %q", got)
	}
}

func TestMaskIdentifier(t *testing.T) {
	if got := maskIdentifier("AB123456"); got != "•••456" {
		t.Fatalf("got %q", got)
	}
	if got := maskIdentifier("ab"); got != "•••" {
		t.Fatalf("short: got %q", got)
	}
	if got := maskIdentifier(""); got != "" {
		t.Fatalf("empty: got %q", got)
	}
}

func TestAcceptedState(t *testing.T) {
	for _, s := range []string{"ok", "ok_duplicate", "partial"} {
		if !acceptedState(s) {
			t.Fatalf("%q should count as accepted", s)
		}
	}
	for _, s := range []string{"error", "running", "failed", "transport_error"} {
		if acceptedState(s) {
			t.Fatalf("%q should not count as accepted", s)
		}
	}
}