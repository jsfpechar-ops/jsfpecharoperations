package mailnotify

import (
	"strings"
	"testing"
)

func TestClaimMailGolden(t *testing.T) {
	old := guestEnabled
	SetGuestLanguages("en,cs,de,es,fr,uk")
	defer func() { guestEnabled = old }()
	for _, lang := range []string{"en", "cs", "de", "es", "fr", "uk"} {
		for _, resend := range []bool{false, true} {
			got := BuildClaim("https://example.test", ClaimInput{Lang: lang, PropertyName: "Stay & home", Dates: "20.06.2026 – 22.06.2026", Link: "https://example.test/l/token/1/claim#c={{claim_secret}}", Resend: resend, Host: &Host{Name: "Host", Email: "host@example.test"}})
			if got.Subject == "" || !strings.Contains(got.Text, "Stay & home") || !strings.Contains(got.Text, "{{claim_secret}}") || !strings.Contains(got.HTML, "{{claim_secret}}") || !strings.Contains(got.HTML, "&amp;") {
				t.Fatalf("claim mail incomplete lang=%s resend=%v", lang, resend)
			}
		}
	}
	open := BuildClaim("https://example.test", ClaimInput{Lang: "en", PropertyName: "Stay", Dates: "20.06.2026", Link: "https://example.test/claim#c={{claim_secret}}"})
	done := BuildClaim("https://example.test", ClaimInput{Lang: "en", PropertyName: "Stay", Dates: "20.06.2026", Link: "https://example.test/claim#c={{claim_secret}}", Resend: true, StayComplete: true})
	if !strings.Contains(open.Text, "You will enter the details") || !strings.Contains(done.Text, "Everyone is already registered") {
		t.Fatal("completed-stay variation mismatch")
	}
}
