package auth

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"reflect"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/signup"
)

// The cases in testdata/signup/cases.json are Python's answers to the four
// routes, recorded by App/scripts/signup_pages_golden.py with the database
// and Turnstile parts replaced (see the script). TestSignupPagesMatchPython
// builds Go's context from the same request, checks it against the context
// Python handed to render() and the arguments it handed to register(), and
// checks the page byte for byte (normalised, CSRF token masked).

type signupCookie struct {
	Name     string `json:"name"`
	Value    string `json:"value"`
	Path     string `json:"path"`
	MaxAge   string `json:"max_age"`
	SameSite string `json:"samesite"`
	Secure   bool   `json:"secure"`
	HTTPOnly bool   `json:"httponly"`
}

type signupCase struct {
	Name     string            `json:"name"`
	Method   string            `json:"method"`
	Path     string            `json:"path"`
	Query    string            `json:"query"`
	Form     [][2]string       `json:"form"`
	Cookies  map[string]string `json:"cookies"`
	Env      map[string]string `json:"env"`
	SignedIn bool              `json:"signed_in"`
	Patch    map[string]bool   `json:"patch"`
	Expected struct {
		Status      int                        `json:"status"`
		ContentType string                     `json:"content_type"`
		Location    string                     `json:"location"`
		SetCookies  []signupCookie             `json:"set_cookies"`
		Template    string                     `json:"template"`
		Context     map[string]json.RawMessage `json:"context"`
		Register    map[string]json.RawMessage `json:"register"`
		Body        string                     `json:"body"`
	} `json:"expected"`
}

type signupGolden struct {
	Secret string       `json:"secret"`
	Nonce  string       `json:"nonce"`
	NowMS  int64        `json:"now_ms"`
	Cases  []signupCase `json:"cases"`
}

func loadSignupGolden(t *testing.T) signupGolden {
	t.Helper()
	raw, err := os.ReadFile("testdata/signup/cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var g signupGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	if len(g.Cases) < 30 {
		t.Fatalf("only %d cases", len(g.Cases))
	}
	return g
}

var (
	signupSpace = regexp.MustCompile(`[ \t\n\r\f\v]+`)
	signupMask  = regexp.MustCompile(`(name="_csrf" value=")[^"]*(")|(name="csrf-token" content=")[^"]*(")`)
)

// signupNormalize is public_legal_golden.normalize plus the script's mask().
func signupNormalize(s string) string {
	s = strings.TrimSpace(strings.ReplaceAll(signupSpace.ReplaceAllString(s, " "), "> <", "><"))
	return signupMask.ReplaceAllStringFunc(s, func(m string) string {
		if strings.HasPrefix(m, `name="_csrf"`) {
			return `name="_csrf" value="CSRF"`
		}
		return `name="csrf-token" content="CSRF"`
	})
}

// signupCookieOf is public_legal_golden._cookie for one Set-Cookie line
// (values other than the language cookie's reduced to "set" or "").
func signupCookieOf(line string) signupCookie {
	parts := strings.Split(line, ";")
	name, value, _ := strings.Cut(strings.TrimSpace(parts[0]), "=")
	c := signupCookie{Name: name, Value: value}
	for _, a := range parts[1:] {
		k, v, _ := strings.Cut(strings.TrimSpace(a), "=")
		switch strings.ToLower(k) {
		case "path":
			c.Path = v
		case "max-age":
			c.MaxAge = v
		case "samesite":
			c.SameSite = strings.ToLower(v)
		case "secure":
			c.Secure = true
		case "httponly":
			c.HTTPOnly = true
		}
	}
	if c.Name != langCookieName {
		if c.Value != "" {
			c.Value = "set"
		}
	}
	return c
}

// signupOrdered decodes a JSON object keeping its key order.
func signupOrdered(t *testing.T, raw json.RawMessage) [][2]string {
	t.Helper()
	dec := json.NewDecoder(bytes.NewReader(raw))
	if _, err := dec.Token(); err != nil {
		t.Fatal(err)
	}
	var out [][2]string
	for dec.More() {
		k, _ := dec.Token()
		var v string
		if err := dec.Decode(&v); err != nil {
			t.Fatal(err)
		}
		out = append(out, [2]string{k.(string), v})
	}
	return out
}

