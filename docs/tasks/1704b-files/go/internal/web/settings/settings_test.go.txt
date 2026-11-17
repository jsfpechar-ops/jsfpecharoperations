package settings

// Tests of GET /settings and GET /settings/{account,data,technical,help}
// (brief 1704b). The expected strings are written by hand from the seed below
// and the host catalog; there is no Python golden file.

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

const testSecret = "settings-test-secret-key-0123456789abcdef"

// testNow is after 31 January 2027, so the cutoff is 1 January 2020 and a
// record that ended in 2020 reaches it within the 30 day notice window.
var testNow = time.Date(2027, 1, 10, 12, 0, 0, 0, time.UTC)

// baseEnv is the environment of every request; a test adds to a copy.
func baseEnv() map[string]string {
	return map[string]string{"UBYHOST_SECRET_KEY": testSecret}
}

func getenvOf(env map[string]string) func(string) string {
	return func(k string) string { return env[k] }
}

// testPool makes a throwaway database from UBYHOST_TEST_DATABASE_URL and
// applies the Postgres migrations. The tests are never skipped silently: a
// missing URL fails them.
func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	base := os.Getenv("UBYHOST_TEST_DATABASE_URL")
	if base == "" {
		t.Fatal("UBYHOST_TEST_DATABASE_URL is not set")
	}
	ctx := context.Background()
	name := fmt.Sprintf("ubyhost_go_settings_%d", time.Now().UnixNano())
	admin, err := pgx.Connect(ctx, base)
	if err != nil {
		t.Fatal("admin connect failed")
	}
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+name); err != nil {
		admin.Close(ctx)
		t.Fatal(err)
	}
	admin.Close(ctx)
	t.Cleanup(func() {
		c, err := pgx.Connect(context.Background(), base)
		if err != nil {
			t.Errorf("admin connect for cleanup failed")
			return
		}
		defer c.Close(context.Background())
		if _, err := c.Exec(context.Background(), "DROP DATABASE IF EXISTS "+name+" WITH (FORCE)"); err != nil {
			t.Errorf("drop test database: %v", err)
		}
	})
	cfg, err := pgxpool.ParseConfig(base)
	if err != nil {
		t.Fatal("bad UBYHOST_TEST_DATABASE_URL")
	}
	cfg.ConnConfig.Database = name
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	files, err := filepath.Glob("../../../../App/migrations_pg/*.sql")
	if err != nil || len(files) == 0 {
		t.Fatal("no migrations found")
	}
	sort.Strings(files)
	for _, f := range files {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		up := string(raw)
		if i := strings.Index(up, "-- +goose Down"); i >= 0 {
			up = up[:i]
		}
		if _, err := pool.Exec(ctx, up); err != nil {
			t.Fatalf("migration %s: %v", f, err)
		}
	}
	return pool
}

const stamp = `'2026-01-01T00:00:00+00:00'`

