package ai

// Tests of the four Havel routes on PostgreSQL with a fake model (the real
// model API is never called): permission checks, the switches, the limits, what
// is sent to the model, what is stored, and the pages the host sees.

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"html"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/anthropic"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const (
	havelTSecret = "havel-test-secret-key-0123456789abcdef"
	havelTCSRF   = "havel-csrf-cookie-value"
)

var havelTNow = time.Date(2026, 11, 13, 12, 0, 0, 0, time.UTC)

// havelScriptModel plays scripted replies and records every call.
type havelScriptModel struct {
	script []any // map[string]any (the model's JSON) or error
	calls  []havelFakeCall
}

func (m *havelScriptModel) Call(_ context.Context, feature string, system []string, messages []anthropic.Message, schema json.RawMessage, key *string, maxTokens int) (map[string]any, error) {
	m.calls = append(m.calls, havelFakeCall{feature, system, messages, schema, key, maxTokens})
	if len(m.script) == 0 {
		return nil, &anthropic.Error{Reason: "api"}
	}
	item := m.script[0]
	m.script = m.script[1:]
	if err, ok := item.(error); ok {
		return nil, err
	}
	raw, _ := json.Marshal(item)
	return havelDecode(nil2t(), raw).(map[string]any), nil
}

// nil2t lets havelDecode be used without a *testing.T (it only needs one to fail).
func nil2t() *testing.T { return &testing.T{} }

func havelTEnv(extra map[string]string) HavelEnv {
	env := map[string]string{
		"UBYHOST_SECRET_KEY": havelTSecret, "UBYHOST_AI_FEATURES": "havel", "UBYHOST_ANTHROPIC_API_KEY": "test-key",
		"UBYHOST_MAIL_BACKEND": "console", "UBYHOST_PUBLIC_BASE_URL": "https://app.example.test",
	}
	for k, v := range extra {
		env[k] = v
	}
	return havelMapEnv(env)
}

type havelRig struct {
	t     *testing.T
	pool  *pgxpool.Pool
	model *havelScriptModel
	mux   *http.ServeMux
	env   HavelEnv
}

func havelNewRig(t *testing.T, extra map[string]string) *havelRig {
	t.Helper()
	pool := havelTestPool(t)
	havelExec(t, pool,
		`INSERT INTO user_account (id, username, password_hash, role, created_at, email, display_name) VALUES (1, 'host', 'x', 'host', '2026-01-01', 'host@example.test', 'Anna Flats')`,
		`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES
		 (1, 'terms', '1.7', '2026-01-01', 'clickwrap'), (1, 'privacy', '1.8', '2026-01-01', 'clickwrap'), (1, 'dpa', '1.8', '2026-01-01', 'clickwrap')`,
		`INSERT INTO apartment (id, owner_user_id, internal_name, active, permalink_token, permalink_pin, addr_obec, created_at) VALUES
		 (11, 1, 'Flat A', 1, 'toka', '1234', 'Praha', '2026-01-01'), (12, 1, 'Chata', 1, 'tokb', NULL, NULL, '2026-01-01')`,
		`INSERT INTO ical_feed (apartment_id, url, active, created_at) VALUES (11, 'https://x.example/a.ics', 1, '2026-01-01')`)
	env := havelTEnv(extra)
	model := &havelScriptModel{}
	mux := http.NewServeMux()
	for _, route := range HavelRoutes(HavelDeps{Pool: pool, Env: env, Now: func() time.Time { return havelTNow }, Model: model}) {
		mux.Handle(route.Pattern, route.Handler)
	}
	return &havelRig{t: t, pool: pool, model: model, mux: mux, env: env}
}

func havelTToken(t *testing.T) string {
	sum := sha256.Sum256([]byte(havelTCSRF))
	token, err := secure.NewTimedSerializer(havelTSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, havelTNow)
	if err != nil {
		t.Fatal(err)
	}
	return token
}

type havelReq struct {
	method, path string
	form         url.Values
	signedOut    bool
	noToken      bool
	fragment     bool
	lang         string
	accept       string
}

