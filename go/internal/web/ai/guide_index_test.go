package ai

import (
	"context"
	"strings"
	"testing"
	"time"
)

func TestGuideLeonStateAndTruthy(t *testing.T) {
	a := &guideApartment{}
	cases := []struct {
		enabled bool
		version string
		live    bool
		want    string
	}{
		{false, "", false, "off"}, {false, guideLeonTermsVersion, true, "off"}, {true, "2026-01-01", true, "terms"},
		{true, guideLeonTermsVersion, true, "on"}, {true, guideLeonTermsVersion, false, "waiting"},
	}
	for _, c := range cases {
		a.LeonEnabled, a.LeonTermsVersion = c.enabled, c.version
		if got := guideLeonState(a, c.live); got != c.want {
			t.Errorf("guideLeonState(%v, %q, %v) = %q, want %q", c.enabled, c.version, c.live, got, c.want)
		}
	}
	for v, want := range map[string]bool{"1": true, "TRUE": true, "Yes": true, "0": false, "": false, "on": false} {
		if guideTruthy(v) != want {
			t.Errorf("guideTruthy(%q) = %v", v, !want)
		}
	}
}

func TestGuideMonthStartUsesPrague(t *testing.T) {
	s := guideTestServer(nil, nil)
	for at, want := range map[time.Time]string{
		time.Date(2026, 11, 13, 10, 0, 0, 0, time.UTC):  "2026-11-01",
		time.Date(2026, 10, 31, 23, 30, 0, 0, time.UTC): "2026-11-01", // already November in Prague
		time.Date(2026, 11, 30, 22, 59, 0, 0, time.UTC): "2026-11-01",
	} {
		at := at
		s.now = func() time.Time { return at }
		if got := s.monthStart(); got != want {
			t.Errorf("monthStart at %v = %q, want %q", at, got, want)
		}
	}
}

func TestGuideIndexPage(t *testing.T) {
	w := newGuideCardWorld(t)
	ctx := context.Background()
	// a property without its default cards gets them when the page is opened, and a QR token
	fresh := guideSeedApartment(t, w.s.pool, w.host, "Fresh")
	rec := guideTestDo(t, w.mux, "GET", "/apartments/"+itoa64(fresh)+"/guide", w.host, nil)
	if rec.Code != 200 {
		t.Fatalf("index: %d %s", rec.Code, rec.Body.String())
	}
	if n := guideTestCount(t, w.s.pool, `SELECT COUNT(*) FROM guide_item WHERE apartment_id = $1`, fresh); n != int64(len(guideDefaultKinds)) {
		t.Errorf("%d cards after the first visit, want %d", n, len(guideDefaultKinds))
	}
	if tok, _ := w.s.currentToken(ctx, fresh); len(tok) != 32 {
		t.Errorf("no QR token after the first visit: %q", tok)
	}
	body := rec.Body.String()
	for _, want := range []string{
		`id="topic-arrival"`, `id="topic-emergency"`, `id="add-card"`, `id="import"`, `action="/apartments/` + itoa64(fresh) + `/guide/cards"`,
		"ui-banner-attention", `href="/apartments/` + itoa64(fresh) + `/guide/quick"`, `/guide/questions"`, `class="ph-hide"`,
		`<tr class="ui-row clickable-row" data-href="/apartments/` + itoa64(fresh) + `/guide/`,
	} {
		if !strings.Contains(body, want) {
			t.Errorf("index lacks %q", want)
		}
	}
	if strings.Contains(body, `id="leon"`) || strings.Contains(body, `action="/apartments/`+itoa64(fresh)+`/guide/import"`) {
		t.Error("Leon or the import form shows although both are off")
	}
	if rec := guideTestDo(t, w.mux, "GET", "/apartments/"+itoa64(fresh)+"/guide", w.stranger, nil); rec.Code != 404 {
		t.Errorf("another account: %d", rec.Code)
	}
	if rec := guideTestDo(t, w.mux, "GET", "/apartments/"+itoa64(fresh)+"/guide", 0, nil); rec.Code != 303 {
		t.Errorf("signed out: %d", rec.Code)
	}
}

