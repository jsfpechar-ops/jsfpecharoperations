package layout

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// pinnedEnv is PINNED_ENV in App/scripts/go_layout_golden.py.
var pinnedEnv = map[string]string{
	"UBYHOST_UBYPORT_ENV":     "mock",
	"UBYHOST_DEPLOYMENT":      "local",
	"UBYHOST_OPERATOR_EMAIL":  "",
	"UBYHOST_PUBLIC_BASE_URL": "http://127.0.0.1:8080",
	"UBYHOST_SECRET_KEY":      "golden-secret-key-not-for-real-use",
}

func getenv(k string) string { return pinnedEnv[k] }

type goldenCase struct {
	Name           string `json:"name"`
	URL            string `json:"url"`
	Cookie         string `json:"cookie"`
	V2             bool   `json:"v2"`
	Nav            string `json:"nav"`
	BodyKind       string `json:"body_kind"`
	HowKey         string `json:"how_key"`
	ShowNav        bool   `json:"show_nav"`
	AdminWorkspace bool   `json:"admin_workspace"`
	BackURL        string `json:"back_url"`
	IsAdmin        bool   `json:"is_admin"`
	Impersonating  bool   `json:"impersonating"`
	DisplayName    string `json:"display_name"`
	Username       string `json:"username"`
	DeletionDueAt  string `json:"deletion_due_at"`
	PropertyCount  int    `json:"property_count"`
	MinutesLeft    *int   `json:"minutes_left"`
	Title          string `json:"title"`
	SetCookie      string `json:"set_cookie"`
	// 1381.
	SignedIn       bool           `json:"signed_in"`
	Alerts         []goldenAlert  `json:"alerts"`
	BillingOn      bool           `json:"billing_on"`
	Billing        *goldenBilling `json:"billing"`
	HavelOn        bool           `json:"havel_on"`
	HavelState     string         `json:"havel_state"`
	Account        goldenAccount  `json:"account"`
	Celebration    string         `json:"celebration"`
	SentGuestCount int            `json:"sent_guest_count"`
	HideAlertStack bool           `json:"hide_alert_stack"`
	AlertsExpanded bool           `json:"alerts_expanded"`
	PhHidePin      bool           `json:"ph_hide_pin"`
}

type goldenAlert struct {
	ID            int64       `json:"id"`
	Level         string      `json:"level"`
	Kind          string      `json:"kind"`
	ApartmentID   *int64      `json:"apartment_id"`
	ReservationID *int64      `json:"reservation_id"`
	DedupeKey     string      `json:"dedupe_key"`
	Message       string      `json:"message"`
	Detail        string      `json:"detail"`
	Params        string      `json:"params"`
	FeedProperty  string      `json:"feed_property"`
	Stay          *goldenStay `json:"stay"`
}

type goldenStay struct {
	ID       int64  `json:"id"`
	DateFrom string `json:"date_from"`
	DateTo   string `json:"date_to"`
	Declared *int64 `json:"declared"`
	Override *int64 `json:"override"`
	Reduced  *int64 `json:"reduced"`
	Property string `json:"property"`
}

type goldenBilling struct {
	Status      string  `json:"status"`
	Plan        *string `json:"plan"`
	TrialEndsAt *string `json:"trial_ends_at"`
	PeriodEnd   *string `json:"period_end"`
}

type goldenAccount struct {
	TwoFactorPromptedAt *string `json:"two_factor_prompted_at"`
	TotpEnabled         int     `json:"totp_enabled"`
	SignupAt            *string `json:"signup_at"`
}

func str(p *string) string {
	if p == nil {
		return ""
	}
	return *p
}

