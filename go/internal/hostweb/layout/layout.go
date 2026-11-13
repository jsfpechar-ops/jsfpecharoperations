// Package layout is the host page layout for Go page handlers: the port of
// App/app/templates/base.html, host_page.html and what they include
// (_seo_head, _env_banner, _shell_v2, _shell_sidebar, _shell_tabbar) plus the
// macros of _icons.html, _ui.html, _ui_layout.html and _components.html as
// template funcs under their Jinja names. App/app/templating.py render() is
// the reference for the shell context. Brief 1380.
//
// A page package parses its templates once with Parse (or MustParse) and calls
// Render per request. A page file defines {{define "<name>"}} (the host_page
// "body" block) and, when it needs them, the slots "<name>.title" (h1 HTML,
// default Page.Title), "<name>.meta", "<name>.primary", "<name>.secondary",
// "<name>.tabs", "<name>.toolbar", "<name>.head" (head_extra) and
// "<name>.back_label". Every slot runs with the same data.
//
// Brief 1381 added the rest of the shell: the host alert stack with the
// filing warnings (alerts.go), the billing line, the Havel panel and launchers,
// the security prompt and the celebration toast (shelldata.go). onboarding is
// not a shell value (only pages read it), so a page passes its own.
//
// CSRF: a page form takes its token from the csrf func ({{csrf}}). A page
// handler never mints a token of its own; Render binds the one token to the
// ubyhost_csrf nonce cookie.
//
// The safe func marks trusted HTML only (markup the handler built or a
// catalog string with markup); never pass it a value from the request, the
// database or a guest.
package layout

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"embed"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	stdhtml "html"
	"html/template"
	"io/fs"
	"math"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata" // Prague must exist on a bare container

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/calendar"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed i18n.json
var layoutJSON []byte

//go:embed shell.html
var shellFS embed.FS

// Strings is the layout's own catalog, generated from host_i18n.py by
// App/scripts/go_host_i18n.py from i18n_keys.txt.
var Strings = hostweb.Load(layoutJSON)

var prague = func() *time.Location {
	loc, err := time.LoadLocation("Europe/Prague")
	if err != nil {
		panic("layout: Prague zone missing: " + err.Error())
	}
	return loc
}()

// Env is what Render reads besides the request.
type Env struct {
	Pool   *pgxpool.Pool
	Getenv func(string) string
	Now    time.Time
}

// Page is the page's part of the Jinja context: the values a page template
// sets at the top (nav, body_kind, v2, show_nav, how_key) and its title.
type Page struct {
	Title    string // the <title> text; also the h1 unless "<name>.title" is defined
	Nav      string
	BodyKind string // list | detail | form | settings; "" is list
	V2       bool
	HideNav  bool // show_nav = false
	HowKey   string
	BackURL  string
	Status   int // 0 is 200

	// Added in 1380 beyond the promised API.
	AdminWorkspace  bool   // render() sets admin_workspace for admin_* templates
	Lang            string // an explicit context lang (en, cs, vi) wins (0433)
	MetaDescription string // meta_description
	NavBadge        string // nav_badge (v2 shell)
	NavActionCount  int    // nav_action_count (legacy shell and tab bar)

	// Added in 1381.
	HideAlertStack       bool   // hide_alert_stack: no _host_alerts.html
	AlertsExpanded       bool   // alerts_expanded: every alert as a full line
	PhHidePin            bool   // ph_hide_pin: hide the guest_pin_rotated line (ph-hide)
	CelebrationMilestone string // celebration_milestone; "" shows no toast
	SentGuestCount       int    // sent_guest_count for celebration.body
}

// Templates is a page package's parsed templates and catalog. The master set
// is never executed; each request runs a clone, so it is safe for concurrent use.
type Templates struct {
	cat    hostweb.Catalog
	master *template.Template
}

// Parse parses the layout shell and the page files matched by patterns in fsys.
func Parse(cat hostweb.Catalog, fsys fs.FS, patterns ...string) (*Templates, error) {
	return ParseFuncs(cat, nil, fsys, patterns...)
}

