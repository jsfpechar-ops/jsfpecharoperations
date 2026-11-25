package guest

import (
	"strings"
	"testing"
)

// TestAssignedLastSentLine: the assigned page shows the day of the last claim mail (guest.py assigned, claim_last_sent_at) as DD.MM.YYYY.
func TestAssignedLastSentLine(t *testing.T) {
	v := assignedView{
		Page:           Page{Lang: "en"},
		StayFrom:       "2026-06-01",
		StayTo:         "2026-06-05",
		DeclaredGuests: 1,
		ClaimLastSent:  "2026-11-20",
	}
	if html := renderAssignedForTest(t, v); !strings.Contains(html, "20.11.2026") {
		t.Errorf("last-sent day 20.11.2026 not rendered")
	}
}