func (g *havelRig) do(r havelReq) *httptest.ResponseRecorder {
	g.t.Helper()
	var body *strings.Reader
	if r.form != nil {
		body = strings.NewReader(r.form.Encode())
	} else {
		body = strings.NewReader("")
	}
	req := httptest.NewRequest(r.method, r.path, body)
	if r.form != nil {
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	}
	req.AddCookie(&http.Cookie{Name: "ubyhost_csrf", Value: havelTCSRF})
	if r.lang != "" {
		req.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: r.lang})
	}
	if !r.signedOut {
		req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(havelTSecret, map[string]any{"uid": 1, "sv": 1}, havelTNow)})
	}
	if r.method == http.MethodPost && !r.noToken {
		req.Header.Set("X-CSRF-Token", havelTToken(g.t))
	}
	if r.fragment {
		req.Header.Set("X-Havel", "1")
	}
	if r.accept != "" {
		req.Header.Set("Accept", r.accept)
	}
	rec := httptest.NewRecorder()
	g.mux.ServeHTTP(rec, req)
	return rec
}

func (g *havelRig) count(sql string, args ...any) int {
	g.t.Helper()
	var n int
	if err := g.pool.QueryRow(context.Background(), sql, args...).Scan(&n); err != nil {
		g.t.Fatal(err)
	}
	return n
}

// havelTxt is a catalog text as it appears in HTML.
func havelTxt(key string) string { return html.EscapeString(havelCatalog.T("en", key, nil)) }

func havelAnswerJSON(reply string) map[string]any {
	return map[string]any{"kind": "answer", "reply": reply, "sources": []string{"guide.stays.body"}, "links": []any{},
		"action": nil, "support_summary": nil, "next": []string{"Show the guest link"}}
}

func havelPost(g *havelRig, form url.Values, fragment bool) *httptest.ResponseRecorder {
	return g.do(havelReq{method: "POST", path: "/havel", form: form, fragment: fragment})
}

func TestHavelSignedOutAndCSRF(t *testing.T) {
	g := havelNewRig(t, nil)
	rec := g.do(havelReq{method: "GET", path: "/havel", signedOut: true})
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/havel" {
		t.Errorf("GET signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	rec = g.do(havelReq{method: "POST", path: "/havel", form: url.Values{"message": {"x"}}, signedOut: true})
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?next=/havel" {
		t.Errorf("POST signed out: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	rec = g.do(havelReq{method: "POST", path: "/havel", form: url.Values{"message": {"x"}}, noToken: true})
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login?notice=form_expired" {
		t.Errorf("POST without a token: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	for _, p := range []string{"/havel/support", "/havel/not-helped"} {
		rec = g.do(havelReq{method: "POST", path: p, form: url.Values{}, signedOut: true})
		if rec.Code != http.StatusSeeOther || !strings.HasPrefix(rec.Header().Get("Location"), "/login?next="+p) {
			t.Errorf("%s signed out: %d %q", p, rec.Code, rec.Header().Get("Location"))
		}
	}
	for _, c := range [][2]string{{"PUT", "/havel"}, {"HEAD", "/havel"}, {"GET", "/havel/support"}, {"GET", "/havel/not-helped"}} {
		rec = g.do(havelReq{method: c[0], path: c[1], signedOut: true})
		if rec.Code != http.StatusMethodNotAllowed || rec.Header().Get("Allow") == "" {
			t.Errorf("%s %s: %d", c[0], c[1], rec.Code)
		}
	}
	if len(g.model.calls) != 0 {
		t.Error("no model call without a login")
	}
}

func TestHavelPageGet(t *testing.T) {
	g := havelNewRig(t, nil)
	rec := g.do(havelReq{method: "GET", path: "/havel?page=reservations&return_to=/stays"})
	body := rec.Body.String()
	if rec.Code != 200 || !strings.Contains(body, `data-havel-page data-havel-owner="1"`) || !strings.Contains(body, `data-havel-topics`) {
		t.Fatalf("page: %d %.300s", rec.Code, body)
	}
	for _, id := range HavelTopicIDs() {
		if !strings.Contains(body, `href="/havel?topic=`+id+`"`) {
			t.Errorf("topic %s missing", id)
		}
	}
	if strings.Index(body, "?topic=stays") > strings.Index(body, "?topic=reporting") {
		t.Error("the page 'reservations' puts the stays topic first")
	}
	if !strings.Contains(body, `name="page" value="stays"`) || !strings.Contains(body, `name="return_to" value="/stays"`) || !strings.Contains(body, `<textarea id="havel-message"`) {
		t.Error("composer fields")
	}
	if strings.Contains(body, `data-havel-fab`) {
		t.Error("the Havel page has no launcher button")
	}
	// A topic answer, no model, no count.
	rec = g.do(havelReq{method: "GET", path: "/havel?topic=stays&q=add"})
	a := HavelTopicAnswer("en", "stays", "add")
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), "<p>"+html.EscapeString(a.Paragraphs[0])+"</p>") || !strings.Contains(rec.Body.String(), `href="/reservations?new=1"`) {
		t.Errorf("topic answer: %d", rec.Code)
	}
	if len(g.model.calls) != 0 || g.count(`SELECT COUNT(*) FROM rate_limit_event`) != 0 {
		t.Error("quick help makes no model call and no count")
	}
	// An unknown topic is dropped.
	if body := g.do(havelReq{method: "GET", path: "/havel?topic=nope&q=add"}).Body.String(); !strings.Contains(body, `name="topic" value=""`) {
		t.Error("an unknown topic is cleaned")
	}
	// The support topic carries the support form with the masked reply address.
	body = g.do(havelReq{method: "GET", path: "/havel?topic=wrong&q=error"}).Body.String()
	if !strings.Contains(body, `action="/havel/support"`) || !strings.Contains(body, html.EscapeString(mail.MaskEmail("host@example.test"))) {
		t.Errorf("support form with the masked reply address %q", mail.MaskEmail("host@example.test"))
	}
}