// seed writes admin 1 and hosts 2 and 3 and what the pages read. Host 2 is the
// workspace the tests look at; host 3 owns the rows that must never show up
// there.
//
//	host 2: one business "Entity Two s.r.o." without contact e-mail (and an
//	  archived one that is ignored), property
//	  10 "Alpha Flat" (no business, a stay fee), property 11 "Bravo House" (with
//	  the business); guests: 1001 expired (ended 2019), 1002 expired and
//	  archived, 1003 due (ended 2020); two open data requests, one closed;
//	  a Google consent given and a Meta consent withdrawn; audit rows a1-a3.
//	host 3: businesses "Foreign Entity" (no contact) and "Foreign Two", property 20 "Zulu Villa"
//	  (no business), 2 expired and 1 due guest, 1 open request, audit row a4.
func seed(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	exec := func(sql string, args ...any) {
		t.Helper()
		if _, err := pool.Exec(ctx, sql, args...); err != nil {
			t.Fatalf("%s: %v", sql, err)
		}
	}
	for _, a := range []struct {
		id                                   int64
		name, role, display, email, mail, ob string
	}{
		{1, "admin_one", "admin", "Ada Admin", "ada@example.test", "0", "0"},
		{2, "host_two", "host", "Hana Host", "hana@example.test", "1", "0"},
		{3, "host_three", "host", "", "", "0", "1"},
	} {
		exec(`INSERT INTO user_account (id, username, password_hash, created_at, role, active, session_version, display_name, email, guest_details_mail, onboarding_emails_opt_out)
			VALUES ($1, $2, 'x', `+stamp+`, $3, 1, 1, NULLIF($4, ''), NULLIF($5, ''), $6::bigint, $7::bigint)`, a.id, a.name, a.role, a.display, a.email, a.mail, a.ob)
		for doc, ver := range map[string]string{"terms": "1.7", "privacy": "1.8", "dpa": "1.8"} {
			exec(`INSERT INTO legal_acceptance (user_account_id, document, version, accepted_at, method) VALUES ($1, $2, $3, `+stamp+`, 'clickwrap')`, a.id, doc, ver)
		}
	}
	exec(`INSERT INTO legal_entity (id, name, owner_user_id, contact_email, created_at) VALUES (5, 'Entity Two s.r.o.', 2, '', ` + stamp + `), (6, 'Foreign Entity', 3, NULL, ` + stamp + `), (7, 'Foreign Two', 3, 'two@example.test', ` + stamp + `)`)
	exec(`INSERT INTO legal_entity (id, name, owner_user_id, contact_email, created_at, archived_at) VALUES (8, 'Archived Biz', 2, '', ` + stamp + `, ` + stamp + `)`)
	for _, a := range []struct {
		id      int64
		name    string
		owner   int64
		entity  any
		feeRate int
	}{{10, "Alpha Flat", 2, nil, 50}, {11, "Bravo House", 2, 5, 0}, {20, "Zulu Villa", 3, nil, 0}} {
		exec(`INSERT INTO apartment (id, internal_name, owner_user_id, legal_entity_id, stay_fee_rate_czk, created_at) VALUES ($1, $2, $3, $4, $5, `+stamp+`)`, a.id, a.name, a.owner, a.entity, a.feeRate)
	}
	for _, r := range []struct{ id, apartment int64 }{{100, 10}, {101, 11}, {200, 20}} {
		exec(`INSERT INTO reservation (id, apartment_id, source, uid, date_from, date_to, created_at, updated_at) VALUES ($1, $2, 'manual', $3, '2019-06-01', '2019-06-02', `+stamp+`, `+stamp+`)`,
			r.id, r.apartment, fmt.Sprintf("uid-%d", r.id))
	}
	for _, g := range []struct {
		id, res  int64
		stayTo   string
		archived any
	}{
		{1001, 100, "2019-06-02", nil}, {1002, 101, "2019-12-31", "2026-01-02T00:00:00+00:00"}, {1003, 100, "2020-05-05", nil},
		{2001, 200, "2018-01-01", nil}, {2002, 200, "2019-01-01", nil}, {2003, 200, "2020-02-02", nil},
	} {
		exec(`INSERT INTO guest (id, reservation_id, surname, first_name, submit_state, stay_to, archived_at, created_at, updated_at) VALUES ($1, $2, 'S', 'F', 'pending', $3, $4, `+stamp+`, `+stamp+`)`,
			g.id, g.res, g.stayTo, g.archived)
	}
	for _, r := range []struct {
		id, owner int64
		status    string
	}{{1, 2, "open"}, {2, 2, "extended"}, {3, 2, "fulfilled"}, {4, 3, "open"}} {
		exec(`INSERT INTO data_subject_request (id, owner_user_id, received_at, due_at, channel, request_type, subject_kind, status, created_at, updated_at)
			VALUES ($1, $2, `+stamp+`, `+stamp+`, 'email', 'access', 'guest', $3, `+stamp+`, `+stamp+`)`, r.id, r.owner, r.status)
	}
	exec(`INSERT INTO consent_texts (id, version, purpose, lang, text, text_sha256, created_at) VALUES (1, '1', 'ads', 'en', 'x', 'h', ` + stamp + `)`)
	exec(`INSERT INTO ad_click (user_account_id, platform, clicked_at, consent_text_id, consented_at, withdrawn_at, created_at) VALUES
		(2, 'meta', '2026-03-01T00:00:00+00:00', 1, '2026-03-01T08:30:00+00:00', '2026-04-01T09:15:00+00:00', ` + stamp + `),
		(2, 'google', '2026-02-01T00:00:00+00:00', 1, '2026-02-01T10:00:00+00:00', NULL, ` + stamp + `),
		(3, 'google', '2026-02-01T00:00:00+00:00', 1, '2026-02-02T10:00:00+00:00', NULL, ` + stamp + `)`)
	exec(`INSERT INTO settings (key, value) VALUES ('retention_last_run', '{"dry_run": false, "owner_user_id": 2, "counts": {"guests": 3, "invoices": 0, "audit": 12}, "at": "2026-12-01T03:00:00+00:00"}')`)
	for _, a := range []struct {
		id         int64
		at         string
		actor      any
		action     string
		detail     any
		owner, imp any
	}{
		{1, "2026-12-01T09:00:05+00:00", "host_two", "login", "ok", 2, nil},
		{2, "2026-12-02T09:00:05+00:00", "admin_one", "impersonation_started", nil, 2, 1},
		{3, "2026-12-03T09:00:05+00:00", "host_two", "guest_identity_revealed", "guest 1001", 2, nil},
		{4, "2026-12-04T09:00:05+00:00", "host_three", "foreign_action", "secret-of-host-three", 3, nil},
		{5, "2026-12-05T09:00:05+00:00", "system", "ownerless_action", "no owner", nil, nil},
	} {
		exec(`INSERT INTO audit (id, at, actor, action, detail, owner_user_id, impersonator_user_id) VALUES ($1, $2, $3, $4, $5, $6, $7)`,
			a.id, a.at, a.actor, a.action, a.detail, a.owner, a.imp)
	}
	exec(`INSERT INTO codelist (kind, code, fetched_at) VALUES ('staty', 'CZE', '2026-11-01T10:00:00+00:00'), ('staty', 'DEU', '2026-10-01T10:00:00+00:00'), ('ucely', '10', '2026-11-02T11:30:15+00:00')`)
}

