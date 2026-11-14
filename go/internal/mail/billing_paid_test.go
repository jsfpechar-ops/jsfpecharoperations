package mail

import (
	"strings"
	"testing"
)

// TestBuildBillingPaid pins mail_notify.build_billing_paid with fixed numbers.
func TestBuildBillingPaid(t *testing.T) {
	c := BuildBillingPaid("https://app.example.test", "https://www.example.test", "support@example.test", "UBY-2026-0042", 1190, "13.11.2026")
	if c.Subject != "Faktura UBY-2026-0042 je zaplacena" {
		t.Errorf("subject %q", c.Subject)
	}
	wantText := "Platbu 1 190 Kč za fakturu UBY-2026-0042 jsme přijali 13.11.2026. Faktura je označená jako zaplacená. Děkujeme.\n\n" +
		"Otevřít předplatné: https://app.example.test/predplatne\n\n--\nUbyHost\nDotazy: support@example.test"
	if c.Text != wantText {
		t.Errorf("text %q", c.Text)
	}
	if !strings.Contains(c.HTML, `<html lang="cs">`) || !strings.Contains(c.HTML, "https://app.example.test/predplatne") {
		t.Error("html lacks the Czech language tag or the link")
	}
}