// goldenShell is the shell a case describes, as loadShell would read it.
func goldenShell(c goldenCase) shell {
	if !c.SignedIn {
		return shell{}
	}
	name := c.DisplayName
	if name == "" {
		name = c.Username
	}
	sh := shell{
		SignedIn: true, IsAdmin: c.IsAdmin, Impersonating: c.Impersonating,
		WorkspaceName: name, WorkspaceUsername: c.Username,
		DeletionDueAt: c.DeletionDueAt, PropertyCount: c.PropertyCount, MinutesLeft: c.MinutesLeft,
		AccountID: 2, AccountIsWorkspace: !c.Impersonating,
		TwoFactorDone: str(c.Account.TwoFactorPromptedAt) != "" || c.Account.TotpEnabled != 0,
		SignupAt:      str(c.Account.SignupAt),
		HavelOn:       c.HavelOn, HavelState: "off",
		Progress: map[int64]calendar.AlertProgress{},
	}
	if c.Impersonating {
		sh.AccountID = 1
	}
	if c.HavelOn {
		sh.HavelState = c.HavelState
	}
	if b := c.Billing; b != nil {
		sh.Billing = billingRow{Status: b.Status, Plan: str(b.Plan), TrialEndsAt: str(b.TrialEndsAt), PeriodEnd: str(b.PeriodEnd)}
	}
	for _, a := range c.Alerts {
		row := alertRow{ID: a.ID, Level: a.Level, Kind: a.Kind, ApartmentID: a.ApartmentID, ReservationID: a.ReservationID,
			DedupeKey: a.DedupeKey, Message: a.Message, Detail: a.Detail, Params: a.Params, FeedProperty: a.FeedProperty}
		if st := a.Stay; st != nil {
			row.Stay = &alertStay{AlertStay: calendar.AlertStay{ID: st.ID, DateFrom: st.DateFrom, DateTo: st.DateTo,
				Declared: st.Declared, Override: st.Override, Reduced: st.Reduced}, Property: st.Property}
			sh.Progress[st.ID] = calendar.AlertProgressNoGuests(row.Stay.AlertStay)
		}
		sh.Alerts = append(sh.Alerts, row)
	}
	sortAlerts(sh.Alerts)
	return sh
}

// catalogKeys is every key of the layout and host catalogs.
var catalogKeys = func() map[string]bool {
	out := map[string]bool{}
	for _, cat := range []hostweb.Catalog{Strings, hostweb.HostStrings} {
		for _, table := range cat {
			for k := range table {
				out[k] = true
			}
		}
	}
	return out
}()

var textOrAttr = regexp.MustCompile(`(?:>|=")\s*([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+)\s*(?:<|")`)

// assertNoRawKeys fails when a text node or attribute value of body is an
// i18n key: a t() that found no string printed its key.
func assertNoRawKeys(t *testing.T, body string) {
	t.Helper()
	for _, m := range textOrAttr.FindAllStringSubmatch(body, -1) {
		if catalogKeys[m[1]] {
			t.Errorf("raw i18n key in output: %q", m[1])
		}
	}
}

var (
	wsRun     = regexp.MustCompile(`\s+`)
	afterTag  = regexp.MustCompile(`> `)
	beforeTag = regexp.MustCompile(` <`)
)

// normalise is the golden comparison: html/template writes "+" as &#43;,
// whitespace runs become one space, and the space next to a tag goes.
func normalise(s string) string {
	s = strings.ReplaceAll(s, "&#43;", "+")
	s = wsRun.ReplaceAllString(s, " ")
	s = afterTag.ReplaceAllString(s, ">")
	s = beforeTag.ReplaceAllString(s, "<")
	return strings.TrimSpace(s)
}

func goldenTemplates(t *testing.T) *Templates {
	t.Helper()
	tpl, err := Parse(nil, os.DirFS("testdata"), "golden_page.html")
	if err != nil {
		t.Fatal(err)
	}
	return tpl
}

func TestGoldenMatchesPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/golden_cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var file struct {
		Value     string         `json:"value"`
		MacroData map[string]any `json:"macro_data"`
		Cases     []goldenCase   `json:"cases"`
	}
	if err := json.Unmarshal(raw, &file); err != nil {
		t.Fatal(err)
	}
	if len(file.Cases) < 9 {
		t.Fatalf("want 9 cases, got %d", len(file.Cases))
	}
	tpl := goldenTemplates(t)
	for _, c := range file.Cases {
		t.Run(c.Name, func(t *testing.T) {
			want, err := os.ReadFile("testdata/" + c.Name + ".html")
			if err != nil {
				t.Fatal(err)
			}
			r := httptest.NewRequest(http.MethodGet, c.URL, nil)
			if c.Cookie != "" {
				r.Header.Set("Cookie", c.Cookie)
			}
			sh := goldenShell(c)
			p := Page{
				Title: c.Title, Nav: c.Nav, BodyKind: c.BodyKind, V2: c.V2, HideNav: !c.ShowNav,
				HowKey: c.HowKey, BackURL: c.BackURL, AdminWorkspace: c.AdminWorkspace,
				HideAlertStack: c.HideAlertStack, AlertsExpanded: c.AlertsExpanded, PhHidePin: c.PhHidePin,
				CelebrationMilestone: c.Celebration, SentGuestCount: c.SentGuestCount,
			}
			w := httptest.NewRecorder()
			caseEnv := func(k string) string {
				if k == "UBYHOST_BILLING_ENABLED" && c.BillingOn {
					return "1"
				}
				return getenv(k)
			}
			env := Env{Getenv: caseEnv, Now: time.Date(2026, 11, 13, 9, 0, 0, 0, time.UTC)}
			if err := render(w, r, env, sh, "GOLDEN-CSRF", p, tpl, "golden", map[string]any{"Value": file.Value, "M": file.MacroData}); err != nil {
				t.Fatal(err)
			}
			assertNoRawKeys(t, w.Body.String())
			got, exp := normalise(w.Body.String()), normalise(string(want))
			if got != exp {
				i := 0
				for i < len(got) && i < len(exp) && got[i] == exp[i] {
					i++
				}
				lo := max(0, i-120)
				t.Fatalf("differs at byte %d\n go: %s\n py: %s", i, got[lo:min(len(got), i+200)], exp[lo:min(len(exp), i+200)])
			}
			var lang *http.Cookie
			for _, ck := range w.Result().Cookies() {
				if ck.Name == "ubyhost_lang" {
					lang = ck
				}
			}
			if (lang != nil) != (c.SetCookie != "") {
				t.Fatalf("lang cookie: go %v, python %q", lang, c.SetCookie)
			}
			if lang != nil {
				py := fmt.Sprintf("ubyhost_lang=%s; Max-Age=%d; Path=/; SameSite=lax", lang.Value, lang.MaxAge)
				if py != c.SetCookie || lang.HttpOnly || lang.SameSite != http.SameSiteLaxMode {
					t.Fatalf("lang cookie %q, python %q", py, c.SetCookie)
				}
			}
			if ct := w.Header().Get("Content-Type"); ct != "text/html; charset=utf-8" {
				t.Fatalf("content type %q", ct)
			}
		})
	}
}

func TestConcurrentRendersKeepTheirLanguage(t *testing.T) {
	tpl := goldenTemplates(t)
	var wg sync.WaitGroup
	errs := make(chan error, 60)
	for i := 0; i < 60; i++ {
		lang := []string{"en", "cs", "vi"}[i%3]
		wg.Add(1)
		go func() {
			defer wg.Done()
			r := httptest.NewRequest(http.MethodGet, "/reservations?lang="+lang, nil)
			w := httptest.NewRecorder()
			sh := shell{SignedIn: true, WorkspaceName: "A", WorkspaceUsername: "a"}
			if err := render(w, r, Env{Getenv: getenv, Now: time.Now()}, sh, "tok", Page{Title: "x"}, tpl, "golden", map[string]any{"Value": lang, "M": map[string]any{}}); err != nil {
				errs <- err
				return
			}
			want := `<html lang="` + lang + `">`
			skip := Strings.T(lang, "a11y.skip_to_content", nil)
			if body := w.Body.String(); !strings.Contains(body, want) || !strings.Contains(body, skip) {
				errs <- fmt.Errorf("render for %s lost its language", lang)
			}
		}()
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		t.Fatal(err)
	}
}