// seedConsoleMail adds two console mails of host 2 (one with a claim secret
// that must be put back, one with HTML) and one of host 3.
func seedConsoleMail(t *testing.T, pool *pgxpool.Pool) {
	t.Helper()
	ctx := context.Background()
	keys, err := secure.LoadDataKeys(getenvOf(baseEnv()))
	if err != nil {
		t.Fatal(err)
	}
	token, err := keys.EncryptString("CLAIM-SECRET-0123456789")
	if err != nil {
		t.Fatal(err)
	}
	for _, m := range []struct {
		id, owner         int64
		to, subject, text string
		html, payload     any
	}{
		{1, 2, "guest@example.test", "Your link", "Open https://x.test/#c={{claim_secret}} now", nil, `{"claim_secret_enc": "` + token + `"}`},
		{2, 2, "other@example.test", "With html", "plain body", `<p onclick="x()">Hello & <b>bye</b></p>`, `{}`},
		{3, 3, "foreign@example.test", "Foreign subject", "foreign body", nil, `{}`},
	} {
		if _, err := pool.Exec(ctx, `INSERT INTO email_outbox (id, idempotency_key, kind, owner_user_id, to_email, subject, payload, state, created_at, updated_at)
			VALUES ($1, $2, 'test', $3, $4, $5, $6, 'sent', `+stamp+`, `+stamp+`)`, m.id, fmt.Sprintf("k%d", m.id), m.owner, m.to, m.subject, m.payload); err != nil {
			t.Fatal(err)
		}
		if _, err := pool.Exec(ctx, `INSERT INTO console_mail_log (id, outbox_id, to_email, subject, body_text, body_html, created_at) VALUES ($1, $1, $2, $3, $4, $5, `+stamp+`)`,
			m.id, m.to, m.subject, m.text, m.html); err != nil {
			t.Fatal(err)
		}
	}
}

var groupOf = map[string]string{
	"/settings": "", "/settings/account": "account", "/settings/data": "data",
	"/settings/technical": "technical", "/settings/help": "help",
}

// req sends GET target as user (0: signed out) with the language cookie lang;
// as is the workspace an admin previews (0: none).
func req(t *testing.T, pool *pgxpool.Pool, env map[string]string, target string, user, as int64, lang string) *httptest.ResponseRecorder {
	t.Helper()
	r := httptest.NewRequest(http.MethodGet, target, nil)
	r.AddCookie(&http.Cookie{Name: "ubyhost_lang", Value: lang})
	if user != 0 {
		payload := map[string]any{"uid": user, "sv": 1}
		if as != 0 {
			payload["as"] = as
			payload["ast"] = testNow.Unix()
		}
		r.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, payload, testNow)})
	}
	path := target
	if i := strings.Index(path, "?"); i >= 0 {
		path = path[:i]
	}
	group, ok := groupOf[path]
	if !ok {
		t.Fatalf("no group for %s", path)
	}
	rec := httptest.NewRecorder()
	Handler(pool, getenvOf(env), func() time.Time { return testNow }, group).ServeHTTP(rec, r)
	return rec
}

func page(t *testing.T, pool *pgxpool.Pool, target string, user, as int64, lang string) string {
	t.Helper()
	rec := req(t, pool, baseEnv(), target, user, as, lang)
	if rec.Code != http.StatusOK {
		t.Fatalf("%s as %d: status %d, body %.200s", target, user, rec.Code, rec.Body.String())
	}
	return rec.Body.String()
}

func mustContain(t *testing.T, name, body string, want ...string) {
	t.Helper()
	for _, w := range want {
		if !strings.Contains(body, w) {
			t.Errorf("%s: missing %q", name, w)
		}
	}
}

func mustNotContain(t *testing.T, name, body string, banned ...string) {
	t.Helper()
	for _, b := range banned {
		if strings.Contains(body, b) {
			t.Errorf("%s: must not contain %q", name, b)
		}
	}
}

// from is body from the first marker to the end of the page's main block, so a
// count does not include the forms of the shell.
func from(t *testing.T, body, marker string) string {
	t.Helper()
	i := strings.Index(body, marker)
	if i < 0 {
		t.Fatalf("no %q in the page", marker)
	}
	body = body[i:]
	if j := strings.Index(body, "</main>"); j >= 0 {
		body = body[:j]
	}
	return body
}

// inOrder fails when the strings do not appear in this order.
func inOrder(t *testing.T, name, body string, parts ...string) {
	t.Helper()
	last := -1
	for _, p := range parts {
		i := strings.Index(body, p)
		if i < 0 {
			t.Errorf("%s: missing %q", name, p)
			return
		}
		if i < last {
			t.Errorf("%s: %q is out of order", name, p)
		}
		last = i
	}
}

func TestGroupsOrderAndVersion(t *testing.T) {
	if got := strings.Join(Groups, ","); got != "account,security,phone,data,technical,help" {
		t.Errorf("Groups = %s", got)
	}
	raw, err := os.ReadFile("../../../../App/app/__init__.py")
	if err != nil {
		t.Fatal(err)
	}
	if want := `__version__ = "` + appVersion + `"`; !strings.Contains(string(raw), want) {
		t.Errorf("appVersion %q is not App/app/__init__.py %s", appVersion, strings.SplitN(string(raw), "\n", 2)[0])
	}
}

