package ai

import (
	"context"
	"net/url"
	"strings"
	"testing"
)

func TestGuideFactTableMatchesCatalog(t *testing.T) {
	if len(guideFactTable) != 22 {
		t.Fatalf("%d facts, want 22", len(guideFactTable))
	}
	var raw struct {
		Steps []string `json:"steps"`
	}
	if err := jsonUnmarshal(guideFactsJSON, &raw); err != nil {
		t.Fatal(err)
	}
	if strings.Join(raw.Steps, ",") != strings.Join(guideSteps, ",") {
		t.Errorf("steps %v vs %v", raw.Steps, guideSteps)
	}
	for _, f := range guideFactTable {
		if !guideIn(guideDefaultKinds, f.Card) || !guideIn(guideSteps, f.Step) {
			t.Errorf("fact %+v names an unknown step or card", f)
		}
		var keys []string
		switch f.Kind {
		case "yesno":
			keys = []string{"guide_fact_" + f.Name + "_yes", "guide_fact_" + f.Name + "_no"}
		default:
			keys = []string{"guide_fact_" + f.Name}
		}
		for _, k := range keys {
			for _, lang := range []string{"en", "cs"} {
				if _, ok := guideGuestStrings[lang][k]; !ok {
					t.Errorf("no %s text for %s", lang, k)
				}
			}
		}
	}
}

func TestGuideCleanFact(t *testing.T) {
	cases := []struct{ kind, in, want string }{
		{"yesno", " yes ", "yes"}, {"yesno", "no", "no"}, {"yesno", "", ""}, {"yesno", "maybe", ""},
		{"time", "09:30", "09:30"}, {"time", "24:00", ""}, {"time", "9:30", ""}, {"time", "12:60", ""}, {"time", " 23:59 ", "23:59"},
		{"range", "22:00-07:00", "22:00-07:00"}, {"range", "22:00-", ""}, {"range", "-", ""}, {"range", "22:00", ""},
	}
	for _, c := range cases {
		if got := guideCleanFact(c.kind, c.in); got != c.want {
			t.Errorf("guideCleanFact(%s, %q) = %q, want %q", c.kind, c.in, got, c.want)
		}
	}
}

