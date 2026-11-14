package ai

import (
	"context"
	"net/url"
	"strings"
	"testing"
)

func TestGuideLeonUTC(t *testing.T) {
	for in, want := range map[string]string{"": "", "2026-11-13T10:05:09+00:00": "2026-11-13 10:05 UTC", "short": "short UTC"} {
		if got := guideLeonUTC(in); got != want {
			t.Errorf("guideLeonUTC(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestGuideLeonRoutes(t *testing.T) {
	pool := guideTestPool(t)
	owner := guideSeedUser(t, pool, "host1", "host")
	stranger := guideSeedUser(t, pool, "stranger", "host")
	apt := guideSeedApartment(t, pool, owner, "Flat")
	id := itoa64(apt)
	page := "/apartments/" + id + "/leon"
	on := map[string]string{"UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "k"}
	mux := guideTestMux(pool, on)
	ctx := context.Background()
	state := func() (bool, string, string) {
		var enabled bool
		var version, by string
		if err := pool.QueryRow(ctx, `SELECT leon_enabled <> 0, COALESCE(leon_terms_version, ''), COALESCE(leon_terms_accepted_by::text, '') FROM apartment WHERE id = $1`, apt).Scan(&enabled, &version, &by); err != nil {
			t.Fatal(err)
		}
		return enabled, version, by
	}

	// switched off: the page sends the host to the wizard
	if rec := guideTestDo(t, mux, "GET", page, owner, nil); rec.Code != 303 || location(rec) != page+"/setup" {
		t.Errorf("off: %d %q", rec.Code, location(rec))
	}
	// Leon not offered (feature off): 404 for the page and for "on", but "off" still works
	offMux := guideTestMux(pool, nil)
	if rec := guideTestDo(t, offMux, "GET", page, owner, nil); rec.Code != 404 {
		t.Errorf("not offered: %d", rec.Code)
	}
	if rec := guideTestDo(t, offMux, "POST", page, owner, url.Values{"action": {"on"}, "terms": {"1"}}); rec.Code != 404 {
		t.Errorf("on while not offered: %d", rec.Code)
	}
	// on without the tick: an error, nothing written; from the wizard the error goes to the wizard step
	rec := guideTestDo(t, mux, "POST", page, owner, url.Values{"action": {"on"}})
	if !strings.HasPrefix(location(rec), page+"?err=") {
		t.Errorf("no tick: %q", location(rec))
	}
	rec = guideTestDo(t, mux, "POST", page, owner, url.Values{"action": {"on"}, "next": {"setup"}})
	if !strings.HasPrefix(location(rec), page+"/setup/switch_on?err=") {
		t.Errorf("no tick from the wizard: %q", location(rec))
	}
	if enabled, _, _ := state(); enabled {
		t.Fatal("Leon was switched on without the terms")
	}
	// on with the tick: version and who accepted are stored, one audit row
	rec = guideTestDo(t, mux, "POST", page, owner, url.Values{"action": {"on"}, "terms": {"1"}})
	if rec.Code != 303 || !strings.HasPrefix(location(rec), page+"?msg=") {
		t.Errorf("on: %d %q", rec.Code, location(rec))
	}
	if enabled, version, by := state(); !enabled || version != guideLeonTermsVersion || by != itoa64(owner) {
		t.Errorf("state after on = %v %q %q", enabled, version, by)
	}
	if n := guideTestCount(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'leon_terms_accepted' AND detail = $1 AND actor = 'host1' AND owner_user_id = $2`,
		"apartment="+id+" version="+guideLeonTermsVersion, owner); n != 1 {
		t.Errorf("%d audit rows for the terms", n)
	}
	rec = guideTestDo(t, mux, "POST", page, owner, url.Values{"action": {"on"}, "terms": {"1"}, "next": {"setup"}})
	if !strings.HasPrefix(location(rec), page+"/setup?msg=") {
		t.Errorf("on from the wizard: %q", location(rec))
	}
	// the page: waiting until the guide is live, with who accepted and when
	body := guideTestDo(t, mux, "GET", page, owner, nil)
	if body.Code != 200 {
		t.Fatalf("on page: %d %s", body.Code, body.Body.String())
	}
	for _, want := range []string{"2026-11-13 10:00 UTC", "host1@example.test", guideLeonTermsVersion, `name="action" value="off"`, `href="/guide#leon-terms"`, "settings-lane"} {
		if !strings.Contains(body.Body.String(), want) {
			t.Errorf("on page lacks %q", want)
		}
	}
	// old terms: back to the wizard
	guideTestExec(t, pool, `UPDATE apartment SET leon_terms_version = '2020-01-01' WHERE id = $1`, apt)
	if rec := guideTestDo(t, mux, "GET", page, owner, nil); location(rec) != page+"/setup" {
		t.Errorf("old terms: %q", location(rec))
	}
	// a stranger cannot read or change the switch
	if rec := guideTestDo(t, mux, "GET", page, stranger, nil); rec.Code != 404 {
		t.Errorf("stranger page: %d", rec.Code)
	}
	if rec := guideTestDo(t, mux, "POST", page, stranger, url.Values{"action": {"off"}}); rec.Code != 404 {
		t.Errorf("stranger off: %d", rec.Code)
	}
	if enabled, _, _ := state(); !enabled {
		t.Fatal("a stranger switched Leon off")
	}
	// off works even while Leon is not offered, and is audited
	rec = guideTestDo(t, offMux, "POST", page, owner, url.Values{"action": {"off"}})
	if !strings.HasPrefix(location(rec), page+"?msg=") {
		t.Errorf("off: %q", location(rec))
	}
	if enabled, _, _ := state(); enabled {
		t.Error("Leon is still on")
	}
	if n := guideTestCount(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'leon_switched_off' AND detail = $1`, "apartment="+id); n != 1 {
		t.Errorf("%d audit rows for off", n)
	}
	// anything else just returns to the page
	if rec := guideTestDo(t, mux, "POST", page, owner, url.Values{"action": {"other"}}); location(rec) != page {
		t.Errorf("unknown action: %q", location(rec))
	}
}

// The wizard-less branches of the template (state off and terms) are not
// reachable through the route, which redirects to the wizard; they must still render.
func TestGuideLeonTemplateOffAndTermsRender(t *testing.T) {
	pool := guideTestPool(t)
	owner := guideSeedUser(t, pool, "host1", "host")
	apt := guideSeedApartment(t, pool, owner, "Flat")
	s := guideTestServer(pool, nil)
	for _, state := range []string{"off", "terms"} {
		req := guideTestRequest(t, owner, "/apartments/"+itoa64(apt)+"/leon")
		rec := guideTestRecorder()
		q := &guideReq{host: guideTestHost(owner), apt: apt, lang: "en", at: guideTestNow, r: req}
		a := &guideApartment{ID: apt, InternalName: "Flat"}
		data := guideLeonData{Apartment: a, State: state, Live: false,
			Warnings:  []string{"leon_page.warn1", "leon_page.warn2", "leon_page.warn3", "leon_page.warn4", "leon_page.warn5", "leon_page.warn6"},
			StateCard: guideValueCard{Label: "Leon", Value: state}}
		s.render(rec, q, "guide_leon", layoutPage("Leon"), 200, data)
		body := rec.Body.String()
		for _, want := range []string{`name="terms" value="1" required`, `name="action" value="on"`, "f1-list", `href="/apartments/` + itoa64(apt) + `/guide"`} {
			if !strings.Contains(body, want) {
				t.Errorf("state %s: page lacks %q (status %d)", state, want, rec.Code)
			}
		}
		if state == "terms" && !strings.Contains(body, "ui-banner-attention") {
			t.Error("the terms state shows no banner")
		}
	}
}