func TestParseLastRunKeepsOrder(t *testing.T) {
	lr := parseLastRun(`{"dry_run": true, "owner_user_id": null, "counts": {"zeta": 2, "alpha": 10}, "at": "2026-01-01T00:00:00+00:00"}`)
	if lr == nil || lr.At != "2026-01-01T00:00:00+00:00" || !lr.DryRun || lr.Counts != "zeta=2 alpha=10" {
		t.Errorf("parseLastRun = %+v", lr)
	}
	if parseLastRun("nonsense") != nil {
		t.Error("nonsense must give nil")
	}
	if got := capitalize("sTAGING"); got != "Staging" {
		t.Errorf("capitalize = %q", got)
	}
}

func TestSettingsSignedOut(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	for _, target := range []string{"/settings", "/settings/account", "/settings/data", "/settings/technical", "/settings/help"} {
		rec := req(t, pool, baseEnv(), target, 0, 0, "en")
		if rec.Code != http.StatusSeeOther && rec.Code != http.StatusFound {
			t.Fatalf("%s: status %d, want a redirect", target, rec.Code)
		}
		if loc := rec.Header().Get("Location"); loc != "/login?next="+target {
			t.Errorf("%s: Location %q", target, loc)
		}
	}
}

func TestSettingsUnknownGroup(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	r := httptest.NewRequest(http.MethodGet, "/settings/nonsense", nil)
	r.AddCookie(&http.Cookie{Name: session.CookieName, Value: session.Sign(testSecret, map[string]any{"uid": int64(2), "sv": 1}, testNow)})
	rec := httptest.NewRecorder()
	Handler(pool, getenvOf(baseEnv()), func() time.Time { return testNow }, "nonsense").ServeHTTP(rec, r)
	if rec.Code != http.StatusNotFound {
		t.Errorf("status %d, want 404", rec.Code)
	}
}

// TestSettingsIndex is GET /settings: no group body, only the index in Python's order.
func TestSettingsIndex(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	rec := req(t, pool, baseEnv(), "/settings", 2, 0, "en")
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	if got := rec.Header().Get("Cache-Control"); got != "no-store, private" {
		t.Errorf("Cache-Control %q", got)
	}
	body := rec.Body.String()
	mustContain(t, "index", body,
		`<title>Settings`,
		`<a class="airbnb-back" href="/" aria-label="Back">`,
		`<h1 class="airbnb-title">Settings</h1>`,
		`<div class="settings-lane">`,
		`<nav class="airbnb-index" aria-label="Settings">`,
		`<div class="settings-groups">`,
	)
	inOrder(t, "index", body,
		`href="/settings/account"`, `<span class="airbnb-label">Account</span>`,
		`href="/settings/security"`, `<span class="airbnb-label">Security</span>`,
		`href="/settings/phone"`, `<span class="airbnb-label">Phone app</span>`,
		`href="/settings/data"`, `<span class="airbnb-label">Data &amp; archive</span>`,
		`<div class="airbnb-divider" aria-hidden="true"></div>`,
		`href="/entities"`, `<span class="airbnb-label">Business &amp; legal details</span>`,
		`href="/privacy-requests"`, `<span class="airbnb-label">Data requests</span>`,
		`href="/settings/archived"`, `<span class="airbnb-label">Archive</span>`,
		`href="/settings/technical"`, `<span class="airbnb-label">Technical</span>`,
		`href="/settings/help"`, `<span class="airbnb-label">Help</span>`,
	)
	if n := strings.Count(body, `class="airbnb-index-row"`); n != 9 {
		t.Errorf("index rows = %d, want 9", n)
	}
	mustNotContain(t, "index", body, `settings-group-account`, `settings-group-data`, `settings-group-technical`, `settings-group-help`, `id="settings-audit"`)
}

