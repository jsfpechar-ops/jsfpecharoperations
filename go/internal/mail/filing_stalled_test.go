package mail

import (
	"strings"
	"testing"
)

func TestBuildFilingStalledCauses(t *testing.T) {
	url := "https://app.example.test/apartments/7?view=bookings"
	for _, cause := range []string{"setup", "auth", "manual", "failed", ""} {
		c, err := BuildFilingStalled("https://example.test", "en", "Byt 7", 36, cause, url, "")
		if err != nil {
			t.Fatalf("cause %q: %v", cause, err)
		}
		if c.Subject != "Guests not reported to the police: Byt 7" {
			t.Fatalf("cause %q: subject %q", cause, c.Subject)
		}
		reason := stalledCauses[cause]
		if cause == "" || !strings.Contains(c.Text, reason) {
			if !strings.Contains(c.Text, reason) {
				t.Fatalf("cause %q: text lacks reason", cause)
			}
		}
		if !strings.Contains(c.Text, "36") {
			t.Fatalf("cause %q: text lacks count", cause)
		}
		if strings.Contains(c.Text, "%(") || strings.Contains(c.HTML, "%(") {
			t.Fatalf("cause %q: unfilled placeholder", cause)
		}
	}
}

func TestBuildFilingStalledOperatorCopy(t *testing.T) {
	c, err := BuildFilingStalled("https://example.test", "en", "Byt 7", 36, "setup",
		"https://app.example.test/apartments/7?view=settings&section=reporting#ubyport", "jan")
	if err != nil {
		t.Fatal(err)
	}
	if c.Subject != "[Operator] Guests not reported: Byt 7 (jan)" {
		t.Fatalf("subject %q", c.Subject)
	}
	if !strings.Contains(c.Text, "Workspace: jan") {
		t.Fatalf("text lacks workspace fact")
	}
}

func TestBuildFilingStalledRejectsOtherLanguage(t *testing.T) {
	if _, err := BuildFilingStalled("https://example.test", "cs", "Byt 7", 1, "", "https://x.test/", ""); err == nil {
		t.Fatal("expected ErrLanguage for cs")
	}
}

func TestBuildFilingStalledUnknownCause(t *testing.T) {
	c, err := BuildFilingStalled("https://example.test", "en", "Byt 7", 3, "bogus", "https://x.test/", "")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(c.Text, strStalledCauseUnknown) {
		t.Fatal("unknown cause does not read as the unknown cause")
	}
}