func TestMacrosEscapeAndBind(t *testing.T) {
	c := &reqCtx{lang: "en", layout: Strings}
	h, err := c.uiButton(`<b>"x"</b>`, "primary", map[string]any{"href": "/a?b=1&c=2"})
	if err != nil {
		t.Fatal(err)
	}
	if want := `<a class="ui-btn ui-btn-primary" href="/a?b=1&amp;c=2"><span>&lt;b&gt;&#34;x&#34;&lt;/b&gt;</span></a>`; string(h) != want {
		t.Fatalf("ui_button = %s", h)
	}
	if _, err := c.uiButton("x", map[string]any{"nope": 1}); err == nil {
		t.Fatal("unknown keyword accepted")
	}
	if _, err := icon("no-such-icon"); err == nil {
		t.Fatal("unknown icon accepted")
	}
	if _, err := kv("a"); err == nil {
		t.Fatal("odd kv accepted")
	}
	if got := c.tp("nav.property_count", 1); got != Strings.T("en", "nav.property_count.one", map[string]any{"count": 1}) {
		t.Fatalf("tp one = %q", got)
	}
	if got := c.t("no.such.key"); got != "no.such.key" {
		t.Fatalf("missing key = %q", got)
	}
	page := hostweb.Catalog{"en": {"nav.stays": "Page stays"}}
	c.page = page
	if got := c.t("nav.stays"); got != "Page stays" {
		t.Fatalf("page catalog not first: %q", got)
	}
	if got := truncate("Some help text that is rather long so the truncate filter has to cut it off", 50); got != "Some help text that is rather long so the..." {
		t.Fatalf("truncate = %q", got)
	}
	if got := datetimeLocal("2026-07-01T10:00:00"); got != "2026-07-01 12:00" {
		t.Fatalf("datetime_local summer = %q", got)
	}
	if got := datetimeLocal("not a date at all"); got != "not a date at al" {
		t.Fatalf("datetime_local raw = %q", got)
	}
}

func TestMinutesLeft(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	h := &session.Host{Impersonating: true, Payload: map[string]any{"ast": int64(now.Unix() - 61)}}
	env := map[string]string{"UBYHOST_IMPERSONATION_MAX_HOURS": "1"}
	if m := minutesLeft(h, func(k string) string { return env[k] }, now); m == nil || *m != 59 {
		t.Fatalf("minutes = %v", m)
	}
	env["UBYHOST_IMPERSONATION_MAX_HOURS"] = "0"
	if m := minutesLeft(h, func(k string) string { return env[k] }, now); m != nil {
		t.Fatal("no limit must be nil")
	}
	h.Impersonating = false
	if minutesLeft(h, getenv, now) != nil {
		t.Fatal("outside an impersonation must be nil")
	}
}

func TestCSRFTokenBindsTheNonceCookie(t *testing.T) {
	now := time.Now()
	r := httptest.NewRequest(http.MethodGet, "/", nil)
	token, cookie, err := csrfToken(r, "s3cret", getenv, now)
	if err != nil || cookie == nil || !cookie.HttpOnly || cookie.SameSite != http.SameSiteStrictMode || len(cookie.Value) != 43 {
		t.Fatalf("new nonce: %v %+v", err, cookie)
	}
	var payload map[string]any
	if err := secure.NewTimedSerializer("s3cret", csrfSalt).Loads(token, time.Hour, now, &payload); err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256([]byte(cookie.Value))
	if payload["nonce"] != hex.EncodeToString(sum[:]) {
		t.Fatal("token not bound to the cookie nonce")
	}
	r.AddCookie(cookie)
	if _, again, _ := csrfToken(r, "s3cret", getenv, now); again != nil {
		t.Fatal("a request with a nonce must not get a new cookie")
	}
}