func TestSettingsAccount(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	body := page(t, pool, "/settings/account", 2, 0, "en")
	mustContain(t, "host 2", body,
		`<a class="airbnb-back" href="/settings" aria-label="Back">`,
		`<h1 class="airbnb-title">Account</h1>`,
		`<section class="settings-group" id="settings-group-account" aria-labelledby="settings-group-account-title"><h2 class="settings-group-title sec" id="settings-group-account-title">Account</h2>`,
		`<div class="account-identity">
        <strong>Hana Host</strong>`,
		`<strong>Login e-mail</strong>
            <small>hana@example.test</small>`,
		`<form method="post" action="/account/email" class="settings-move-form settings-email-form">`,
		`<label for="account-new-email">New login e-mail`,
		`<input id="account-new-email" name="email" type="email" required maxlength="254"`,
		// one business: its editor opens directly
		`href="/entities?edit=5&amp;next=/settings"`,
		`<form method="post" action="/account/onboarding-emails" class="settings-toggle-form" id="settings-onboarding-emails">`,
		`aria-label="Setup tips by e-mail" checked>`,
		`<form method="post" action="/account/stay-fee-emails" class="settings-toggle-form" id="settings-stay-fee-emails">`,
		`aria-label="Stay fee report by email" checked>`,
		`<form method="post" action="/account/guest-details-mail" class="settings-toggle-form" id="settings-guest-details-mail">`,
		`aria-label="Guest details in the confirmation e-mail" checked>`,
	)
	// Every form carries the CSRF field; there are four.
	sec := from(t, body, `id="settings-group-account"`)
	if n := strings.Count(sec, `<form method="post"`); n != 4 {
		t.Errorf("forms = %d, want 4", n)
	}
	if n := strings.Count(sec, `<input type="hidden" name="_csrf" value="`); n != 4 {
		t.Errorf("_csrf inputs = %d, want 4", n)
	}
	mustNotContain(t, "host 2", sec, "/admin/customers", "/admin/incidents", "/predplatne", "Foreign Entity", "Ada Admin", "Archived Biz")

	// Billing on: the plan row opens.
	env := baseEnv()
	env["UBYHOST_BILLING_ENABLED"] = "1"
	rec := req(t, pool, env, "/settings/account", 2, 0, "en")
	mustContain(t, "billing", rec.Body.String(), `<a class="set-row" href="/predplatne"><span>Plan and billing</span><span class="set-row-v">Open</span></a>`)

	// Host 3: no display name and no e-mail (user name and "No login e-mail"),
	// two businesses (the list), onboarding tips off, no fee property so no fee
	// switch, guest details off.
	body3 := page(t, pool, "/settings/account", 3, 0, "en")
	mustContain(t, "host 3", body3,
		`<strong>host_three</strong>`,
		`<small>No login e-mail</small>`,
		`class="ui-btn ui-btn-secondary ui-btn-compact" href="/entities">Open business details</a>`,
		`aria-label="Setup tips by e-mail">`,
		`aria-label="Guest details in the confirmation e-mail">`,
	)
	sec3 := from(t, body3, `id="settings-group-account"`)
	mustNotContain(t, "host 3", sec3, `settings-stay-fee-emails`, `edit=`, `Hana Host`, `Entity Two`)

	// The admin: identity from the display name, the admin rows, and no
	// e-mail switches (they are for hosts).
	bodyA := page(t, pool, "/settings/account", 1, 0, "en")
	mustContain(t, "admin", bodyA,
		`<strong>Ada Admin</strong>`,
		`<a data-turbo="false" class="ui-btn ui-btn-secondary ui-btn-compact" href="/admin/customers">Manage users</a>`,
		`<a data-turbo="false" class="ui-btn ui-btn-secondary ui-btn-compact" href="/admin/incidents">View incidents</a>`,
	)
	mustNotContain(t, "admin", from(t, bodyA, `id="settings-group-account"`), `settings-onboarding-emails`, `settings-stay-fee-emails`, `settings-guest-details-mail`)

	// The admin looking at host 2's workspace: still the admin's own identity
	// and no switches (not their account), but host 2's business link.
	bodyP := page(t, pool, "/settings/account", 1, 2, "en")
	mustContain(t, "preview", bodyP, `<strong>Ada Admin</strong>`, `href="/entities?edit=5&amp;next=/settings"`, `href="/admin/customers"`)
	mustNotContain(t, "preview", from(t, bodyP, `id="settings-group-account"`), `settings-onboarding-emails`, `settings-stay-fee-emails`, `settings-guest-details-mail`, "Hana Host")
}