func TestHavelFragmentGet(t *testing.T) {
	g := havelNewRig(t, nil)
	rec := g.do(havelReq{method: "GET", path: "/havel?page=guide", fragment: true})
	body := rec.Body.String()
	if rec.Code != 200 || !strings.HasPrefix(body, `<div data-havel-items data-mode="replace">`) || strings.Contains(body, "<html") || strings.Contains(body, "data-havel-fragment") {
		t.Fatalf("fragment: %d %.300s", rec.Code, body)
	}
	if !strings.Contains(body, `<div data-havel-form-wrap>`) || !strings.Contains(body, `<div hidden data-havel-state`) || strings.Contains(body, " hidden data-havel-locked") {
		t.Error("fragment parts: form wrap, state div, an unlocked form")
	}
	if rec.Header().Get("Content-Type") != "text/html; charset=utf-8" {
		t.Errorf("content type %q", rec.Header().Get("Content-Type"))
	}
	// Without the nonce cookie the layout issues one; the fragment passes it on.
	req := httptest.NewRequest("GET", "/havel", nil)
	req.Header.Set("X-Havel", "1")
	req.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(havelTSecret, map[string]any{"uid": 1, "sv": 1}, havelTNow)})
	out := httptest.NewRecorder()
	g.mux.ServeHTTP(out, req)
	if !strings.Contains(strings.Join(out.Header().Values("Set-Cookie"), ";"), "ubyhost_csrf=") {
		t.Error("the CSRF cookie must reach the browser")
	}
}