func TestShellQuery(t *testing.T) {
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Skip("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_layout_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err == nil {
			_, _ = c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)")
			c.Close(context.Background())
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal(err)
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()
	now := time.Now()
	stamp := func(d time.Duration) string { return now.Add(d).UTC().Format("2006-01-02T15:04:05") }
	nowF := float64(now.UnixNano()) / 1e9
	for _, q := range []string{
		`CREATE TABLE user_account (id BIGINT PRIMARY KEY, username TEXT, display_name TEXT, deletion_due_at TEXT,
			email TEXT, two_factor_prompted_at TEXT, totp_enabled INTEGER NOT NULL DEFAULT 0, signup_at TEXT)`,
		`CREATE TABLE apartment (id BIGINT PRIMARY KEY, owner_user_id BIGINT, archived_at TEXT, internal_name TEXT)`,
		`CREATE TABLE billing_account (owner_user_id BIGINT PRIMARY KEY, status TEXT NOT NULL, plan TEXT, trial_ends_at TEXT, period_end TEXT)`,
		`CREATE TABLE reservation (id BIGINT PRIMARY KEY, apartment_id BIGINT, date_from TEXT, date_to TEXT,
			declared_guests INTEGER, expected_guests_override INTEGER, lead_reduced_guests INTEGER)`,
		`CREATE TABLE alert (id BIGINT PRIMARY KEY, level TEXT NOT NULL, kind TEXT NOT NULL, apartment_id INTEGER, reservation_id INTEGER,
			owner_user_id INTEGER, dedupe_key TEXT, message TEXT NOT NULL, detail TEXT, created_at TEXT NOT NULL, resolved_at TEXT, params TEXT)`,
		`CREATE TABLE guest (id BIGINT PRIMARY KEY, reservation_id BIGINT, is_lead INTEGER NOT NULL DEFAULT 0, archived_at TEXT,
			nationality TEXT, submit_state TEXT, manual_filed_at TEXT, submitted_at TEXT, identity_verified_at TEXT,
			stay_from TEXT, stay_to TEXT, surname TEXT, first_name TEXT, res_country TEXT, purpose TEXT, note TEXT,
			doc_number TEXT, doc_number_enc TEXT, visa_number TEXT, visa_number_enc TEXT, birth_date TEXT, birth_date_enc TEXT,
			res_street TEXT, res_street_enc TEXT, res_city TEXT, res_city_enc TEXT, signature_png TEXT, signature_png_enc TEXT)`,
		`CREATE TABLE rate_limit_event (id BIGSERIAL PRIMARY KEY, scope TEXT NOT NULL, key TEXT NOT NULL, at DOUBLE PRECISION NOT NULL)`,
		`INSERT INTO user_account (id, username, display_name, deletion_due_at, email) VALUES
			(1, 'admin-1', 'Admin', NULL, 'Boss@x.cz'), (2, 'host-2', NULL, '2026-12-01T10:00:00', 'host@x.cz')`,
		`INSERT INTO apartment VALUES (1, 2, NULL, 'Flat A'), (2, 2, NULL, 'Flat B'), (3, 2, '2026-01-01', 'Old'), (4, 1, NULL, 'Admin flat')`,
		`INSERT INTO billing_account VALUES (2, 'trialing', NULL, '2099-01-01T00:00:00', NULL), (1, 'active', 'standard', NULL, NULL)`,
		`INSERT INTO reservation VALUES (10, 1, '2026-11-05', '2026-11-09', 2, NULL, NULL), (11, 2, '2026-11-05', '2026-11-09', 1, NULL, NULL)`,
		`INSERT INTO guest (id, reservation_id, surname, stay_from) VALUES (100, 10, 'Novak', '2026-11-04')`,
		`INSERT INTO guest (id, reservation_id, surname, doc_number_enc) VALUES (101, 11, 'Unreadable', 'not-a-fernet-token')`,
		`INSERT INTO alert (id, level, kind, apartment_id, reservation_id, owner_user_id, dedupe_key, message, created_at, resolved_at) VALUES
			(1, 'warning', 'deadline', 2, 11, 2, 'deadline:11', 'log 1', '` + stamp(-4*time.Hour) + `', NULL),
			(2, 'critical', 'deadline', 1, 10, 2, 'deadline:10', 'log 2', '` + stamp(-3*time.Hour) + `', NULL),
			(3, 'critical', 'job_failed', NULL, NULL, NULL, 'job_failed:submit', 'log 3', '` + stamp(-2*time.Hour) + `', NULL),
			(4, 'critical', 'deadline', 4, NULL, 1, 'x', 'other workspace', '` + stamp(-time.Hour) + `', NULL),
			(5, 'critical', 'feed_error', 1, NULL, 2, 'y', 'resolved', '` + stamp(-time.Hour) + `', '` + stamp(0) + `'),
			(6, 'warning', 'feed_incomplete', 2, NULL, 2, 'z', 'log 6', '` + stamp(-time.Minute) + `', NULL)`,
		fmt.Sprintf(`INSERT INTO rate_limit_event (scope, key, at) SELECT 'havel_week', '1', %f FROM generate_series(1, 8)`, nowF-60),
		fmt.Sprintf(`INSERT INTO rate_limit_event (scope, key, at) SELECT 'havel_burst', '1', %f FROM generate_series(1, 9)`, nowF-7200),
	} {
		if _, err := pool.Exec(ctx, q); err != nil {
			t.Fatal(err)
		}
	}
	dbEnv := func(k string) string {
		switch k {
		case "UBYHOST_AI_FEATURES":
			return "havel"
		case "UBYHOST_ANTHROPIC_API_KEY":
			return "test-key"
		case "UBYHOST_BILLING_ENABLED":
			return "1"
		}
		return getenv(k)
	}
	h := &session.Host{
		Account:       session.Account{ID: 1, Username: "admin-1", Role: "admin"},
		Workspace:     session.Account{ID: 2, Username: "host-2", Role: "host"},
		Impersonating: true, Payload: map[string]any{},
	}
	sh, err := loadShell(ctx, httptest.NewRequest(http.MethodGet, "/reservations", nil), Env{Pool: pool, Getenv: dbEnv, Now: now}, h)
	if err != nil {
		t.Fatal(err)
	}
	if sh.WorkspaceName != "host-2" || sh.PropertyCount != 2 || sh.DeletionDueAt != "2026-12-01T10:00:00" || !sh.IsAdmin || !sh.Impersonating {
		t.Fatalf("shell = %+v", sh)
	}
	var ids []int64
	for _, a := range sh.Alerts {
		ids = append(ids, a.ID)
	}
	if fmt.Sprint(ids) != "[3 2 6 1]" {
		t.Fatalf("open alerts %v, want critical first then newest", ids)
	}
	if a := sh.Alerts[1]; a.Stay == nil || a.Stay.Property != "Flat A" || sh.Alerts[2].FeedProperty != "Flat B" {
		t.Fatalf("joined stay/feed property: %+v %+v", a.Stay, sh.Alerts[2])
	}
	exp := 2
	if p := sh.Progress[10]; p.Unreadable || p.Status != "incomplete" || p.Filled != 0 || p.Expected == nil || *p.Expected != exp || p.Incomplete != 1 ||
		p.Anchor.Format("2006-01-02") != "2026-11-04" {
		t.Fatalf("progress 10 = %+v", p)
	}
	if !sh.Progress[11].Unreadable {
		t.Fatalf("progress 11 = %+v, want unreadable", sh.Progress[11])
	}
	if !sh.HavelOn || sh.HavelState != "limit_week" || sh.Billing.Status != "trialing" || sh.TwoFactorDone || sh.AccountIsWorkspace || sh.AccountID != 1 {
		t.Fatalf("shell 1381 = on %v state %q billing %+v 2fa %v", sh.HavelOn, sh.HavelState, sh.Billing, sh.TwoFactorDone)
	}
	getenv := dbEnv
	w := httptest.NewRecorder()
	r := httptest.NewRequest(http.MethodGet, "/reservations", nil)
	env := Env{Pool: pool, Getenv: getenv, Now: time.Now()}
	if err := Render(w, r, env, h, Page{Title: "T", Status: http.StatusNotFound}, goldenTemplates(t), "golden", map[string]any{"Value": "v", "M": map[string]any{}}); err != nil {
		t.Fatal(err)
	}
	body := w.Body.String()
	if w.Code != http.StatusNotFound || !strings.Contains(body, "@host-2") || !strings.Contains(body, `name="csrf-token" content="`) {
		t.Fatalf("Render: %d", w.Code)
	}
	for _, want := range []string{`data-alert-id="2"`, `data-alert-id="3"`, "Overdue", `data-billing-banner="trial"`, `id="havel-sheet"`, "havel-status"} {
		if !strings.Contains(body, want) {
			t.Errorf("Render body lacks %q", want)
		}
	}
	assertNoRawKeys(t, body)
	if !strings.Contains(w.Header().Get("Set-Cookie"), "ubyhost_csrf=") {
		t.Fatal("Render did not set the CSRF nonce cookie")
	}
	if err := Render(w, r, env, h, Page{}, goldenTemplates(t), "missing", nil); err == nil {
		t.Fatal("unknown page template accepted")
	}
}
