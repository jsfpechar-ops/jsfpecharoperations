package onboarding

// Unit tests of the finish and try-it page data (brief 1601) and of the QR
// image, which the golden normalises to one token because the PNG encoders
// of Python and Go differ. html/template writes "+" of the data URI as
// "&#43;", which the browser reads back as "+".

import (
	"encoding/base64"
	"html"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
	"time"
)

func TestWizardReadyCardQR(t *testing.T) {
	g := wizardLoadGolden(t, "testdata/wizard_golden_finish.json")
	pool := testPool(t)
	wizardGoldenSeed(t, pool, g)
	mux := http.NewServeMux()
	RegisterWizard(mux, func(_ string, h http.HandlerFunc) http.Handler { return h }, pool, wizardGoldenEnv(g),
		func() time.Time { return wizardGoldenNow })
	var c *wizardGoldenCase
	for i := range g.Cases {
		if g.Cases[i].Name == "done_ready_celebrate" {
			c = &g.Cases[i]
		}
	}
	if c == nil {
		t.Fatal("no done_ready_celebrate case")
	}
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, wizardGoldenRequest(t, g, *c))
	m := regexp.MustCompile(`class="ready-card-qr" src="data:image/png;base64,([A-Za-z0-9+/=]+)"`).FindStringSubmatch(html.UnescapeString(rec.Body.String()))
	if rec.Code != http.StatusOK || m == nil {
		t.Fatalf("status %d, no QR image", rec.Code)
	}
	png, err := base64.StdEncoding.DecodeString(m[1])
	if err != nil || !strings.HasPrefix(string(png), "\x89PNG\r\n\x1a\n") {
		t.Fatalf("QR is not a PNG (%v)", err)
	}
}

func TestWizardFinishHelpers(t *testing.T) {
	v := &wizardView{Checklist: []ChecklistRow{{"property", "done"}, {"calendar", "skipped"}, {"police", "waiting"}, {"guest_link", "todo"}}}
	if m := v.MissingRow(); m == nil || m.Key != "police" {
		t.Fatalf("missing row %+v", m)
	}
	v.Checklist[2].Status = "not_needed"
	if m := v.MissingRow(); m == nil || m.Key != "guest_link" {
		t.Fatalf("missing row %+v", m)
	}
	v.Checklist = v.Checklist[:3]
	if m := v.MissingRow(); m != nil {
		t.Fatalf("missing row %+v", m)
	}
	for in, want := range map[string]string{"done": "done", "skipped": "skipped", "waiting": "waiting", "not_needed": "not_needed", "todo": "todo", "odd": "todo"} {
		if got := v.SummaryStatus(in); got != want {
			t.Errorf("status %q: %q", in, got)
		}
	}
	for in, want := range map[string]string{"Jana": "J", "[Your name]": "Y", "[[": "", "Žofie": "Ž"} {
		if got := (&wizardView{OperatorFirst: in}).OperatorMark(); got != want {
			t.Errorf("mark %q: %q", in, got)
		}
	}
	if got := (&wizardView{Apt: &wizardApt{}}).RehearsalHours(); got != 24 {
		t.Errorf("hours %d", got)
	}
	parts := (&wizardView{Lang: "en", Permalink: "https://app.example.test/l/x", Pin: "123456", OperatorFirst: "Jana", Apt: &wizardApt{InternalName: "Alfa"}}).DemoMessage()
	if len(parts) != 2 || !parts[1].Last || parts[0].Last {
		t.Fatalf("message parts %+v", parts)
	}
}