func TestGuideQuickRoutes(t *testing.T) {
	w := newGuideCardWorld(t)
	ctx := context.Background()
	base := w.path("/quick")

	rec := guideTestDo(t, w.mux, "GET", base, w.host, nil)
	if rec.Code != 303 || !strings.HasPrefix(location(rec), base+"/times") {
		t.Errorf("quick start: %d %q", rec.Code, location(rec))
	}
	page := guideTestDo(t, w.mux, "GET", base+"/times", w.host, nil)
	if page.Code != 200 {
		t.Fatalf("step page: %d %s", page.Code, page.Body.String())
	}
	body := page.Body.String()
	for _, want := range []string{`data-quick-fact="late_checkout"`, `name="checkin_from"`, `type="time"`, `name="skip" value="1"`, `<input type="radio" name="luggage" value="" checked>`} {
		if !strings.Contains(body, want) {
			t.Errorf("step page lacks %q", want)
		}
	}
	if rec := guideTestDo(t, w.mux, "GET", base+"/nope", w.host, nil); rec.Code != 404 {
		t.Errorf("unknown step: %d", rec.Code)
	}
	if rec := guideTestDo(t, w.mux, "POST", base+"/nope", w.host, nil); rec.Code != 404 {
		t.Errorf("unknown step save: %d", rec.Code)
	}

	// save the first step: valid answers are stored, invalid ones are not, the step is seen
	rec = guideTestDo(t, w.mux, "POST", base+"/times", w.host, url.Values{
		"checkin_from": {"15:00"}, "checkout_by": {"25:00"}, "late_checkout": {"yes"}, "luggage": {""},
	})
	if rec.Code != 303 || location(rec) != base+"/rules" {
		t.Errorf("save times: %d %q", rec.Code, location(rec))
	}
	got, _ := w.s.answers(ctx, w.apt)
	if got["checkin_from"] != "15:00" || got["late_checkout"] != "yes" || got["step.times"] != "seen" {
		t.Errorf("answers = %v", got)
	}
	if _, ok := got["checkout_by"]; ok {
		t.Error("an invalid time was stored")
	}
	// a blank answer removes the fact again
	guideTestDo(t, w.mux, "POST", base+"/times", w.host, url.Values{"late_checkout": {""}, "checkin_from": {"16:00"}})
	got, _ = w.s.answers(ctx, w.apt)
	if _, ok := got["late_checkout"]; ok || got["checkin_from"] != "16:00" {
		t.Errorf("answers after the second save = %v", got)
	}
	// ranges, and "skip" changes nothing but marks the step seen
	rec = guideTestDo(t, w.mux, "POST", base+"/rules", w.host, url.Values{"quiet_hours_from": {"22:00"}, "quiet_hours_to": {"07:00"}, "pets": {"no"}})
	if location(rec) != base+"/access" {
		t.Errorf("save rules: %q", location(rec))
	}
	rec = guideTestDo(t, w.mux, "POST", base+"/access", w.host, url.Values{"skip": {"1"}, "parking": {"yes"}})
	got, _ = w.s.answers(ctx, w.apt)
	if got["quiet_hours"] != "22:00-07:00" || got["step.access"] != "seen" {
		t.Errorf("answers = %v", got)
	}
	if _, ok := got["parking"]; ok {
		t.Error("a skipped step stored an answer")
	}
	// the last step goes to done, and quick now leads there
	guideTestDo(t, w.mux, "POST", base+"/kitchen", w.host, url.Values{"skip": {"1"}})
	rec = guideTestDo(t, w.mux, "POST", base+"/comfort", w.host, url.Values{"safe": {"yes"}})
	if location(rec) != base+"/done" {
		t.Errorf("last step Location = %q", location(rec))
	}
	if rec := guideTestDo(t, w.mux, "GET", base, w.host, nil); location(rec) != base+"/done" {
		t.Errorf("quick after all steps: %q", location(rec))
	}

	// the done page lists what guests now read, in the host's language; the guide is not live yet
	done := guideTestDo(t, w.mux, "GET", base+"/done", w.host, nil)
	if done.Code != 200 {
		t.Fatalf("done: %d %s", done.Code, done.Body.String())
	}
	d := done.Body.String()
	for _, want := range []string{"Check-in from 16:00.", "Quiet hours from 22:00 to 07:00.", "ui-banner-attention", `id="quick-answers"`, `id="quick-missing"`} {
		if !strings.Contains(d, want) {
			t.Errorf("done page lacks %q", want)
		}
	}
	// every ownership rule applies
	for _, path := range []string{base, base + "/times", base + "/done"} {
		if rec := guideTestDo(t, w.mux, "GET", path, w.stranger, nil); rec.Code != 404 {
			t.Errorf("another account on %s: %d", path, rec.Code)
		}
	}
	if rec := guideTestDo(t, w.mux, "POST", base+"/times", w.stranger, url.Values{"checkin_from": {"01:00"}}); rec.Code != 404 {
		t.Errorf("another account saving: %d", rec.Code)
	}
	if got, _ := w.s.answers(ctx, w.apt); got["checkin_from"] != "16:00" {
		t.Error("another account changed the answers")
	}
}

func TestGuideFactLinesCzechAndVietnamese(t *testing.T) {
	w := newGuideCardWorld(t)
	ctx := context.Background()
	guideTestExec(t, w.s.pool, `INSERT INTO guide_fact (apartment_id, fact, value, updated_at) VALUES ($1, 'checkin_from', '15:00', 'x'), ($1, 'pets', 'yes', 'x')`, w.apt)
	cs, _ := w.s.factLines(ctx, w.apt, "cs")
	en, _ := w.s.factLines(ctx, w.apt, "en")
	vi, _ := w.s.factLines(ctx, w.apt, "vi")
	if len(cs["checkin"]) != 1 || !strings.Contains(cs["checkin"][0], "15:00") || cs["checkin"][0] == en["checkin"][0] {
		t.Errorf("cs = %v en = %v", cs, en)
	}
	if strings.Join(vi["house_rules"], "") != strings.Join(en["house_rules"], "") {
		t.Errorf("vi should read English: %v vs %v", vi, en)
	}
}