func signupCSRFFor(t *testing.T, secret, nonce string, at time.Time) string {
	t.Helper()
	sum := sha256.Sum256([]byte(nonce))
	tok, err := secure.NewTimedSerializer(secret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, at)
	if err != nil {
		t.Fatal(err)
	}
	return tok
}

func signupRequest(t *testing.T, method, path, query string, form [][2]string, cookies map[string]string, csrf string) *http.Request {
	t.Helper()
	target := "http://testserver" + path
	if query != "" {
		target += "?" + query
	}
	var pairs []string
	for _, p := range form {
		pairs = append(pairs, url.QueryEscape(p[0])+"="+url.QueryEscape(p[1]))
	}
	if method == http.MethodPost && csrf != "" {
		pairs = append(pairs, "_csrf="+url.QueryEscape(csrf))
	}
	r := httptest.NewRequest(method, target, strings.NewReader(strings.Join(pairs, "&")))
	if method == http.MethodPost {
		r.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	}
	var lines []string
	for k, v := range cookies {
		lines = append(lines, k+"="+v)
	}
	if len(lines) > 0 {
		r.Header.Set("Cookie", strings.Join(lines, "; "))
	}
	return r
}

func signupJSONEq(t *testing.T, raw json.RawMessage, want any) bool {
	t.Helper()
	got, _ := json.Marshal(want)
	var a, b any
	_ = json.Unmarshal(raw, &a)
	_ = json.Unmarshal(got, &b)
	return reflect.DeepEqual(a, b)
}

// signupCheckContext compares Go's view with the context Python rendered.
func signupCheckContext(t *testing.T, ctx map[string]json.RawMessage, v signupView) {
	t.Helper()
	for key, raw := range ctx {
		var ok bool
		switch key {
		case "attr":
			ok = signupJSONEq(t, raw, v.Attr)
		case "selection":
			ok = reflect.DeepEqual(signupOrdered(t, raw), v.Selection)
		case "consent_boxes":
			boxes := v.Boxes
			if boxes == nil {
				boxes = []signupConsentBox{}
			}
			ok = signupJSONEq(t, raw, boxes)
		case "lang_next":
			ok = signupJSONEq(t, raw, v.LangNext)
		case "error":
			ok = signupJSONEq(t, raw, v.Error)
		case "error_field":
			ok = signupJSONEq(t, raw, v.ErrorField)
		case "email":
			ok = signupJSONEq(t, raw, v.Email)
		case "workspace":
			ok = signupJSONEq(t, raw, v.Workspace)
		case "marketing_opt_in":
			ok = signupJSONEq(t, raw, v.MarketingOptIn)
		case "token":
			ok = signupJSONEq(t, raw, v.Token)
		case "expired":
			ok = signupJSONEq(t, raw, v.Expired)
		default:
			t.Errorf("context key %q not ported", key)
			continue
		}
		if !ok {
			t.Errorf("context %s = %s, Go has %+v", key, raw, v)
		}
	}
}

// signupCheckRegister compares Go's RegisterInput with Python's register() kwargs.
func signupCheckRegister(t *testing.T, want map[string]json.RawMessage, in signup.RegisterInput) {
	t.Helper()
	got := map[string]any{
		"email": in.Email, "workspace": in.Workspace, "attr": in.Attr, "consents": in.Consents,
		"onboarding_opt_out": in.OnboardingOptOut, "lang": in.Lang, "selection": signup.CleanSelection(in.Selection),
	}
	if len(want) != len(got) {
		t.Errorf("register keys %v", want)
	}
	for k, v := range got {
		if !signupJSONEq(t, want[k], v) {
			t.Errorf("register %s = %s, Go has %v", k, want[k], v)
		}
	}
}

