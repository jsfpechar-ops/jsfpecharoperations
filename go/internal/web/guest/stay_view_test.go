package guest

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func renderStaySetForTest(t *testing.T, name string, view any) string {
	t.Helper()
	var buf bytes.Buffer
	set := staySet
	if name == "assigned" {
		set = assignedSet
	}
	if err := set.ExecuteTemplate(&buf, "guest.base", view); err != nil {
		t.Fatal(err)
	}
	out := buf.String()
	if dir := os.Getenv("STAY_SHOT_DIR"); dir != "" {
		_ = os.WriteFile(filepath.Join(dir, name+".html"), buf.Bytes(), 0o644)
	}
	return out
}

func assertHas(t *testing.T, out string, wants ...string) {
	t.Helper()
	for _, w := range wants {
		if !strings.Contains(out, w) {
			t.Errorf("missing %q", w)
		}
	}
}

func TestStayTemplatesRender(t *testing.T) {
	base := Page{Lang: "en", Token: "tok", Facility: "Test house", CSRFToken: "csrf"}
	mine := stayPerson{Index: 1, ID: 1, Mine: true, Complete: true, Name: "Anna Test",
		Summary: &stayPersonSummary{Nationality: "Czechia", BirthDate: "1990-01-02", Purpose: "Tourism", Residence: "Praha"}}
	other := stayPerson{Index: 2, ID: 2}
	claimed := stayView{Page: base, StayFrom: "2026-12-01", StayTo: "2026-12-03", HasExpected: true, Expected: 2,
		Filled: 1, HasRemaining: true, Remaining: 1, Percent: 50, CanRaiseParty: true, Base: "/l/tok/1",
		LangQ: "?lang=en", PartyURL: "/l/tok/1/party?lang=en", AnotherURL: "/l/tok/1/another?lang=en",
		NewURL: "/l/tok/1/new?lang=en", People: []stayPerson{mine, other}, Mine: []stayPerson{mine}, Others: []stayPerson{other}}
	out := renderStaySetForTest(t, "stay-claimed", claimed)
	assertHas(t, out, `class="g-bar"`, `class="g-still-missing"`, `href="/l/tok/1/new?lang=en"`,
		`Anna Test`, `Person 2`, `href="/l/tok/1/edit/1?lang=en"`, `g-stay-summary`)

	stepper := claimed
	stepper.HasExpected, stepper.HasRemaining = false, false
	out = renderStaySetForTest(t, "stay-stepper", stepper)
	assertHas(t, out, `data-guest-stepper`, `name="party_size"`, `action="/l/tok/1/party?lang=en"`)

	done := claimed
	done.Filled, done.Remaining = 2, 0
	out = renderStaySetForTest(t, "stay-done", done)
	assertHas(t, out, `g-big-ok`, `action="/l/tok/1/another?lang=en"`)
	if strings.Contains(out, `g-still-missing`) {
		t.Error("done page shows still-missing")
	}

	assigned := assignedView{Page: base, StayFrom: "2026-12-01", StayTo: "2026-12-03", EmailMasked: "a***@x.cz",
		DeclaredGuests: 2, ActionURL: "/l/tok/1/party?lang=en", NotMineURL: "/l/tok?lang=en"}
	out = renderStaySetForTest(t, "assigned", assigned)
	assertHas(t, out, `g-assigned-stay`, `name="resend" value="1"`, `name="party_size" value="2"`)
}