// MustParse is Parse that panics, for package-level vars.
func MustParse(cat hostweb.Catalog, fsys fs.FS, patterns ...string) *Templates {
	t, err := Parse(cat, fsys, patterns...)
	if err != nil {
		panic("layout: " + err.Error())
	}
	return t
}

// shell is the data the shell reads from the database and the session. It is
// a value of its own so tests can give it without a database.
type shell struct {
	SignedIn          bool
	IsAdmin           bool
	Impersonating     bool
	WorkspaceName     string // display_name or username
	WorkspaceUsername string
	DeletionDueAt     string
	PropertyCount     int
	MinutesLeft       *int // impersonation_minutes_left(); nil outside one

	// 1381.
	AccountID          int64  // current_user id (data-havel-owner)
	AccountIsWorkspace bool   // not an admin in a host's workspace
	TwoFactorDone      bool   // two_factor_prompted_at or totp_enabled (or no account row)
	SignupAt           string // user_account.signup_at of the account
	HavelOn            bool
	HavelState         string     // _havel_panel_state state: "off", a limit, or "" (may send)
	Billing            billingRow // the workspace's billing_account row
	Alerts             []alertRow // alerts.open_alerts(workspace), ordered by level
	Progress           map[int64]calendar.AlertProgress
}

// shellSQL is auth.workspace_user's display_name and deletion_due_at, the
// count of access.apartments(request, ...) (owner-scoped, archived_at IS NULL),
// the signed-in account's e-mail and security-prompt columns, and the
// billing_account rows of the workspace (banner) and of the account (Havel's
// plan multiplier), in one read. $1 is the workspace, $2 the account.
const shellSQL = `SELECT COALESCE(u.display_name, ''), COALESCE(u.deletion_due_at, ''),
       (SELECT COUNT(*) FROM apartment a WHERE a.owner_user_id = u.id AND a.archived_at IS NULL),
       COALESCE(acc.email, ''),
       (acc.id IS NULL OR COALESCE(acc.two_factor_prompted_at::text, '') != '' OR COALESCE(acc.totp_enabled, 0) != 0),
       COALESCE(acc.signup_at::text, ''),
       COALESCE(wb.status, ''), COALESCE(wb.plan, ''), COALESCE(wb.trial_ends_at::text, ''), COALESCE(wb.period_end::text, ''),
       COALESCE(ab.status, ''), COALESCE(ab.plan, '')
  FROM user_account u
  LEFT JOIN user_account acc ON acc.id = $2
  LEFT JOIN billing_account wb ON wb.owner_user_id = u.id
  LEFT JOIN billing_account ab ON ab.owner_user_id = $2
 WHERE u.id = $1`

// loadShell reads the shell data: shellSQL, the open alerts with their stays
// (openAlertsSQL), the guests of those stays (one read, none without a stay
// card) and, only while Havel is on, the rate-limit counts. All reads only.
func loadShell(ctx context.Context, r *http.Request, env Env, host *session.Host) (shell, error) {
	if host == nil {
		return shell{}, nil
	}
	s := shell{
		SignedIn:           true,
		IsAdmin:            host.Account.Role == "admin",
		Impersonating:      host.Impersonating,
		WorkspaceUsername:  host.Workspace.Username,
		MinutesLeft:        minutesLeft(host, env.Getenv, env.Now),
		AccountID:          host.Account.ID,
		AccountIsWorkspace: host.Workspace.ID == host.Account.ID,
		TwoFactorDone:      true,
		HavelState:         "off",
	}
	var name, email string
	var count int64
	var acct billingRow
	err := env.Pool.QueryRow(ctx, shellSQL, host.Workspace.ID, host.Account.ID).Scan(&name, &s.DeletionDueAt, &count,
		&email, &s.TwoFactorDone, &s.SignupAt,
		&s.Billing.Status, &s.Billing.Plan, &s.Billing.TrialEndsAt, &s.Billing.PeriodEnd, &acct.Status, &acct.Plan)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return shell{}, err
	}
	if s.HavelOn = havelOn(env.Getenv, email); s.HavelOn {
		counts, err := loadHavelCounts(ctx, env.Pool, host.Account.ID, env.Now)
		if err != nil {
			return shell{}, err
		}
		s.HavelState = havelLimitState(env.Getenv, counts, aiMultiplier(billingOn(env.Getenv), acct))
	}
	if s.Alerts, err = loadAlerts(ctx, env.Pool, host.Workspace.ID); err != nil {
		return shell{}, err
	}
	shown := s.Alerts
	if r.URL.Path != "/" {
		shown, _ = shellSlice(shown)
	}
	if s.Progress, err = calendar.AlertProgresses(ctx, env.Pool, env.Getenv, progressStays(shown), env.Now); err != nil {
		return shell{}, err
	}
	s.PropertyCount = int(count)
	s.WorkspaceName = name
	if s.WorkspaceName == "" {
		s.WorkspaceName = host.Workspace.Username
	}
	return s, nil
}