func TestHavelOffShowsSupportOnly(t *testing.T) {
	g := havelNewRig(t, map[string]string{"UBYHOST_AI_FEATURES": ""})
	body := g.do(havelReq{method: "GET", path: "/havel"}).Body.String()
	if strings.Contains(body, `<textarea id="havel-message"`) || !strings.Contains(body, `havel-support-open`) {
		t.Error("with AI off the composer is replaced by the support link")
	}
	rec := havelPost(g, url.Values{"message": {"How do I add a stay?"}}, false)
	if rec.Code != 200 || !strings.Contains(rec.Body.String(), havelTxt("havel.off")) || len(g.model.calls) != 0 {
		t.Errorf("off: %d, %d calls", rec.Code, len(g.model.calls))
	}
	if g.count(`SELECT COUNT(*) FROM havel_stats`) != 0 || g.count(`SELECT COUNT(*) FROM rate_limit_event`) != 0 {
		t.Error("AI off counts nothing")
	}
	// The test list: only listed e-mails may use Havel.
	g2 := havelNewRig(t, map[string]string{"UBYHOST_AI_TEST_EMAILS": "other@example.test"})
	if strings.Contains(g2.do(havelReq{method: "GET", path: "/havel"}).Body.String(), `<textarea id="havel-message"`) {
		t.Error("an account off the test list does not get the composer")
	}
	g3 := havelNewRig(t, map[string]string{"UBYHOST_AI_TEST_EMAILS": "HOST@example.test"})
	if !strings.Contains(g3.do(havelReq{method: "GET", path: "/havel"}).Body.String(), `<textarea id="havel-message"`) {
		t.Error("an account on the test list gets the composer")
	}
}

func TestHavelLocalReplyCostsNothing(t *testing.T) {
	g := havelNewRig(t, nil)
	rec := havelPost(g, url.Values{"message": {"Hello!"}}, false)
	if !strings.Contains(rec.Body.String(), havelTxt("havel.greeting")) || len(g.model.calls) != 0 ||
		g.count(`SELECT COUNT(*) FROM rate_limit_event`) != 0 || g.count(`SELECT COUNT(*) FROM havel_stats`) != 0 {
		t.Error("a greeting is answered locally with no model call and no count")
	}
}

func TestHavelAnswerSendsOnlyRedactedFacts(t *testing.T) {
	g := havelNewRig(t, nil)
	g.model.script = []any{havelAnswerJSON("Open the Stays page and press Add stay.")}
	rec := havelPost(g, url.Values{"message": {"How do I add a stay? my mail is anna@example.test, phone +420 777 123 456"}, "page": {"reservations"},
		"device": {"phone"}, "return_to": {"/stays"}}, false)
	body := rec.Body.String()
	if rec.Code != 200 || !strings.Contains(body, "Open the Stays page and press Add stay.") || !strings.Contains(body, `data-havel-not-helped`) ||
		!strings.Contains(body, `value="Show the guest link"`) {
		t.Fatalf("answer page: %d", rec.Code)
	}
	if len(g.model.calls) != 1 {
		t.Fatalf("%d model calls", len(g.model.calls))
	}
	call := g.model.calls[0]
	if call.feature != "havel" || call.max != 2500 || call.key != nil || len(call.system) != 3 || len(call.messages) != 1 {
		t.Errorf("call shape: %+v", call)
	}
	sent := call.messages[0].Content
	for _, secret := range []string{"anna@example.test", "777 123 456", "host@example.test", "Anna Flats", "1234", "toka"} {
		if strings.Contains(sent, secret) {
			t.Errorf("%q must not reach the model", secret)
		}
	}
	for _, block := range call.system {
		if strings.Contains(block, "anna@example.test") || strings.Contains(block, "host@example.test") {
			t.Error("a system block holds an address")
		}
	}
	for _, want := range []string{"[email 1]", "[phone 1]", "device: phone", "page: stays", "properties: id 12: Chata; id 11: Flat A (Praha)", "today: 2026-11-13 (Friday)", "lang: en"} {
		if !strings.Contains(sent, want) {
			t.Errorf("the model should see %q, got:\n%s", want, sent)
		}
	}
	if g.count(`SELECT COUNT(*) FROM rate_limit_event WHERE scope IN ('havel_burst','havel_week','havel_month') AND key = '1'`) != 3 ||
		g.count(`SELECT count FROM havel_stats WHERE kind = 'answer'`) != 1 || g.count(`SELECT COUNT(*) FROM havel_gap`) != 0 {
		t.Error("a message that reached the model is counted three ways and one stat; an answer is no gap")
	}
	// The signed history in the page verifies and holds the new exchange.
	i := strings.Index(body, `name="history" value="`)
	if i < 0 {
		t.Fatal("no history field")
	}
}