func TestSettingsData(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "backups"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "backups", ".last_success.json"), []byte(`{"at": "2026-12-31T02:00:00+00:00", "encrypted": true, "retention_days": 14}`), 0o600); err != nil {
		t.Fatal(err)
	}
	env := baseEnv()
	env["UBYHOST_DATA_DIR"] = dir
	get := func(user, as int64) string {
		rec := req(t, pool, env, "/settings/data", user, as, "en")
		if rec.Code != http.StatusOK {
			t.Fatalf("user %d: status %d", user, rec.Code)
		}
		return rec.Body.String()
	}
	body := get(2, 0)
	mustContain(t, "host 2", body,
		`<h1 class="airbnb-title">Data &amp; archive</h1>`,
		`id="settings-group-data-title">Data &amp; archive</h2>`,
		`<a class="ui-btn ui-btn-secondary" href="/settings/archived">`,
		`<span class="settings-value-label">Retention</span>
  <strong class="settings-value">6 years after the stay ends</strong>`,
		`<span class="settings-value-label">Delete anything ending before</span>
  <strong class="settings-value">01.01.2020</strong>`,
		// host 2: guest 1001 (2019-06-02) and the archived 1002 (2019-12-31) are past the cutoff
		`<span class="settings-value-label">Records past that date</span>
  <strong class="settings-value">2</strong>`,
		`<form method="post" action="/settings/purge-expired"
            data-confirm data-confirm-message="`,
		`<input type="hidden" name="_csrf" value="`,
		`<button class="ui-btn ui-btn-danger" type="submit">
          Delete 2 expired records`,
		// the last run is global; non-admins see when and how, not the counts
		`2026-12-01T03:00:00&#43;00:00,
              live`,
		// 1003 ended 2020-05-05: inside the 30 day window after the cutoff moves on 31 January
		`<dd><a href="/housebook">1 · open the house book</a></dd>`,
		`<dd><a href="/privacy-requests">2 open · manage</a></dd>`,
		// privacy: the property without a business and the business without a contact
		`<strong>The guest privacy notice is incomplete.</strong>`,
		`No operator on:
                
                  <a href="/apartments/10">Alpha Flat</a>`,
		`No contact e-mail on:
                Entity Two s.r.o..
                <a href="/entities">Add one</a> so guests can exercise their rights.`,
		// ad consents: Google first, then Meta, whatever the row order
		`<form method="post" action="/settings/privacy/ad-consent">`,
		`<input type="hidden" name="platform" value="google">`,
		`On since 2026-02-01 11:00.`,
		`<span class="ui-badge ui-badge-neutral" data-tone="grey">Off</span>`,
		`Off since 2026-04-01 11:15. The click identifier has been deleted.`,
	)
	inOrder(t, "consents", body, `Google Ads`, `On since 2026-02-01 11:00.`, `Facebook and Instagram`, `Off since 2026-04-01 11:15.`)
	mustNotContain(t, "host 2", body, "guests=3", "NOT encrypted", "Backup", "Zulu Villa", "Foreign Entity", "2026-02-02", `<a href="/apartments/11">`)
	// Two forms with a CSRF field each: purge and the one active consent.
	secD := from(t, body, `id="settings-group-data"`)
	if a, b := strings.Count(secD, `<form method="post"`), strings.Count(secD, `<input type="hidden" name="_csrf" value="`); a != 2 || b != 2 {
		t.Errorf("forms = %d, _csrf inputs = %d, want 2 and 2", a, b)
	}

	// Host 3: its own numbers (2 expired, 1 due, 1 open request), its own consent.
	body3 := get(3, 0)
	mustContain(t, "host 3", body3,
		`<strong class="settings-value">2</strong>`,
		`<dd><a href="/housebook">1 · open the house book</a></dd>`,
		`<dd><a href="/privacy-requests">1 open · manage</a></dd>`,
		`<a href="/apartments/20">Zulu Villa</a>`,
		`Foreign Entity.
                <a href="/entities">Add one</a>`,
		`On since 2026-02-02 11:00.`,
	)
	mustNotContain(t, "host 3", body3, "Alpha Flat", "Entity Two", "Facebook", "Foreign Two", "Archived Biz")

	// The admin: the counts of the last run and the backup marker.
	bodyA := get(1, 0)
	mustContain(t, "admin", bodyA,
		`guests=3 invoices=0 audit=12`,
		`<dt>Last backup</dt>`,
		`2026-12-31T02:00:00&#43;00:00,
              encrypted`,
		`kept 14 days`,
	)
	// Without the data directory there is no backup row, and a non-admin never has one.
	env["UBYHOST_DATA_DIR"] = ""
	mustNotContain(t, "no dir", get(1, 0), `<dt>Last backup</dt>`)
	env["UBYHOST_DATA_DIR"] = dir
	mustNotContain(t, "host with a marker", get(2, 0), `<dt>Last backup</dt>`)
}