// minutesLeft is auth.impersonation_minutes_left: whole minutes left, rounded
// up, or nil outside an impersonation or without a limit.
func minutesLeft(host *session.Host, getenv func(string) string, now time.Time) *int {
	if !host.Impersonating {
		return nil
	}
	started, ok := host.Payload["ast"].(int64)
	if !ok {
		return nil
	}
	limit := impersonationMaxAge(getenv)
	if limit <= 0 {
		return nil
	}
	remaining := float64(limit) - (float64(now.UnixNano())/1e9 - float64(started))
	m := int(math.Ceil(remaining / 60))
	if m < 0 {
		m = 0
	}
	return &m
}

// impersonationMaxAge is auth._impersonation_max_age in seconds, read as
// session.impersonationMaxAge reads it (an empty value is the default 24 h).
func impersonationMaxAge(getenv func(string) string) int64 {
	raw := strings.TrimSpace(getenv("UBYHOST_IMPERSONATION_MAX_HOURS"))
	if raw == "" {
		raw = "24"
	}
	if raw == "0" {
		return 0
	}
	hours, err := strconv.ParseInt(raw, 10, 64)
	if err != nil {
		hours = 24
	}
	if hours < 0 {
		hours = 0
	}
	return hours * 3600
}

// Render writes the page: the shell around the page template name, executed
// with data. It loads the shell data (one query) and issues the CSRF token.
func Render(w http.ResponseWriter, r *http.Request, env Env, host *session.Host, p Page, tpl *Templates, name string, data any) error {
	if tpl.master.Lookup(name) == nil {
		return fmt.Errorf("layout: no template %q", name)
	}
	sh, err := loadShell(r.Context(), r, env, host)
	if err != nil {
		return err
	}
	secret, err := secure.LoadSecret(env.Getenv)
	if err != nil {
		return err
	}
	token, cookie, err := csrfToken(r, secret, env.Getenv, env.Now)
	if err != nil {
		return err
	}
	if cookie != nil {
		http.SetCookie(w, cookie)
	}
	return render(w, r, env, sh, token, p, tpl, name, data)
}

