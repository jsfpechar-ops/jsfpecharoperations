package guest

import (
	"bytes"
	"strings"
	"testing"
)

// renderAssignedForTest renders guest/assigned.html through the handler's template set.
func renderAssignedForTest(t *testing.T, v assignedView) string {
	t.Helper()
	var buf bytes.Buffer
	if err := assignedSet.ExecuteTemplate(&buf, "guest.base", v); err != nil {
		t.Fatalf("render: %v", err)
	}
	return buf.String()
}

// TestAssignedTurnstileWidget: Python assigned.html draws the widget and loads
// api.js only when require_turnstile and turnstile_site_key are both set. The
// resend form keeps its hidden field and submit button, so it works without JS.
func TestAssignedTurnstileWidget(t *testing.T) {
	const widget = `<div class="cf-turnstile" data-sitekey="site-key" data-action="guest_claim"></div>`
	const script = "challenges.cloudflare.com/turnstile/v0/api.js"
	cases := []struct {
		name     string
		required bool
		key      string
		want     bool
	}{
		{"required with key", true, "site-key", true},
		{"not required (local, or Turnstile off)", false, "site-key", false},
		{"required without key", true, "", false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			v := assignedView{
				Page:             Page{Lang: "en"},
				StayFrom:         "2026-06-01",
				StayTo:           "2026-06-05",
				DeclaredGuests:   1,
				RequireTurnstile: tc.required,
				TurnstileSiteKey: tc.key,
			}
			html := renderAssignedForTest(t, v)
			if got := strings.Contains(html, widget); got != tc.want {
				t.Errorf("widget present = %v, want %v", got, tc.want)
			}
			if got := strings.Contains(html, script); got != tc.want {
				t.Errorf("api.js present = %v, want %v", got, tc.want)
			}
			if !strings.Contains(html, `name="resend" value="1"`) || !strings.Contains(html, `type="submit"`) {
				t.Error("resend form lost its hidden field or submit button")
			}
		})
	}
}