func TestSettingsDataNothingToPurge(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	if _, err := pool.Exec(context.Background(), `DELETE FROM guest`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(context.Background(), `DELETE FROM settings`); err != nil {
		t.Fatal(err)
	}
	body := page(t, pool, "/settings/data", 2, 0, "en")
	mustContain(t, "empty", body, `Never run`, `<dd><a href="/housebook">0 · open the house book</a></dd>`)
	mustNotContain(t, "empty", body, `action="/settings/purge-expired"`)
}

func TestSettingsTechnical(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	body := page(t, pool, "/settings/technical", 2, 0, "en")
	mustContain(t, "host 2", body,
		`<h1 class="airbnb-title">Technical</h1>`,
		`<details class="ui-section technical" open id="settings-technical">
      <summary>Technical details</summary>`,
		// the guest PIN line is the default: required
		`<dd>Required (six digits per property)</dd>`,
		`<details class="ui-section technical" open id="settings-audit">`,
		`<h2>Recent activity (3 events)</h2>`,
		`<a class="settings-pill is-current" href="/settings/technical#settings-audit" aria-current="page">All activity</a>`,
		`<a class="settings-pill" href="/settings/technical?audit=support#settings-audit">Support sessions</a>`,
		`data-label="When">2026-12-03 10:00:05</td>`,
		`data-label="Who">admin_one <span class="ui-sub">(as admin admin_one)</span></td>`,
		`data-label="Action">impersonation_started</td>`,
		// a NULL detail prints as Jinja prints None
		`data-label="Detail">None</td>`,
		`data-label="Detail">guest 1001</td>`,
	)
	// Newest first: 3, 2, 1.
	inOrder(t, "audit", body, `guest_identity_revealed`, `impersonation_started`, `>login</td>`)
	// Not an admin: no destination, mail or codelist blocks; nothing of host 3 or of no owner.
	mustNotContain(t, "host 2", body, `id="settings-overview"`, `id="settings-mail"`, `id="settings-codelists"`,
		"foreign_action", "secret-of-host-three", "ownerless_action", "no owner")

	// The support filter keeps what an admin did and the three actions.
	rec := req(t, pool, baseEnv(), "/settings/technical?audit=support", 2, 0, "en")
	bs := rec.Body.String()
	mustContain(t, "support", bs,
		`<h2>Recent activity (2 events)</h2>`,
		`<a class="settings-pill" href="/settings/technical#settings-audit">All activity</a>`,
		`<a class="settings-pill is-current" href="/settings/technical?audit=support#settings-audit" aria-current="page">Support sessions</a>`,
		`impersonation_started`, `guest_identity_revealed`)
	mustNotContain(t, "support", bs, `>login</td>`)

	// Guest PIN off.
	env := baseEnv()
	env["UBYHOST_GUEST_PIN"] = "no"
	mustContain(t, "pin off", req(t, pool, env, "/settings/technical", 2, 0, "en").Body.String(), `<dt>PIN before the form</dt>`+"\n        "+`<dd>Off</dd>`)

	// An empty audit log.
	if _, err := pool.Exec(context.Background(), `DELETE FROM audit WHERE owner_user_id = 3`); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.Exec(context.Background(), `DELETE FROM audit WHERE owner_user_id = 2`); err != nil {
		t.Fatal(err)
	}
	bodyE := page(t, pool, "/settings/technical", 2, 0, "en")
	mustContain(t, "empty", bodyE, `<h2>Recent activity (0 events)</h2>`, `<td colspan="4" class="ui-sub">Nothing logged yet.</td>`)
}

func TestSettingsTechnicalAdmin(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	env := baseEnv()
	env["UBYHOST_DEPLOYMENT"] = "STAGING"
	env["UBYHOST_PUBLIC_BASE_URL"] = "https://app.example.test/"
	env["UBYHOST_ICAL_POLL_MINUTES"] = "15"
	env["UBYHOST_UBYPORT_ENV"] = "test"
	get := func(env map[string]string, as int64) string {
		rec := req(t, pool, env, "/settings/technical", 1, as, "en")
		if rec.Code != http.StatusOK {
			t.Fatalf("status %d", rec.Code)
		}
		return rec.Body.String()
	}
	body := get(env, 0)
	mustContain(t, "admin", body,
		`<h2 id="settings-overview">Where reports go`,
		`<dt>Deployment</dt><dd>Staging</dd>`,
		`<dt>UbyPort target</dt><dd>TEST</dd>`,
		`<dd class="ui-mono ui-sub">https://ubyport.pcr.cz/ws_uby_test/ws_uby.svc</dd>`,
		`<dt>Calendar polling</dt><dd>every 15 minutes</dd>`,
		`<dt>Submission sweep</dt><dd>every 10 minutes</dd>`,
		`<dd class="ui-mono ui-sub">https://app.example.test</dd>`,
		`<h2 id="settings-mail">`,
		`data-mail-backend="disabled">Sending is off: no guest e-mail leaves this installation.</p>`,
		`<dd class="ui-mono">disabled</dd>`,
		`<h2 id="settings-codelists">`,
		// the newest fetch of each list, in Prague time; the errors list was never fetched
		`<dt>Countries</dt><dd>2026-11-01 11:00:00</dd>`,
		`<dt>Purposes of stay</dt><dd>2026-11-02 12:30:15</dd>`,
		`<dt>Error codes</dt><dd>not fetched yet</dd>`,
	)
	mustNotContain(t, "admin test env", body, `Nothing is being reported to the police`)

	// Production target, the mock banner, SES, an unknown backend.
	env["UBYHOST_UBYPORT_ENV"] = "prod"
	mustContain(t, "prod", get(env, 0), `<dt>UbyPort target</dt><dd>Production</dd>`, `https://ubyport.pcr.cz/ws_uby/ws_uby.svc`)
	env["UBYHOST_UBYPORT_ENV"] = ""
	env["UBYHOST_MOCK_URL"] = "http://mock.test/uby"
	bodyM := get(env, 0)
	mustContain(t, "mock", bodyM, `<dt>UbyPort target</dt><dd>MOCK</dd>`, `<dd class="ui-mono ui-sub">http://mock.test/uby</dd>`,
		`<strong>Nothing is being reported to the police</strong>`, `<span class="ui-mono">UBYHOST_UBYPORT_ENV=test</span> or <span class="ui-mono">prod</span>`)
	env["UBYHOST_MAIL_BACKEND"] = "SES"
	mustContain(t, "ses", get(env, 0), `data-mail-backend="ses"`, `<dd class="ui-mono">ses</dd>`)
	env["UBYHOST_MAIL_BACKEND"] = "smtp"
	mustContain(t, "unknown", get(env, 0), `data-mail-backend="smtp">Mail status is unknown.</p>`)

	// An admin previewing host 2 reads host 2's audit log, not the admin's own.
	pBody := get(baseEnv(), 2)
	mustContain(t, "preview", pBody, `<h2>Recent activity (3 events)</h2>`, `<h2 id="settings-overview">`)
	mustNotContain(t, "preview", pBody, "foreign_action", "ownerless_action")
}

func TestSettingsTechnicalConsoleMail(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	seedConsoleMail(t, pool)
	env := baseEnv()
	env["UBYHOST_MAIL_BACKEND"] = "console"
	rec := req(t, pool, env, "/settings/technical", 2, 0, "en")
	body := rec.Body.String()
	// A host sees the mail block only on the console backend with messages, and no backend line.
	mustContain(t, "host 2", body,
		`<h2 id="settings-mail">`,
		`data-mail-backend="console">Not delivered: messages are kept below for claim links.</p>`,
		`<td class="ui-sub">guest@example.test</td>`,
		`<td class="ui-sub">Your link</td>`,
		// the claim secret is back in the body
		`<pre class="ui-sub ui-prewrap">Open https://x.test/#c=CLAIM-SECRET-0123456789 now</pre>`,
		`<td class="ui-sub">other@example.test</td>`,
		`<summary class="ui-sub">Preview the HTML e-mail</summary>`,
		`<iframe srcdoc="&lt;p onclick=&#34;x()&#34;&gt;Hello &amp; &lt;b&gt;bye&lt;/b&gt;&lt;/p&gt;" sandbox=""`,
	)
	mustNotContain(t, "host 2", body, `{{claim_secret}}`, `foreign@example.test`, `Foreign subject`, `<dt>Mail backend</dt>`, `id="settings-overview"`)
	inOrder(t, "newest first", body, `other@example.test`, `guest@example.test`)
	// The same messages as an admin of host 2's workspace: the backend line too.
	pbody := req(t, pool, env, "/settings/technical", 1, 2, "en").Body.String()
	mustContain(t, "preview", pbody, `<dd class="ui-mono">console</dd>`, `CLAIM-SECRET-0123456789`)
	mustNotContain(t, "preview", pbody, `foreign@example.test`)
	// Without a data key the marker stays standing instead of failing the page.
	envNoKey := map[string]string{"UBYHOST_MAIL_BACKEND": "console", "UBYHOST_SECRET_KEY": testSecret, "UBYHOST_DATA_KEYS": "not-a-key"}
	rec = req(t, pool, envNoKey, "/settings/technical", 2, 0, "en")
	if rec.Code != http.StatusOK {
		t.Fatalf("no key: status %d", rec.Code)
	}
	mustContain(t, "no key", rec.Body.String(), `Open https://x.test/#c={{claim_secret}} now`)
	// Console backend, no mail of host 3 to show: the host sees no mail block.
	if rec = req(t, pool, env, "/settings/technical", 3, 0, "en"); strings.Contains(rec.Body.String(), `id="settings-mail"`) == false {
		t.Error("host 3 has a console message of its own and must see the block")
	}
	if _, err := pool.Exec(context.Background(), `DELETE FROM console_mail_log WHERE outbox_id = 3`); err != nil {
		t.Fatal(err)
	}
	mustNotContain(t, "host 3 empty", req(t, pool, env, "/settings/technical", 3, 0, "en").Body.String(), `id="settings-mail"`)
	// Any other backend: a host sees no mail block even though messages exist.
	mustNotContain(t, "disabled", page(t, pool, "/settings/technical", 2, 0, "en"), `id="settings-mail"`)
}

func TestSettingsHelp(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	env := baseEnv()
	env["UBYHOST_OPERATOR_NAME"] = "Test Operator s.r.o."
	env["UBYHOST_OPERATOR_ICO"] = "12345678"
	env["UBYHOST_OPERATOR_ADDRESS"] = "Testovaci 1, Praha"
	env["UBYHOST_OPERATOR_EMAIL"] = "help@operator.test"
	rec := req(t, pool, env, "/settings/help", 2, 0, "en")
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	body := rec.Body.String()
	mustContain(t, "help", body,
		`<h1 class="airbnb-title">Help</h1>`,
		`<div class="settings-action-list">`,
		`href="/guide"`,
		`<dt>Registered address</dt><dd>Testovaci 1, Praha</dd>`,
		`<dt>UbyHost support</dt><dd><a href="mailto:help@operator.test">help@operator.test</a></dd>`,
		`<nav class="document-links" aria-label="Software operator">`,
		`<a href="/legal"><span>`, `<a href="/terms"><span>`, `<a href="/privacy"><span>`, `<a href="/dpa"><span>`,
		`<span class="settings-value-label">Version</span>
  <strong class="settings-value">1.1.0</strong>`,
	)
	// The legal help text names the operator and the company number.
	mustContain(t, "legal tip", body, `UbyHost is operated by Test Operator s.r.o., IČO 12345678.`)
	// The default operator e-mail.
	mustContain(t, "default", page(t, pool, "/settings/help", 2, 0, "en"), `<a href="mailto:support@ubyhost.com">support@ubyhost.com</a>`)
}

// TestSettingsLanguages checks the page title and group names in cs and vi.
func TestSettingsLanguages(t *testing.T) {
	pool := testPool(t)
	seed(t, pool)
	cs := page(t, pool, "/settings", 2, 0, "cs")
	mustContain(t, "cs", cs, `<title>Nastavení`, `<h1 class="airbnb-title">Nastavení</h1>`, `<span class="airbnb-label">Účet</span>`, `<span class="airbnb-label">Data a archiv</span>`)
	vi := page(t, pool, "/settings/technical", 2, 0, "vi")
	mustContain(t, "vi", vi, `<title>Cài đặt`, `<h1 class="airbnb-title">Kỹ thuật</h1>`, `<summary>Chi tiết kỹ thuật</summary>`)
	csData := page(t, pool, "/settings/data", 2, 0, "cs")
	mustContain(t, "cs data", csData, `6 let po skončení pobytu`, `Smazat 2 prošlé záznamy`, `Otevřené: 2 · spravovat`)
}