func TestGuideIndexSwitchesAndCounts(t *testing.T) {
	pool := guideTestPool(t)
	owner := guideSeedUser(t, pool, "host1", "host")
	apt := guideSeedApartment(t, pool, owner, "Flat")
	now := guideStamp(guideTestNow)
	path := "/apartments/" + itoa64(apt) + "/guide"
	on := map[string]string{"UBYHOST_APIFY_TOKEN": "t", "UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "k"}
	mux := guideTestMux(pool, on)
	s := guideTestServer(pool, on)

	body := guideTestDo(t, mux, "GET", path, owner, nil).Body.String()
	for _, want := range []string{`action="` + path + `/import"`, `name="booking_url"`, `name="airbnb_url"`, `id="leon"`, `href="/apartments/` + itoa64(apt) + `/leon"`} {
		if !strings.Contains(body, want) {
			t.Errorf("with Apify and Leon on, the page lacks %q", want)
		}
	}
	if strings.Index(body, `id="import"`) > strings.Index(body, `id="topic-arrival"`) {
		t.Error("the import section should come first while imports are left")
	}
	// a booking import is queued: one source left, no form while it runs, the section stays first
	guideTestExec(t, pool, `INSERT INTO guide_import (apartment_id, source, url, status, created_at) VALUES ($1, 'booking', 'https://www.booking.com/hotel/cz/x.html', 'queued', $2)`, apt, now)
	body = guideTestDo(t, mux, "GET", path, owner, nil).Body.String()
	if strings.Contains(body, `name="booking_url"`) || strings.Contains(body, `<form method="post" action="`+path+`/import"`) {
		t.Error("the import form shows while an import runs")
	}
	if !strings.Contains(body, "2026-11-13") {
		t.Error("the import row has no date")
	}
	// done: the form is back, for Airbnb only; both used: no form, the section moves below the cards
	guideTestExec(t, pool, `UPDATE guide_import SET status = 'used'`)
	body = guideTestDo(t, mux, "GET", path, owner, nil).Body.String()
	if strings.Contains(body, `name="booking_url"`) || !strings.Contains(body, `name="airbnb_url"`) {
		t.Error("only the Airbnb field should show after a Booking import")
	}
	guideTestExec(t, pool, `INSERT INTO guide_import (apartment_id, source, url, status, error, created_at) VALUES ($1, 'airbnb', 'https://www.airbnb.com/rooms/1', 'failed', 'merge:x', $2)`, apt, now)
	imports, _ := s.imports(context.Background(), apt)
	if len(imports) != 2 || !imports[0].MergeFailed || imports[0].CreatedDay != "2026-11-13" {
		t.Errorf("imports = %+v", imports)
	}
	if left, _ := s.usedSources(context.Background(), apt); left["airbnb"] || !left["booking"] {
		t.Errorf("a failed run must not use a source up: %v", left)
	}

	// Leon: needs the feature, a key, the test list and a billing account that is not paused
	for name, c := range map[string]struct {
		env  map[string]string
		want bool
	}{
		"on":                     {on, true},
		"no key":                 {map[string]string{"UBYHOST_AI_FEATURES": "leon"}, false},
		"feature not listed":     {map[string]string{"UBYHOST_AI_FEATURES": "havel", "UBYHOST_ANTHROPIC_API_KEY": "k"}, false},
		"owner not on test list": {map[string]string{"UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "k", "UBYHOST_AI_TEST_EMAILS": "other@example.test"}, false},
		"owner on test list":     {map[string]string{"UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "k", "UBYHOST_AI_TEST_EMAILS": "A@x.test, HOST1@example.test"}, true},
	} {
		got, err := guideTestServer(pool, c.env).leonOffered(context.Background(), apt)
		if err != nil || got != c.want {
			t.Errorf("leonOffered %s = %v, %v; want %v", name, got, err, c.want)
		}
	}
	guideTestExec(t, pool, `INSERT INTO billing_account (owner_user_id, status, updated_at) VALUES ($1, 'paused', $2)`, owner, now)
	if got, _ := s.leonOffered(context.Background(), apt); !got {
		t.Error("a paused account loses Leon only while billing is on")
	}
	billing := guideTestServer(pool, map[string]string{"UBYHOST_BILLING_ENABLED": "1", "UBYHOST_AI_FEATURES": "leon", "UBYHOST_ANTHROPIC_API_KEY": "k"})
	if got, _ := billing.leonOffered(context.Background(), apt); got {
		t.Error("a paused account still has Leon while billing is on")
	}

	// counts: open questions, Leon replies this month, cached guest languages
	guideTestExec(t, pool, `INSERT INTO ai_usage (day, feature, key, requests) VALUES ('2026-11-02', 'leon', $1, 5), ('2026-10-31', 'leon', $1, 9), ('2026-11-02', 'leon', '999', 7)`, itoa64(apt))
	u, err := s.usage(context.Background(), apt, "2026-11-01")
	if err != nil || u.Leon != 5 {
		t.Errorf("usage = %+v, %v", u, err)
	}
	var itemID int64
	_ = pool.QueryRow(context.Background(), `INSERT INTO guide_item (apartment_id, topic, kind, created_at, updated_at) VALUES ($1, 'arrival', 'custom', 'x', 'x') RETURNING id`, apt).Scan(&itemID)
	guideTestExec(t, pool, `INSERT INTO guide_translation (item_id, lang, source_hash, same, created_at) VALUES ($1, 'de', 'h', 0, 'x'), ($1, 'cs', 'h', 0, 'x'), ($1, 'fr', 'h', 1, 'x')`, itemID)
	if u, _ = s.usage(context.Background(), apt, "2026-11-01"); strings.Join(u.Languages, ",") != "cs,de" {
		t.Errorf("languages = %v", u.Languages)
	}
	body = guideTestDo(t, mux, "GET", path, owner, nil).Body.String()
	if !strings.Contains(body, "data-guide-usage") || !strings.Contains(body, "CS, DE") {
		t.Error("the usage line is missing")
	}
}