func TestSignupPagesMatchPython(t *testing.T) {
	g := loadSignupGolden(t)
	at := time.UnixMilli(g.NowMS)
	csrf := signupCSRFFor(t, g.Secret, g.Nonce, at)
	rendered := 0
	for _, c := range g.Cases {
		t.Run(c.Name, func(t *testing.T) {
			getenv := func(k string) string { return c.Env[k] }
			d := deps{getenv: getenv, now: func() time.Time { return at }}
			cookies := map[string]string{"ubyhost_csrf": g.Nonce}
			for k, v := range c.Cookies {
				cookies[k] = v
			}
			r := signupRequest(t, c.Method, c.Path, c.Query, c.Form, cookies, csrf)
			want := c.Expected
			if want.Template == "" {
				// No page: the 404s run the real handler (no database is
				// reached); the signed-in redirect is TestSignupDatabase's.
				if c.SignedIn && want.Status == http.StatusSeeOther && want.Location == "/" {
					return
				}
				rec := httptest.NewRecorder()
				handler := map[string]http.HandlerFunc{
					"GET /signup": d.signupForm, "POST /signup": d.signupSubmit,
					"GET /signup/verify": d.signupVerifyForm, "POST /signup/verify": d.signupVerifySubmit,
				}[c.Method+" "+c.Path]
				handler(rec, r)
				if rec.Code != want.Status || rec.Body.String() != want.Body || rec.Header().Get("Content-Type") != want.ContentType {
					t.Fatalf("got %d %q %q, want %d %q %q", rec.Code, rec.Header().Get("Content-Type"), rec.Body.String(),
						want.Status, want.ContentType, want.Body)
				}
				return
			}
			secret := g.Secret
			nowMS := g.NowMS
			var v signupView
			switch c.Method + " " + c.Path {
			case "GET /signup":
				q := r.URL.Query()
				v = d.signupFormView(r, secret, signup.Attribution(secret, q, true, nowMS), nil, q, nowMS)
			case "POST /signup":
				form(r)
				in := d.readSignupForm(r, secret, nowMS)
				switch {
				case c.Patch["turnstile"] == false && signupHasKey(c.Patch, "turnstile"):
					v = d.againView(r, secret, in, "signup.error.turnstile", http.StatusForbidden, "", nowMS)
				case c.Patch["rate_limited"]:
					v = d.againView(r, secret, in, "signup.error.rate_limited", http.StatusTooManyRequests, "", nowMS)
				default:
					if key, status, field := in.check(); key != "" {
						v = d.againView(r, secret, in, key, status, field, nowMS)
					} else {
						signupCheckRegister(t, want.Register, signupRegisterInput(r, in, getenv))
						v = signupView{Template: "signup_sent.html", Email: in.Email}
					}
				}
			case "GET /signup/verify":
				v = signupVerifyView(signupQuery(r, "t"), !c.Patch["pending"], "", 0)
			case "POST /signup/verify":
				switch {
				case c.Patch["locked"]:
					v = signupVerifyView(formStr(r, "t", ""), false, "signup.verify.locked", http.StatusTooManyRequests)
				default: // no pending account, or activate lost the race
					v = signupVerifyView("", true, "", 0)
				}
			}
			if want.Register != nil && c.Path == "/signup" && v.Template != "signup_sent.html" {
				t.Errorf("Python registered, Go did not")
			}
			if v.Template == "signup.html" {
				signupSameClick(t, secret, nowMS, want.Context["attr"], &v)
			}
			if v.Template != want.Template {
				t.Fatalf("template %q, want %q", v.Template, want.Template)
			}
			signupCheckContext(t, want.Context, v)
			rec := httptest.NewRecorder()
			if err := renderSignup(rec, r, getenv, at, c.SignedIn, v); err != nil {
				t.Fatal(err)
			}
			if rec.Code != want.Status || rec.Header().Get("Content-Type") != want.ContentType {
				t.Errorf("status %d %q, want %d %q", rec.Code, rec.Header().Get("Content-Type"), want.Status, want.ContentType)
			}
			var gotCookies []signupCookie
			for _, line := range rec.Header().Values("Set-Cookie") {
				gotCookies = append(gotCookies, signupCookieOf(line))
			}
			if len(gotCookies) != 0 || len(want.SetCookies) != 0 {
				if !reflect.DeepEqual(gotCookies, want.SetCookies) {
					t.Errorf("cookies %+v, want %+v", gotCookies, want.SetCookies)
				}
			}
			page, err := os.ReadFile("testdata/signup/" + c.Name + ".html")
			if err != nil {
				t.Fatal(err)
			}
			got, exp := signupNormalize(rec.Body.String()), strings.TrimSpace(string(page))
			if got != exp {
				i := 0
				for i < len(got) && i < len(exp) && got[i] == exp[i] {
					i++
				}
				lo := max(0, i-120)
				t.Fatalf("page differs at %d:\n go:     %q\n python: %q", i, got[lo:min(len(got), i+120)], exp[lo:min(len(exp), i+120)])
			}
			rendered++
		})
	}
	if rendered < 30 {
		t.Errorf("only %d pages compared", rendered)
	}
}

