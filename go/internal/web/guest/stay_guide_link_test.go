package guest

import (
	"bytes"
	"strings"
	"testing"
)

// TestStayGuideLink: the guide link shows only while the host's guide is live (guest.py _guide_is_live).
func TestStayGuideLink(t *testing.T) {
	const link = `href="/l/tok/5/guide?lang=en" data-guide-link`
	for _, live := range []bool{true, false} {
		view := stayView{
			Page:      Page{Lang: "en"},
			StayFrom:  "2026-06-01",
			StayTo:    "2026-06-05",
			Base:      "/l/tok/5",
			LangQ:     "?lang=en",
			GuideLive: live,
		}
		var buf bytes.Buffer
		if err := staySet.ExecuteTemplate(&buf, "guest.base", view); err != nil {
			t.Fatalf("render: %v", err)
		}
		if got := strings.Contains(buf.String(), link); got != live {
			t.Errorf("live=%v: guide link present = %v", live, got)
		}
	}
}