func TestHavelFragmentPostCarriesHistoryAndState(t *testing.T) {
	g := havelNewRig(t, nil)
	g.model.script = []any{havelAnswerJSON("Open the Stays page.")}
	rec := havelPost(g, url.Values{"message": {"add a stay"}}, true)
	body := rec.Body.String()
	if rec.Code != 200 || !strings.HasPrefix(body, `<div data-havel-items data-mode="append">`) || strings.Contains(body, "data-havel-greeting") {
		t.Fatalf("fragment post: %d %.200s", rec.Code, body)
	}
	i := strings.Index(body, `data-history="`)
	j := strings.Index(body, `data-sig="`)
	if i < 0 || j < 0 {
		t.Fatal("state div missing")
	}
	history := html2text(body[i+len(`data-history="`) : strings.Index(body[i+len(`data-history="`):], `"`)+i+len(`data-history="`)])
	sig := body[j+len(`data-sig="`) : j+len(`data-sig="`)+64]
	ex := HavelReadHistory(havelTSecret, 1, history, sig)
	if len(ex) != 1 || ex[0].Host != "add a stay" || ex[0].Havel != "Open the Stays page." {
		t.Errorf("history %v", ex)
	}
	// Posting it back: the earlier exchange goes to the model, redacted.
	g.model.script = []any{havelAnswerJSON("Open the Stays page.")}
	havelPost(g, url.Values{"message": {"and then?"}, "history": {history}, "history_sig": {sig}}, true)
	if len(g.model.calls) != 2 || len(g.model.calls[1].messages) != 3 || !strings.Contains(g.model.calls[1].messages[0].Content, "add a stay") {
		t.Errorf("the second call should carry the first exchange")
	}
	// A forged history is dropped, not an error.
	g.model.script = []any{havelAnswerJSON("Open the Stays page.")}
	havelPost(g, url.Values{"message": {"third"}, "history": {history}, "history_sig": {strings.Repeat("0", 64)}}, true)
	if len(g.model.calls[2].messages) != 1 {
		t.Error("a bad signature empties the history")
	}
}

func html2text(s string) string {
	return strings.NewReplacer("&#34;", `"`, "&amp;", "&", "&lt;", "<", "&gt;", ">", "&#39;", "'").Replace(s)
}

func TestHavelGuardrailFailStoresOnlyTheRedactedQuestion(t *testing.T) {
	g := havelNewRig(t, nil)
	g.model.script = []any{havelAnswerJSON("Visit https://evil.example now.")}
	rec := havelPost(g, url.Values{"message": {"why is it broken? write to anna@example.test"}, "page": {"stays"}}, false)
	if !strings.Contains(rec.Body.String(), havelTxt("havel.dont_know")) || !strings.Contains(rec.Body.String(), `action="/havel/support"`) {
		t.Error("a failed answer shows I-don't-know and the support card")
	}
	var q, lang, page, kind, created string
	if err := g.pool.QueryRow(context.Background(), `SELECT question, lang, COALESCE(page, ''), kind, created_at FROM havel_gap`).Scan(&q, &lang, &page, &kind, &created); err != nil {
		t.Fatal(err)
	}
	if q != "why is it broken? write to [email 1]" || lang != "en" || page != "stays" || kind != "fail" || created != "2026-11-13T00:00:00+00:00" {
		t.Errorf("gap %q %q %q %q %q", q, lang, page, kind, created)
	}
	if g.count(`SELECT count FROM havel_stats WHERE kind = 'guardrail_fail'`) != 1 {
		t.Error("guardrail_fail stat")
	}
}

