package layout

import (
	"html/template"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"testing/fstest"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

func envOf(m map[string]string) func(string) string { return func(k string) string { return m[k] } }

func TestSafeHrefNeutralisesScripts(t *testing.T) {
	for _, bad := range []string{"javascript:alert(1)", " JaVa\tScRiPt:alert(1)", "data:text/html,x", "vbscript:x", "java\nscript:x"} {
		if got := safeHref(bad); got != unsafeHref {
			t.Errorf("safeHref(%q) = %q", bad, got)
		}
	}
	for in, want := range map[string]string{
		"/a?b=1&c=2": "/a?b=1&amp;c=2", "#x": "#x", "?q=1": "?q=1", "page.html": "page.html",
		"https://x.cz/a": "https://x.cz/a", "HTTP://x": "HTTP://x", "mailto:a@b.cz": "mailto:a@b.cz", "/x:y": "/x:y",
	} {
		if got := safeHref(in); got != want {
			t.Errorf("safeHref(%q) = %q, want %q", in, got, want)
		}
	}
	c := &reqCtx{lang: "en", layout: Strings}
	h, err := c.uiButton("x", "primary", map[string]any{"href": "javascript:alert(1)"})
	if err != nil || !strings.Contains(string(h), `href="#ZgotmplZ"`) {
		t.Fatalf("ui_button with a javascript: href = %s (%v)", h, err)
	}
	if h := c.rowOpen(template.HTML("javascript:x")); !strings.Contains(string(h), `href="#ZgotmplZ"`) {
		t.Fatalf("row_open = %s", h)
	}
}

func TestHavelGateAndLimits(t *testing.T) {
	env := map[string]string{"UBYHOST_AI_FEATURES": "leon, Havel", "UBYHOST_ANTHROPIC_API_KEY": "k"}
	if !havelOn(envOf(env), "a@b.cz") {
		t.Fatal("havel listed with a key must be on")
	}
	env["UBYHOST_AI_TEST_EMAILS"] = "Boss@x.cz"
	if havelOn(envOf(env), "a@b.cz") || !havelOn(envOf(env), " boss@X.cz ") {
		t.Fatal("test list not applied")
	}
	env["UBYHOST_AI_PROVIDER"] = "mistral"
	if havelOn(envOf(env), "boss@x.cz") {
		t.Fatal("mistral without its key must be off")
	}
	g := envOf(map[string]string{})
	for _, tc := range []struct {
		c     havelCounts
		scale int
		want  string
	}{
		{havelCounts{0, 0, 0, 0}, 1, ""}, {havelCounts{3, 0, 0, 0}, 1, "paused"}, {havelCounts{0, 5, 0, 0}, 1, "limit_burst"},
		{havelCounts{0, 0, 8, 8}, 1, "limit_week"}, {havelCounts{0, 0, 8, 8}, 5, ""}, {havelCounts{0, 0, 0, 15}, 1, "limit_month"},
		{havelCounts{0, 0, 0, 0}, 0, "limit_week"},
	} {
		if got := havelLimitState(g, tc.c, tc.scale); got != tc.want {
			t.Errorf("limit %v x%d = %q, want %q", tc.c, tc.scale, got, tc.want)
		}
	}
	for _, tc := range []struct {
		acc  billingRow
		on   bool
		want int
	}{
		{billingRow{}, true, 1}, {billingRow{Status: "paused"}, true, 0}, {billingRow{Status: "active", Plan: "max"}, true, 5},
		{billingRow{Status: "trialing", Plan: "max"}, true, 1}, {billingRow{Status: "active", Plan: "max"}, false, 1},
	} {
		if got := aiMultiplier(tc.on, tc.acc); got != tc.want {
			t.Errorf("multiplier %+v = %d", tc.acc, got)
		}
	}
	// Wednesday 2026-11-11 00:00:30 Prague: the week began on Monday.
	week, month := havelWindows(time.Date(2026, 11, 10, 23, 0, 30, 0, time.UTC))
	if week != 2*86400+31 || month != 10*86400+31 {
		t.Fatalf("windows %d %d", week, month)
	}
	if got := orderedHavelTopics("apartments")[0].ID; got != "guest_link" {
		t.Fatalf("first topic %q", got)
	}
}

func TestBillingBanner(t *testing.T) {
	today := time.Date(2026, 11, 13, 0, 0, 0, 0, time.UTC)
	trial := billingRow{Status: "trialing", TrialEndsAt: "2026-11-16T08:00:00"}
	if b := billingBanner(true, trial, today); b == nil || b.Kind != "trial" || !b.Warning || b.Date != "16.11.2026" {
		t.Fatalf("trial %+v", b)
	}
	trial.TrialEndsAt = "2026-11-17"
	if b := billingBanner(true, trial, today); b == nil || b.Warning {
		t.Fatalf("trial 4 days %+v", b)
	}
	if billingBanner(false, trial, today) != nil || billingBanner(true, billingRow{}, today) != nil {
		t.Fatal("billing off or no row must show nothing")
	}
	trial.Plan = "standard"
	if billingBanner(true, trial, today) != nil {
		t.Fatal("a trial with a plan shows nothing")
	}
	if b := billingBanner(true, billingRow{Status: "canceling", PeriodEnd: "2026-12-31T00:00:00"}, today); b == nil || b.Warning || b.Date != "31.12.2026" {
		t.Fatalf("canceling %+v", b)
	}
	if b := billingBanner(true, billingRow{Status: "paused"}, today); b == nil || !b.Warning || b.Date != "" {
		t.Fatalf("paused %+v", b)
	}
	if billingBanner(true, billingRow{Status: "active"}, today) != nil {
		t.Fatal("active shows nothing")
	}
}

func TestSecurityPromptRules(t *testing.T) {
	now := time.Date(2026, 11, 13, 9, 0, 0, 0, time.UTC)
	sh := shell{SignedIn: true, AccountIsWorkspace: true, SignupAt: "2026-11-01T00:00:00"}
	if p := securityPrompt(sh, "/reservations", now, true); p == nil || !*p {
		t.Fatal("an old unsecured account gets the prompt")
	}
	for _, path := range []string{"/settings", "/settings/x", "/account/2fa/setup", "/account/accept"} {
		if securityPrompt(sh, path, now, true) != nil {
			t.Errorf("prompt on %s", path)
		}
	}
	sh.SignupAt = "2026-11-08T10:00:00"
	if securityPrompt(sh, "/", now, false) != nil {
		t.Fatal("a signup under 7 days gets no prompt")
	}
	sh.SignupAt = ""
	if securityPrompt(sh, "/", now, false) == nil {
		t.Fatal("no signup date: prompt")
	}
	sh.AccountIsWorkspace = false
	if securityPrompt(sh, "/", now, false) != nil {
		t.Fatal("an admin in a host's workspace gets no prompt")
	}
	sh.AccountIsWorkspace, sh.TwoFactorDone = true, true
	if securityPrompt(sh, "/", now, false) != nil {
		t.Fatal("prompted or TOTP: no prompt")
	}
}

func TestAlertPresentation(t *testing.T) {
	x := alertText{lang: "en", now: time.Date(2026, 11, 13, 9, 0, 0, 0, time.UTC)}
	five := int64(5)
	stored := alertRow{ID: 1, Level: "critical", Kind: "submission_rejected", ApartmentID: &five,
		Message: "log copy", Params: `{"property": "Flat", "count": 2}`}
	if c := present(stored, nil, x); c.Title != "Flat: the police did not accept 2 guest record(s)." || c.ActionHref != "/apartments/5" {
		t.Fatalf("stored card %+v", c)
	}
	stored.Params = ""
	stored.Kind = "apartment_setup"
	if c := present(stored, nil, x); c.Title != "log copy" {
		t.Fatalf("placeholders without params must keep the stored text: %+v", c)
	}
	if p := storedParams(`{"a": 3, "b": 1.5, "c": true, "d": null}`); p["a"] != int64(3) || p["b"] != 1.5 || p["c"] != "True" || p["d"] != nil {
		t.Fatalf("params %#v", p)
	}
	rid := int64(9)
	stay := &alertStay{AlertStay: calendar.AlertStay{ID: 9, DateFrom: "2026-11-12", DateTo: "2026-11-14"}, Property: "Flat"}
	unreadable := map[int64]calendar.AlertProgress{9: {Unreadable: true}}
	a := alertRow{ID: 2, Level: "critical", Kind: "deadline", ReservationID: &rid, Detail: "stored", Stay: stay}
	if c := present(a, unreadable, x); c.Reason != "stored" || !strings.HasPrefix(c.Title, "Flat · 12.11.2026") {
		t.Fatalf("unreadable stay card %+v", c)
	}
	inc := alertRow{ID: 3, Level: "warning", Kind: "guest_incomplete_checkin", ReservationID: &rid, Stay: stay}
	exp := 1
	done := map[int64]calendar.AlertProgress{9: {Filled: 1, Expected: &exp, Status: "ready"}}
	if cards := presentMany([]alertRow{inc}, done, x); len(cards) != 0 {
		t.Fatal("a complete stay drops its incomplete-checkin card")
	}
	if cards := presentMany([]alertRow{inc, a}, unreadable, x); len(cards) != 1 || cards[0].Kind != "deadline" {
		t.Fatalf("one card per stay, most severe wins: %+v", cards)
	}
	rows := make([]alertRow, 0, 20)
	for i := 0; i < 20; i++ {
		lvl := "warning"
		if i < 3 {
			lvl = "critical"
		}
		rows = append(rows, alertRow{ID: int64(i), Level: lvl})
	}
	if kept, more := shellSlice(rows); len(kept) != 15 || more != 5 {
		t.Fatalf("slice %d %d", len(kept), more)
	}
}

func TestPageFuncsAndHelpers(t *testing.T) {
	fsys := fstest.MapFS{"p.html": {Data: []byte(`{{define "p"}}{{range seq 3}}{{.}}{{end}}|{{range seq 2 4}}{{.}}{{end}}|{{add 2 3}}|{{sub 2 3}}|{{default "d" .Missing}}|{{default "d" .Zero}}|{{shout "hi"}}{{end}}`)}}
	if _, err := ParseFuncs(nil, template.FuncMap{"t": func() string { return "" }}, fsys, "p.html"); err == nil {
		t.Fatal("a page func named t was accepted")
	}
	tpl, err := ParseFuncs(nil, template.FuncMap{"shout": strings.ToUpper}, fsys, "p.html")
	if err != nil {
		t.Fatal(err)
	}
	w := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/x", nil)
	if err := render(w, r, Env{Getenv: getenv, Now: time.Now()}, shell{}, "tok", Page{Title: "T"}, tpl, "p", map[string]any{"Zero": 0}); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(w.Body.String(), "012|23|5|-1|d|0|HI") {
		t.Fatal("helpers or page func did not render")
	}
}

func TestLangAndSlotTitle(t *testing.T) {
	r := httptest.NewRequest(http.MethodGet, "/reservations", nil)
	if Lang(r, &session.Host{}) != "en" || Lang(r, nil) != "cs" {
		t.Fatal("Lang fallbacks: host en, visitor cs")
	}
	r = httptest.NewRequest(http.MethodGet, "/cenik?lang=vi", nil)
	if Lang(r, nil) != "en" {
		t.Fatal("public pages are en or cs")
	}
	fsys := fstest.MapFS{"p.html": {Data: []byte(`{{define "p"}}x{{end}}{{define "p.title"}}Stay <em>&amp; more</em>{{end}}`)}}
	tpl := MustParse(nil, fsys, "p.html")
	w := httptest.NewRecorder()
	if err := render(w, httptest.NewRequest(http.MethodGet, "/x", nil), Env{Getenv: getenv, Now: time.Now()}, shell{}, "tok", Page{}, tpl, "p", nil); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(w.Body.String(), "<title>Stay &amp; more</title>") {
		t.Fatal("empty Page.Title must use the slot text")
	}
}

func TestCSRFCookieLivesThirtyDays(t *testing.T) {
	_, cookie, err := csrfToken(httptest.NewRequest(http.MethodGet, "/", nil), "s", getenv, time.Now())
	if err != nil || cookie.MaxAge != 30*24*60*60 {
		t.Fatalf("csrf cookie max age %v %v", cookie, err)
	}
}