// render is Render after the reads: everything it needs is given, so the
// golden test runs it without a database.
func render(w http.ResponseWriter, r *http.Request, env Env, sh shell, token string, p Page, tpl *Templates, name string, data any) error {
	lang := resolveLang(r, sh.SignedIn, p)
	c := &reqCtx{lang: lang, page: tpl.cat, layout: Strings, csrf: token, v2: p.V2, now: env.Now, getenv: env.Getenv}
	clone, err := tpl.master.Clone()
	if err != nil {
		return err
	}
	clone.Funcs(c.funcs())
	v := buildView(r, env, sh, c, p)
	slot := func(suffix string) (template.HTML, bool, error) {
		t := clone.Lookup(name + suffix)
		if t == nil {
			return "", false, nil
		}
		var b bytes.Buffer
		if err := t.Execute(&b, data); err != nil {
			return "", true, err
		}
		return template.HTML(b.String()), true, nil
	}
	var defined bool
	if v.Body, _, err = slot(""); err != nil {
		return err
	}
	// A fixed order, so a slot with side effects or an error behaves the same
	// on every request.
	for _, sl := range []struct {
		suffix string
		dst    *template.HTML
	}{
		{".meta", &v.Meta}, {".primary", &v.Primary}, {".secondary", &v.Secondary}, {".tabs", &v.Tabs},
		{".toolbar", &v.Toolbar}, {".head", &v.Head}, {".back_label", &v.BackLabel},
	} {
		h, _, err := slot(sl.suffix)
		if err != nil {
			return err
		}
		*sl.dst = trimHTML(h)
	}
	var h1 template.HTML
	if h1, defined, err = slot(".title"); err != nil {
		return err
	}
	if defined {
		v.H1 = trimHTML(h1)
		if p.Title == "" {
			// No Page.Title: <title> is the slot's text.
			if txt := strings.TrimSpace(stdhtml.UnescapeString(striptags(string(v.H1)))); txt != "" {
				v.Title = txt
			}
		}
	} else {
		v.H1 = template.HTML(escText(strings.TrimSpace(v.Title)))
	}
	if v.BackLabel == "" {
		v.BackLabel = template.HTML(escText(c.t("common.back")))
	}
	var out bytes.Buffer
	if err := clone.ExecuteTemplate(&out, "layout.base", v); err != nil {
		return err
	}
	if asked := supportedLang(lastQuery(r, "lang")); asked != "" && hostweb.Cookie(r, langCookie) != asked {
		http.SetCookie(w, &http.Cookie{
			Name:     langCookie,
			Value:    asked,
			Path:     "/",
			MaxAge:   langCookieMaxAge,
			SameSite: http.SameSiteLaxMode,
			Secure:   strings.HasPrefix(strings.ToLower(hostweb.PublicBase(env.Getenv)), "https://"),
		})
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	status := p.Status
	if status == 0 {
		status = http.StatusOK
	}
	w.WriteHeader(status)
	_, err = w.Write(out.Bytes())
	return err
}

func trimHTML(h template.HTML) template.HTML { return template.HTML(strings.TrimSpace(string(h))) }

// host_i18n.LANG_COOKIE and LANG_COOKIE_MAX_AGE (180 days).
const (
	langCookie       = "ubyhost_lang"
	langCookieMaxAge = 60 * 60 * 24 * 180
)

// supportedLang is host_i18n.supported_language.
func supportedLang(v string) string {
	s := []rune(strings.ToLower(strings.TrimSpace(v)))
	if len(s) > 2 {
		s = s[:2]
	}
	switch string(s) {
	case "en", "cs", "vi":
		return string(s)
	}
	return ""
}

// indexablePaths is seo.INDEXABLE_PATHS.
var indexablePaths = map[string]bool{
	"/": true, "/login": true, "/legal": true, "/terms": true, "/privacy": true, "/dpa": true,
	"/subprocessors": true, "/jak-to-funguje": true, "/cenik": true,
	"/pruvodce/hlaseni-cizincu-ubyport": true, "/pruvodce/online-ubytovaci-kniha": true,
}

// resolveLang is the language part of templating.render: a signed-in host
// falls back to English (hostweb.Lang), a visitor to Czech; public pages exist
// in en and cs only; an explicit Page.Lang wins.
func resolveLang(r *http.Request, signedIn bool, p Page) string {
	var lang string
	if signedIn {
		lang = hostweb.Lang(r)
	} else {
		lang = supportedLang(r.URL.Query().Get("lang"))
		if lang == "" {
			lang = supportedLang(hostweb.Cookie(r, langCookie))
		}
		if lang == "" {
			lang = "cs"
		}
	}
	public := indexablePaths[r.URL.Path] && r.URL.Path != "/login"
	if r.URL.Path == "/" && signedIn {
		public = false
	}
	if public && lang != "en" && lang != "cs" {
		lang = "en"
	}
	switch p.Lang {
	case "en", "cs", "vi":
		lang = p.Lang
	}
	return lang
}

// lastQuery is Starlette's request.query_params.get: the last value of key.
func lastQuery(r *http.Request, key string) string {
	v, _ := lastQueryOK(r, key)
	return v
}

func lastQueryOK(r *http.Request, key string) (string, bool) {
	vals, ok := r.URL.Query()[key]
	if !ok || len(vals) == 0 {
		return "", false
	}
	return vals[len(vals)-1], true
}

// security.CSRF_COOKIE, CSRF_MAX_AGE and the serializer salt.
const (
	csrfCookie = "ubyhost_csrf"
	csrfMaxAge = 30 * 24 * 60 * 60 // auth.SESSION_REMEMBER_MAX_AGE
	csrfSalt   = "ubyhost-csrf"
)

// csrfToken is security.csrf_token plus attach_csrf_cookie: the token is bound
// to the ubyhost_csrf nonce cookie; a request without one gets a new nonce and
// the cookie to set.
func csrfToken(r *http.Request, secret string, getenv func(string) string, now time.Time) (string, *http.Cookie, error) {
	nonce := hostweb.Cookie(r, csrfCookie)
	var cookie *http.Cookie
	if nonce == "" {
		buf := make([]byte, 32)
		if _, err := rand.Read(buf); err != nil {
			return "", nil, err
		}
		nonce = base64.RawURLEncoding.EncodeToString(buf)
		cookie = &http.Cookie{
			Name:     csrfCookie,
			Value:    nonce,
			Path:     "/",
			MaxAge:   csrfMaxAge,
			HttpOnly: true,
			SameSite: http.SameSiteStrictMode,
			Secure:   hostweb.SecureCookies(getenv),
		}
	}
	sum := sha256.Sum256([]byte(nonce))
	token, err := secure.NewTimedSerializer(secret, csrfSalt).Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, now)
	if err != nil {
		return "", nil, err
	}
	return token, cookie, nil
}