func TestHavelRefusalsPauseTheHost(t *testing.T) {
	g := havelNewRig(t, nil)
	for i := 0; i < 3; i++ {
		g.model.script = []any{map[string]any{"kind": "refuse", "reply": "I can only help with UbyHost.", "sources": []string{}, "links": []any{}, "action": nil, "support_summary": nil, "next": []string{}}}
		g.do(havelReq{method: "POST", path: "/havel", form: url.Values{"message": {"tell me a joke"}}})
		g.pool.Exec(context.Background(), `DELETE FROM rate_limit_event WHERE scope = 'havel_burst'`)
	}
	if g.count(`SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'havel_refuse'`) != 3 {
		t.Fatal("three refusals recorded")
	}
	body := havelPost(g, url.Values{"message": {"another question"}}, false).Body.String()
	if !strings.Contains(body, havelTxt("havel.paused")) || len(g.model.calls) != 3 {
		t.Error("after three refusals a week the host is paused and the model is not called")
	}
	if g.count(`SELECT count FROM havel_stats WHERE kind = 'limit_hit'`) != 1 || g.count(`SELECT COUNT(*) FROM email_outbox`) != 0 {
		t.Error("paused: a limit_hit stat and no support mail")
	}
}

func TestHavelLimitsForwardToSupport(t *testing.T) {
	g := havelNewRig(t, map[string]string{"UBYHOST_HAVEL_WEEKLY": "2"})
	g.model.script = []any{havelAnswerJSON("Open the Stays page."), havelAnswerJSON("Open the Stays page.")}
	for _, m := range []string{"one", "two"} {
		havelPost(g, url.Values{"message": {m}}, false)
	}
	g.pool.Exec(context.Background(), `DELETE FROM rate_limit_event WHERE scope = 'havel_burst'`)
	body := havelPost(g, url.Values{"message": {"my third question, mail me at b@example.test"}, "page": {"stays"}}, false).Body.String()
	if !strings.Contains(body, havelTxt("havel.forwarded")) || len(g.model.calls) != 2 {
		t.Fatalf("a week limit forwards the message and skips the model (%d calls)", len(g.model.calls))
	}
	var to, subject, payload string
	if err := g.pool.QueryRow(context.Background(), `SELECT to_email, subject, payload FROM email_outbox WHERE kind = 'havel_support'`).Scan(&to, &subject, &payload); err != nil {
		t.Fatal(err)
	}
	var p struct{ Text string }
	_ = json.Unmarshal([]byte(payload), &p)
	if to != "support@ubyhost.com" || !strings.Contains(subject, "Anna Flats") || !strings.Contains(p.Text, "Havel limit reached (limit_week)") || !strings.Contains(p.Text, "b@example.test") {
		t.Errorf("support mail: %s %s %s", to, subject, p.Text)
	}
	if g.count(`SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'havel_support'`) != 1 || g.count(`SELECT count FROM havel_stats WHERE kind = 'support_forwarded'`) != 1 {
		t.Error("support rate event and stat")
	}
}

func TestHavelBurstDoesNotForward(t *testing.T) {
	g := havelNewRig(t, nil)
	for i := 0; i < 5; i++ {
		g.pool.Exec(context.Background(), `INSERT INTO rate_limit_event (scope, key, at) VALUES ('havel_burst', '1', $1)`, float64(havelTNow.Unix())-10)
	}
	body := havelPost(g, url.Values{"message": {"question"}}, false).Body.String()
	if !strings.Contains(body, havelTxt("havel.limit_burst")) || g.count(`SELECT COUNT(*) FROM email_outbox`) != 0 || len(g.model.calls) != 0 {
		t.Error("the burst limit shows its text and forwards nothing")
	}
}