// signupSameClick: a click value with ids of two platforms is long enough for
// itsdangerous to zlib-compress it, and Go's zlib bytes differ from Python's.
// When both values sign the same ids and time, Python's is used for the page.
func signupSameClick(t *testing.T, secret string, nowMS int64, raw json.RawMessage, v *signupView) {
	t.Helper()
	var attr map[string]string
	_ = json.Unmarshal(raw, &attr)
	py, gov := attr["click"], v.Attr["click"]
	if py == gov || py == "" || gov == "" || !strings.HasPrefix(gov, ".") {
		return
	}
	a, b := signup.ReadClick(secret, py, nowMS), signup.ReadClick(secret, gov, nowMS)
	if a == nil || b == nil || !reflect.DeepEqual(a, b) {
		t.Fatalf("click values differ: %q, %q", py, gov)
	}
	v.Attr["click"] = py
	v.LangNext = signupHref(secret, signupHrefLang(v.LangNext), v.Attr, v.Selection, nowMS)
}

// signupHrefLang is the lang= value of a /signup?lang=... address.
func signupHrefLang(href string) string {
	u, _ := url.Parse(href)
	return u.Query().Get("lang")
}

func signupHasKey(m map[string]bool, k string) bool { _, ok := m[k]; return ok }

// TestSignupWorkspaceFromEmail is _workspace_from_email on the edges.
func TestSignupWorkspaceFromEmail(t *testing.T) {
	for in, want := range map[string]string{
		"anna.nova+airbnb@example.cz":       "anna nova",
		"__-..@example.cz":                  "example.cz",
		"+tag@example.cz":                   "example.cz",
		"jan_novak-2@x.cz":                  "jan novak 2",
		strings.Repeat("ab.", 50) + "@x.cz": strings.TrimSpace(strings.Repeat("ab ", 40)),
		"žluťoučký.kůň@x.cz":                "žluťoučký kůň",
	} {
		if got := signupWorkspaceFromEmail(in); got != want {
			t.Errorf("signupWorkspaceFromEmail(%q) = %q, want %q", in, got, want)
		}
	}
}

// signupDBEnv is the environment of TestSignupDatabase.
var signupDBEnv = map[string]string{
	"UBYHOST_SECRET_KEY":      "signup-pages-db-secret-0123456789-abcdef",
	"UBYHOST_SIGNUP_ENABLED":  "1",
	"UBYHOST_MAIL_BACKEND":    "console",
	"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example",
	"UBYHOST_DEPLOYMENT":      "local",
}