// fixTargets is templating.FIX_TARGETS (?fix=<code>).
var fixTargets = map[string][2]string{
	"bank":       {"/entities", "payments.fix.bank"},
	"stripe":     {"/payments#stripe-setup", "payments.fix.stripe"},
	"lock_guide": {"/guide#door-codes", "smart_locks.guide_link"},
}

var toastKinds = map[string]bool{"info": true, "success": true, "warning": true, "partial": true, "error": true}

type navLink struct {
	Href, Label string
	Icon        template.HTML
	Active      bool
	Count       string
}

type alternate struct{ Code, Href string }

// view is the context the shell templates read.
type view struct {
	Lang, CSRF, Title, Path      string
	V2, ShowNav, AdminWorkspace  bool
	Nav, BodyKind, WrapClass     string
	HowKey, BackURL              string
	Canonical, MetaDescription   string
	Alternates                   []alternate
	SignedIn, IsAdmin            bool
	Impersonating                bool
	WorkspaceName, WorkspaceUser string
	Initial                      string
	PropertyCount                int
	DeletionDue                  string
	UbyportEnv                   string
	MockProduction               bool
	OperatorEmail                string
	Passkeys                     bool
	HavelOn                      bool // havel_on (launcher links)
	HavelPanel                   bool // _havel_panel.html is included
	HavelFab                     bool // nav != "havel": the FAB and the dialog
	HavelState                   string
	HavelSrc                     template.URL
	HavelPage, ReturnPath        string
	HavelTopics                  []havelTopic
	AccountID                    int64
	Alerts                       alertStack
	Billing                      *billingLine
	SecurityPrompt               bool // the dialog is shown
	SecurityPasskeys             bool // and offers a passkey
	Celebration                  string
	SentGuestCount               int
	Flash, FlashError, FlashKind string
	ShowFlash, ShowError, Sticky bool
	FixHref, FixKey              string
	UndoStay, UndoReturn         string
	MinutesText                  string
	MinutesLeft                  *int
	StaysNav, PropertiesNav      bool
	MoreNav, MenuNav             bool
	NavBadge, NavCount           string
	SideNav                      []navLink
	Body, H1, Meta, Primary      template.HTML
	Secondary, Tabs, Toolbar     template.HTML
	Head, BackLabel              template.HTML
}