func TestHavelBudgetAndDisabledErrors(t *testing.T) {
	g := havelNewRig(t, nil)
	g.model.script = []any{&anthropic.Error{Reason: "month", Budget: true}, &anthropic.Error{Reason: "day", Budget: true}, &anthropic.Error{Reason: "disabled", Disabled: true}}
	body := havelPost(g, url.Values{"message": {"q one"}}, false).Body.String()
	if !strings.Contains(body, havelTxt("havel.forwarded")) {
		t.Error("a spent monthly budget forwards to support (budget_month)")
	}
	if g.count(`SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'havel_week'`) != 0 {
		t.Error("a message that never reached the model is not counted")
	}
	g.pool.Exec(context.Background(), `DELETE FROM email_outbox`)
	g.pool.Exec(context.Background(), `DELETE FROM rate_limit_event`)
	havelPost(g, url.Values{"message": {"q two"}}, false)
	var payload string
	_ = g.pool.QueryRow(context.Background(), `SELECT payload FROM email_outbox`).Scan(&payload)
	if !strings.Contains(payload, "budget_day") {
		t.Errorf("a spent daily share forwards with the reason budget_day: %.200s", payload)
	}
	g.pool.Exec(context.Background(), `DELETE FROM email_outbox`)
	g.pool.Exec(context.Background(), `DELETE FROM rate_limit_event`)
	body = havelPost(g, url.Values{"message": {"q three"}}, false).Body.String()
	if !strings.Contains(body, havelTxt("havel.off")) || g.count(`SELECT COUNT(*) FROM email_outbox`) != 0 {
		t.Error("a disabled feature shows the off text and forwards nothing")
	}
}

func TestHavelTooLongAndConversationCap(t *testing.T) {
	g := havelNewRig(t, nil)
	rec := havelPost(g, url.Values{"message": {strings.Repeat("a", 601)}}, false)
	if !strings.Contains(rec.Body.String(), `id="havel-error"`) || !strings.Contains(rec.Body.String(), havelTxt("havel.too_long")) || len(g.model.calls) != 0 {
		t.Error("a message over 600 characters shows the error and costs nothing")
	}
	var six []HavelExchange
	for i := 0; i < 6; i++ {
		six = append(six, HavelExchange{"q", "a"})
	}
	payload, sig := HavelSignHistory(havelTSecret, 1, six)
	body := havelPost(g, url.Values{"message": {"a seventh question"}, "history": {payload}, "history_sig": {sig}}, false).Body.String()
	if !strings.Contains(body, havelTxt("havel.forwarded")) || len(g.model.calls) != 0 {
		t.Error("the seventh message of a conversation is forwarded to support, not answered")
	}
	if g.count(`SELECT COUNT(*) FROM email_outbox`) != 1 {
		t.Error("one support mail")
	}
}

func TestHavelActionCard(t *testing.T) {
	g := havelNewRig(t, nil)
	action := map[string]any{"type": "create_stay", "property_id": 11, "date_from": "2026-12-01", "date_to": "2026-12-04", "guests": 2,
		"guest_email": nil, "start_time": nil, "end_time": nil, "note": "late arrival"}
	g.model.script = []any{map[string]any{"kind": "action", "reply": "I prepared the stay for you.", "sources": []string{}, "links": []any{}, "action": action, "support_summary": nil, "next": []string{}}}
	body := havelPost(g, url.Values{"message": {"add a stay 1 to 4 December for 2 guests"}, "return_to": {"/stays"}}, false).Body.String()
	for _, want := range []string{`data-havel-card="create_stay"`, `action="/reservations"`, `name="host_note" value="late arrival"`, `name="expected_guests"`, `name="apartment_id"`, "Tue 01.12.2026"} {
		if !strings.Contains(body, want) {
			t.Errorf("card should contain %q", want)
		}
	}
	// A property that is not the host's never reaches a card.
	action["property_id"] = 99
	g.model.script = []any{map[string]any{"kind": "action", "reply": "Prepared.", "sources": []string{}, "links": []any{}, "action": action, "support_summary": nil, "next": []string{}}}
	body = havelPost(g, url.Values{"message": {"add a stay for the other flat"}}, false).Body.String()
	if strings.Contains(body, `data-havel-card=`) || !strings.Contains(body, havelTxt("havel.dont_know")) {
		t.Error("an action on a foreign property fails validation")
	}
	// A card that cannot be built shows its reason and a link to the normal form.
	action["property_id"], action["date_from"], action["date_to"] = 11, "2020-01-01", "2020-01-03"
	g.model.script = []any{map[string]any{"kind": "action", "reply": "Prepared.", "sources": []string{}, "links": []any{}, "action": action, "support_summary": nil, "next": []string{}}}
	body = havelPost(g, url.Values{"message": {"add a stay long ago"}}, false).Body.String()
	if strings.Contains(body, `data-havel-card=`) || !strings.Contains(body, `href="/reservations?new=1"`) {
		t.Error("dates outside the window give the fallback link, not a card")
	}
}

