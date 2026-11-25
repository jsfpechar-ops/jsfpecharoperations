package guest

import (
	"bytes"
	"strings"
	"testing"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/doorcodes"
)

// TestDoorCodeCardStates maps each doorcodes.Shown state to the card state
// Python shows: issued (PIN), failed, and every other state as preparing.
func TestDoorCodeCardStates(t *testing.T) {
	if got := doorCodeCardFrom(nil); got != nil {
		t.Fatalf("no door code: want nil card, got %+v", got)
	}
	cases := map[string]string{
		"issued":    "issued",
		"failed":    "failed",
		"preparing": "preparing",
		"waiting":   "preparing",
		"delayed":   "preparing",
	}
	for in, want := range cases {
		got := doorCodeCardFrom(&doorcodes.Shown{State: in})
		if got == nil || got.State != want {
			t.Errorf("state %q: want card %q, got %+v", in, want, got)
		}
	}
	issued := doorCodeCardFrom(&doorcodes.Shown{State: "issued", PIN: "4815", Checkin: "14:00", Checkout: "10:00", FirstUseBy: "15.06.2026 14:00"})
	if issued.PIN != "4815" || issued.Checkin != "14:00" || issued.Checkout != "10:00" || issued.FirstUseBy != "15.06.2026 14:00" {
		t.Errorf("issued fields not copied: %+v", issued)
	}
}

// TestDoorCodeCardRender renders the stay page with each state. The card is
// shown only once every guest is in (remaining <= 0), as in Python.
func TestDoorCodeCardRender(t *testing.T) {
	issued := &doorcodes.Shown{State: "issued", PIN: "4815", Checkin: "14:00", Checkout: "10:00", FirstUseBy: "15.06.2026 14:00"}
	cases := []struct {
		name      string
		shown     *doorcodes.Shown
		email     string
		remaining int
		want      []string
		wantNot   []string
	}{
		{name: "issued first use and sent", shown: issued, email: "a***@example.cz", want: []string{`id="door-code"`, "4815", "14:00", "15.06.2026 14:00", "We have also sent it to a***@example.cz."}},
		{name: "issued without first use or email", shown: &doorcodes.Shown{State: "issued", PIN: "4815", Checkin: "14:00", Checkout: "10:00"}, want: []string{"4815"}, wantNot: []string{"You must enter it on the lock", "We have also sent it"}},
		{name: "failed", shown: &doorcodes.Shown{State: "failed"}, want: []string{`id="door-code"`, "Your host will send you the door code."}, wantNot: []string{"4815"}},
		{name: "preparing", shown: &doorcodes.Shown{State: "preparing"}, want: []string{`id="door-code"`, "You will receive your door code by email."}, wantNot: []string{"4815"}},
		{name: "waiting shows preparing", shown: &doorcodes.Shown{State: "waiting"}, want: []string{"You will receive your door code by email."}},
		{name: "delayed shows preparing", shown: &doorcodes.Shown{State: "delayed"}, want: []string{"You will receive your door code by email."}},
		{name: "no door code hides card", shown: nil, want: nil, wantNot: []string{`id="door-code"`}},
		{name: "guests missing hides card", shown: issued, remaining: 1, wantNot: []string{`id="door-code"`, "4815"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			view := stayView{
				Page:             Page{Lang: "en"},
				StayFrom:         "2026-06-01",
				StayTo:           "2026-06-05",
				HasExpected:      true,
				Expected:         2,
				Filled:           2 - tc.remaining,
				HasRemaining:     true,
				Remaining:        tc.remaining,
				ClaimEmailMasked: tc.email,
				DoorCode:         doorCodeCardFrom(tc.shown),
			}
			var buf bytes.Buffer
			if err := staySet.ExecuteTemplate(&buf, "guest.base", view); err != nil {
				t.Fatalf("render: %v", err)
			}
			html := buf.String()
			for _, w := range tc.want {
				if !strings.Contains(html, w) {
					t.Errorf("want %q in page", w)
				}
			}
			for _, w := range tc.wantNot {
				if strings.Contains(html, w) {
					t.Errorf("did not want %q in page", w)
				}
			}
		})
	}
}