func buildView(r *http.Request, env Env, sh shell, c *reqCtx, p Page) view {
	getenv := env.Getenv
	q := func(k string) string { return lastQuery(r, k) }
	bodyKind := p.BodyKind
	if bodyKind == "" {
		bodyKind = "list"
	}
	v := view{
		Lang: c.lang, CSRF: c.csrf, Title: p.Title, Path: r.URL.Path,
		V2: p.V2, ShowNav: !p.HideNav, AdminWorkspace: p.AdminWorkspace,
		Nav: p.Nav, BodyKind: bodyKind, HowKey: p.HowKey, BackURL: strings.TrimSpace(p.BackURL),
		MetaDescription: p.MetaDescription, NavBadge: p.NavBadge,
		SignedIn: sh.SignedIn, IsAdmin: sh.IsAdmin, Impersonating: sh.Impersonating,
		WorkspaceName: sh.WorkspaceName, WorkspaceUser: sh.WorkspaceUsername,
		Initial: firstUpper(sh.WorkspaceName), PropertyCount: sh.PropertyCount,
		MinutesLeft: sh.MinutesLeft,
	}
	if v.Title == "" {
		v.Title = "UbyHost"
	}
	if bodyKind == "form" || bodyKind == "settings" {
		v.WrapClass = "ui-lane-narrow"
	}
	if indexablePaths[r.URL.Path] {
		base := hostweb.PublicBase(getenv) + r.URL.Path
		v.Canonical = base
		if asked := supportedLang(q("lang")); asked == "en" || asked == "cs" {
			v.Canonical = base + "?lang=" + asked
		}
		v.Alternates = []alternate{{"en", base + "?lang=en"}, {"cs", base + "?lang=cs"}, {"x-default", base}}
	}
	if sh.DeletionDueAt != "" {
		v.DeletionDue = datetimeLocal(sh.DeletionDueAt)
	}
	v.UbyportEnv = strings.ToLower(getenvOr(getenv, "UBYHOST_UBYPORT_ENV", "mock"))
	v.MockProduction = strings.ToLower(getenvOr(getenv, "UBYHOST_DEPLOYMENT", "local")) == "production"
	v.OperatorEmail = strings.TrimSpace(getenv("UBYHOST_OPERATOR_EMAIL"))
	if v.OperatorEmail == "" {
		v.OperatorEmail = "support@ubyhost.com"
	}
	v.Passkeys = passkeysAvailable(getenv)
	// Toasts (templating.render).
	flash, err := q("msg"), q("err")
	inlineSection := ""
	if sec := q("sec"); isAlpha(sec) && isPropertyPath(r.URL.Path) {
		inlineSection = sec
	}
	editorSaved := q("saved") == "1" && isPropertyPath(r.URL.Path)
	v.Flash, v.FlashError = flash, err
	v.ShowFlash = flash != "" && inlineSection == "" && !editorSaved
	v.ShowError = err != "" && inlineSection == ""
	v.FlashKind = "info"
	if kind := q("toast_kind"); sh.SignedIn && toastKinds[kind] {
		v.FlashKind = kind
	}
	v.Sticky = sh.SignedIn && flash != "" && q("toast_sticky") == "1"
	if fix, ok := fixTargets[q("fix")]; ok {
		v.FixHref, v.FixKey = fix[0], fix[1]
	}
	if stay := q("undo_stay"); isDigits(stay) {
		v.UndoStay = stay
	}
	if ret, ok := lastQueryOK(r, "undo_return"); ok {
		v.UndoReturn = ret
	} else {
		v.UndoReturn = "/"
	}
	if m := sh.MinutesLeft; m != nil {
		if *m >= 120 {
			v.MinutesText = c.tp("impersonation.hours_left", *m/60)
		} else {
			v.MinutesText = c.tp("impersonation.minutes_left", *m)
		}
	}
	// 1381: alerts, billing line, Havel, security prompt, celebration.
	v.ReturnPath = r.URL.Path
	if v.ShowNav && !(p.HideAlertStack || p.V2) {
		rows, more := sh.Alerts, 0
		if r.URL.Path != "/" {
			rows, more = shellSlice(rows)
		}
		cards := presentMany(rows, sh.Progress, alertText{lang: c.lang, now: env.Now})
		v.Alerts = buildAlertStack(cards, more, r.URL.Path, lastQuery(r, "apartment"), p.AlertsExpanded, p.PhHidePin, c.t)
	}
	if sh.SignedIn {
		pn := env.Now.In(prague)
		v.Billing = billingBanner(billingOn(getenv), sh.Billing, time.Date(pn.Year(), pn.Month(), pn.Day(), 0, 0, 0, 0, time.UTC))
	}
	v.HavelOn = sh.SignedIn && sh.HavelOn
	v.HavelPanel = v.ShowNav && sh.SignedIn
	if v.HavelPanel {
		v.HavelFab = p.Nav != "havel"
		v.HavelState = sh.HavelState
		v.HavelPage = p.Nav
		v.HavelSrc = template.URL("/havel?page=" + pyQuote(p.Nav) + "&return_to=" + pyQuote(r.URL.Path))
		v.HavelTopics = orderedHavelTopics(p.Nav)
		v.AccountID = sh.AccountID
	}
	if v.ShowNav {
		if sp := securityPrompt(sh, r.URL.Path, env.Now, v.Passkeys); sp != nil {
			v.SecurityPrompt, v.SecurityPasskeys = true, *sp
		}
	}
	v.Celebration, v.SentGuestCount = p.CelebrationMilestone, p.SentGuestCount
	// Navigation state (_shell_*.html).
	switch p.Nav {
	case "reservations", "submissions", "housebook":
		v.StaysNav = true
	case "apartments", "guest_links", "automation", "entities", "smart_locks":
		v.PropertiesNav = true
	}
	switch p.Nav {
	case "invoices", "payments", "stay_fees", "booking_sites", "settings", "admin", "guide":
		v.MoreNav = true
	}
	switch p.Nav {
	case "menu", "cleaning", "stay_fees", "payments", "settings", "entities", "privacy_requests":
		v.MenuNav = true
	}
	if p.NavActionCount != 0 {
		v.NavCount = fmt.Sprint(p.NavActionCount)
		if p.NavActionCount >= 10 {
			v.NavCount = "9+"
		}
	}
	for _, l := range []struct {
		href, icon, key string
		active          bool
	}{
		{"/", "layout-dashboard", "nav.overview", p.Nav == "dashboard"},
		{"/reservations", "calendar-days", "nav.stays", v.StaysNav},
		{"/apartments", "house", "nav.properties", v.PropertiesNav},
		{"/stay-fees", "receipt-text", "nav.stay_fees", p.Nav == "stay_fees"},
		{"/cleaning", "sparkles", "nav.cleaning", p.Nav == "cleaning"},
		{"/payments", "credit-card", "nav.payments", p.Nav == "payments"},
		{"/booking-sites", "external-link", "nav.booking_sites", p.Nav == "booking_sites"},
	} {
		link := navLink{Href: l.href, Label: c.t(l.key), Icon: template.HTML(mustIcon(l.icon, 20)), Active: l.active}
		if l.href == "/" {
			link.Count = v.NavCount
		}
		v.SideNav = append(v.SideNav, link)
	}
	return v
}

func getenvOr(getenv func(string) string, key, def string) string {
	if v := getenv(key); v != "" {
		return v
	}
	return def
}

// isPropertyPath is re.fullmatch(r"/apartments/\d+", path).
func isPropertyPath(path string) bool {
	rest, ok := strings.CutPrefix(path, "/apartments/")
	return ok && isDigits(rest)
}

// passkeysAvailable is passkeys.available(): a host name (not an IP) and
// HTTPS, or localhost.
func passkeysAvailable(getenv func(string) string) bool {
	u, err := url.Parse(hostweb.PublicBase(getenv))
	if err != nil {
		return false
	}
	host := strings.ToLower(u.Hostname())
	if host == "" || isDigits(strings.ReplaceAll(host, ".", "")) || strings.Contains(host, ":") {
		return false
	}
	return strings.ToLower(u.Scheme) == "https" || host == "localhost"
}