// TestSignupDatabase runs the four routes end to end on PostgreSQL: the sign-up
// row, budgets and mail, the verify link from the outbox, activation with its
// session cookie and audit row, the 410 and 429 answers, the signed-in
// redirect and the Turnstile refusal in production.
func TestSignupDatabase(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	env := map[string]string{}
	for k, v := range signupDBEnv {
		env[k] = v
	}
	getenv := func(k string) string { return env[k] }
	at := time.Now().UTC()
	d := deps{pool: pool, getenv: getenv, now: func() time.Time { return at }}
	secret := env["UBYHOST_SECRET_KEY"]
	nonce := "signup-db-nonce"
	csrf := signupCSRFFor(t, secret, nonce, at)
	mux := http.NewServeMux()
	for _, rt := range Routes(pool, getenv, d.now) {
		mux.HandleFunc(rt.Pattern, rt.Handler)
	}
	do := func(method, path, query string, form [][2]string, extra map[string]string) *httptest.ResponseRecorder {
		cookies := map[string]string{"ubyhost_csrf": nonce}
		for k, v := range extra {
			cookies[k] = v
		}
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, signupRequest(t, method, path, query, form, cookies, csrf))
		return rec
	}
	count := func(sql string, args ...any) int {
		var n int
		if err := pool.QueryRow(ctx, sql, args...).Scan(&n); err != nil {
			t.Fatalf("%s: %v", sql, err)
		}
		return n
	}

	// Sign up: the "check your e-mail" page, a pending account, both budgets, one mail.
	rec := do("POST", "/signup", "lang=en", [][2]string{{"email", " Anna.Nova@Example.CZ "}, {"accept", "1"}, {"plan", "max"}}, nil)
	if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), "anna.nova@example.cz") {
		t.Fatalf("submit %d %s", rec.Code, rec.Body.String())
	}
	var id int64
	var name, selection string
	var active int64
	if err := pool.QueryRow(ctx, `SELECT id, display_name, active, signup_selection_json FROM user_account WHERE email = 'anna.nova@example.cz'`).
		Scan(&id, &name, &active, &selection); err != nil {
		t.Fatal(err)
	}
	if name != "anna nova" || active != 0 || selection != `{"plan": "max"}` {
		t.Fatalf("account %q %d %q", name, active, selection)
	}
	if n := count(`SELECT COUNT(*) FROM rate_limit_event WHERE (scope = 'signup_ip' AND key = '192.0.2.1') OR (scope = 'signup_email' AND key = 'anna.nova@example.cz')`); n != 2 {
		t.Fatalf("%d budget rows, want 2", n)
	}
	if n := count(`SELECT COUNT(*) FROM legal_acceptance WHERE user_account_id = $1 AND ip = '192.0.2.1'`, id); n != 3 {
		t.Fatalf("%d acceptance rows", n)
	}
	var key, payloadRaw string
	if err := pool.QueryRow(ctx, `SELECT idempotency_key, payload FROM email_outbox WHERE kind = 'signup_verify' AND owner_user_id = $1`, id).
		Scan(&key, &payloadRaw); err != nil {
		t.Fatal(err)
	}
	var payload map[string]string
	if err := json.Unmarshal([]byte(payloadRaw), &payload); err != nil {
		t.Fatal(err)
	}
	keys, err := secure.LoadDataKeys(getenv)
	if err != nil {
		t.Fatal(err)
	}
	plain, err := keys.Decrypt(payload["claim_secret_enc"], 0, at)
	if err != nil {
		t.Fatal(err)
	}
	token := string(plain)

	// A bad field: the form again, 422, the address kept, no second account.
	rec = do("POST", "/signup", "", [][2]string{{"email", "b@example.cz"}}, nil)
	if rec.Code != http.StatusUnprocessableEntity || !strings.Contains(rec.Body.String(), `value="b@example.cz"`) ||
		count(`SELECT COUNT(*) FROM user_account WHERE email = 'b@example.cz'`) != 0 {
		t.Fatalf("no accept: %d", rec.Code)
	}

	// The verify page: the form for the newest link, 410 for anything else.
	rec = do("GET", "/signup/verify", "t="+url.QueryEscape(token), nil, nil)
	if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), `name="t" value="`+token+`"`) {
		t.Fatalf("verify form %d", rec.Code)
	}
	if rec = do("GET", "/signup/verify", "t=forged", nil, nil); rec.Code != http.StatusGone {
		t.Fatalf("verify forged %d", rec.Code)
	}

	// Confirm: 303 to "/", the session cookie then the language, the audit row.
	rec = do("POST", "/signup/verify", "lang=en", [][2]string{{"t", token}}, nil)
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/" {
		t.Fatalf("confirm %d %q", rec.Code, rec.Header().Get("Location"))
	}
	lines := rec.Header().Values("Set-Cookie")
	if len(lines) != 2 || !strings.HasPrefix(lines[0], session.CookieName+"=") || !strings.HasPrefix(lines[1], "ubyhost_lang=en;") {
		t.Fatalf("cookies %v", lines)
	}
	payloadSession, ok := session.ReadPayload(secret, cookieValue(lines[0]), at)
	if !ok || payloadSession["uid"] != id || payloadSession["rm"] != nil {
		t.Fatalf("session payload %v", payloadSession)
	}
	var action, detail, actor string
	var owner int64
	var actorID *int64
	if err := pool.QueryRow(ctx, `SELECT action, detail, actor, owner_user_id, actor_user_id FROM audit WHERE action = 'login'`).
		Scan(&action, &detail, &actor, &owner, &actorID); err != nil {
		t.Fatal(err)
	}
	if detail != "method=signup_link" || owner != id || actorID != nil || actor == "" || actor == "anonymous" {
		t.Fatalf("audit %q %q %d %v", detail, actor, owner, actorID)
	}
	if count(`SELECT active FROM user_account WHERE id = $1`, id) != 1 {
		t.Fatal("account not active")
	}

	// The same link again: 410 and one bad link counted.
	if rec = do("POST", "/signup/verify", "", [][2]string{{"t", token}}, nil); rec.Code != http.StatusGone {
		t.Fatalf("second confirm %d", rec.Code)
	}
	if n := count(`SELECT COUNT(*) FROM rate_limit_event WHERE scope = 'login_link_bad' AND key = '192.0.2.1'`); n != 1 {
		t.Fatalf("%d bad links", n)
	}
	for i := 0; i < 19; i++ {
		if err := session.LinkRecordConsumeFailure(ctx, pool, "192.0.2.1", at); err != nil {
			t.Fatal(err)
		}
	}
	rec = do("POST", "/signup/verify", "lang=en", [][2]string{{"t", token}}, nil)
	if rec.Code != http.StatusTooManyRequests || !strings.Contains(rec.Body.String(), signupEsc(signupCatalog.Strings.T("en", "signup.verify.locked", nil))) {
		t.Fatalf("locked %d", rec.Code)
	}

	// Signed in: GET /signup goes home.
	var sv int64
	if err := pool.QueryRow(ctx, `SELECT session_version FROM user_account WHERE id = $1`, id).Scan(&sv); err != nil {
		t.Fatal(err)
	}
	cookie, err := session.IssueSession(secret, id, sv, session.IssueOptions{}, at)
	if err != nil {
		t.Fatal(err)
	}
	if rec = do("GET", "/signup", "", nil, map[string]string{session.CookieName: cookie}); rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/" {
		t.Fatalf("signed in %d", rec.Code)
	}

	// The IP budget: ten attempts an hour, then 429 before any check.
	for i := 0; i < 8; i++ {
		if err := session.RateRecord(ctx, pool, "signup_ip", "192.0.2.1", at); err != nil {
			t.Fatal(err)
		}
	}
	rec = do("POST", "/signup", "", [][2]string{{"email", "c@example.cz"}, {"accept", "1"}}, nil)
	if rec.Code != http.StatusTooManyRequests || count(`SELECT COUNT(*) FROM user_account WHERE email = 'c@example.cz'`) != 0 {
		t.Fatalf("rate limit %d", rec.Code)
	}

	// Production with Turnstile: no token, 403 before the budget is touched.
	env["UBYHOST_DEPLOYMENT"] = "production"
	env["TURNSTILE_SECRET"] = "s"
	env["TURNSTILE_HOSTNAMES"] = "ubyhost.example"
	before := count(`SELECT COUNT(*) FROM rate_limit_event`)
	rec = do("POST", "/signup", "", [][2]string{{"email", "d@example.cz"}, {"accept", "1"}}, nil)
	if rec.Code != http.StatusForbidden || !strings.Contains(rec.Body.String(), `class="cf-turnstile"`) ||
		count(`SELECT COUNT(*) FROM rate_limit_event`) != before {
		t.Fatalf("turnstile %d", rec.Code)
	}
}