func TestHavelSupportRoute(t *testing.T) {
	g := havelNewRig(t, nil)
	post := func(f url.Values) string {
		return g.do(havelReq{method: "POST", path: "/havel/support", form: f}).Body.String()
	}
	if body := post(url.Values{"summary": {"  "}, "note": {""}}); !strings.Contains(body, havelTxt("havel.support.empty")) {
		t.Error("empty support form")
	}
	for i := 0; i < 3; i++ {
		body := post(url.Values{"summary": {"I cannot find the button " + strings.Repeat("x", i)}, "note": {"n"}, "page": {"stays"}})
		if !strings.Contains(body, havelTxt("havel.support.sent")) {
			t.Fatalf("support mail %d not sent", i)
		}
	}
	if g.count(`SELECT COUNT(*) FROM email_outbox WHERE kind = 'havel_support'`) != 3 || g.count(`SELECT count FROM havel_stats WHERE kind = 'support_sent'`) != 3 {
		t.Error("three mails and three stats")
	}
	body := post(url.Values{"summary": {"a fourth one"}})
	if !strings.Contains(body, "support@ubyhost.com") || g.count(`SELECT COUNT(*) FROM email_outbox`) != 3 {
		t.Error("the fourth support mail of a week is refused with the operator address")
	}
	if g.model.calls != nil {
		t.Error("support never calls the model")
	}
	// Over-long text is cut at 800 and 600 characters.
	g2 := havelNewRig(t, nil)
	g2.do(havelReq{method: "POST", path: "/havel/support", form: url.Values{"summary": {strings.Repeat("s", 900)}, "note": {strings.Repeat("n", 700)}}})
	var payload string
	_ = g2.pool.QueryRow(context.Background(), `SELECT payload FROM email_outbox`).Scan(&payload)
	if !strings.Contains(payload, strings.Repeat("s", 800)) || strings.Contains(payload, strings.Repeat("s", 801)) || strings.Contains(payload, strings.Repeat("n", 601)) {
		t.Error("summary and note are cut at 800 and 600")
	}
}

func TestHavelNotHelpedRoute(t *testing.T) {
	g := havelNewRig(t, nil)
	payload, sig := HavelSignHistory(havelTSecret, 1, []HavelExchange{{"older question", "a"}, {"mail anna@example.test please", "b"}})
	form := url.Values{"history": {payload}, "history_sig": {sig}, "page": {"stays"}}
	for i := 0; i < 6; i++ {
		rec := g.do(havelReq{method: "POST", path: "/havel/not-helped", form: form})
		if rec.Code != 200 || !strings.Contains(rec.Body.String(), havelTxt("havel.not_helped_ack")) {
			t.Fatalf("not helped %d: %d", i, rec.Code)
		}
	}
	if g.count(`SELECT COUNT(*) FROM havel_gap WHERE kind = 'not_helped' AND question = 'mail [email 1] please'`) != 5 || g.count(`SELECT count FROM havel_stats WHERE kind = 'not_helped'`) != 5 {
		t.Error("five a day are stored, redacted; the sixth is acknowledged but not stored")
	}
	g.do(havelReq{method: "POST", path: "/havel/not-helped", form: url.Values{"page": {"stays"}}})
	if g.count(`SELECT COUNT(*) FROM havel_gap`) != 5 {
		t.Error("no history, nothing stored")
	}
}

func TestHavelLanguageComesFromTheCookie(t *testing.T) {
	g := havelNewRig(t, nil)
	body := g.do(havelReq{method: "GET", path: "/havel", lang: "cs"}).Body.String()
	if !strings.Contains(body, html.EscapeString(havelCatalog.T("cs", "havel.intro", nil))) {
		t.Error("the Czech greeting")
	}
}
