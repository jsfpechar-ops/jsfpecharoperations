// Package auth serves the login and account routes of
// App/app/routes/admin_accounts.py, signup.py and passkeys.py that render no
// page: every answer is a redirect, plain text, CSV, JSON or empty (brief
// 1282). The pages (login, 2FA setup, e-mail confirm, sign-up) stay on Python.
//
// Gates run in Python's order: the host CSRF dependency first (admin.router's
// protect_host_post), then the path parameter (FastAPI's 422), then the route
// body: current_user, require_login or _require_admin.
package auth

import (
	"context"
	_ "embed"
	"encoding/json"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed i18n.json
var catalogJSON []byte

// catalog holds the host strings these routes raise, written from
// host_i18n.STRINGS by App/scripts/auth_routes_golden.py.
var catalog = hostweb.Load(catalogJSON)

// Route is one pattern and its handler.
type Route struct {
	Pattern string // the http.ServeMux pattern, method included
	Path    string // the metrics label
	Handler http.HandlerFunc
}

// Routes lists every route of the package. It does not use pool.
func Routes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {
	d := deps{pool: pool, getenv: getenv, now: now}
	return []Route{
		{"POST /logout", "/logout", d.logout},
		{"POST /account/logout-all", "/account/logout-all", d.logoutAll},
		{"POST /account/onboarding-emails", "/account/onboarding-emails", d.onboardingEmails},
		{"POST /account/stay-fee-emails", "/account/stay-fee-emails", d.stayFeeEmails},
		{"POST /account/guest-details-mail", "/account/guest-details-mail", d.guestDetailsMail},
		{"POST /account/2fa/move", "/account/2fa/move", d.twoFactorMove},
		{"POST /account/2fa/disable", "/account/2fa/disable", d.twoFactorDisable},
		{"POST /account/security-prompt/seen", "/account/security-prompt/seen", d.securityPromptSeen},
		{"GET /login/2fa", "/login/2fa", d.twoFactorLoginGet},
		{"GET /admin/users", "/admin/users", d.usersAdmin},
		{"POST /admin/users/{id}/impersonate", "/admin/users/{id}/impersonate", d.impersonate},
		{"POST /admin/stop-impersonating", "/admin/stop-impersonating", d.stopImpersonating},
		{"GET /admin/incidents", "/admin/incidents", d.incidentsAdmin},
		{"POST /admin/incidents", "/admin/incidents", d.incidentCreate},
		{"POST /admin/incidents/{id}", "/admin/incidents/{id}", d.incidentUpdate},
		{"POST /admin/ads-conversions.csv", "/admin/ads-conversions.csv", d.adsConversionsCSV},
		{"POST /admin/users/{id}/ads-consent/withdraw", "/admin/users/{id}/ads-consent/withdraw", d.adsConsentWithdraw},
		{"POST /settings/privacy/ad-consent", "/settings/privacy/ad-consent", d.adConsentSettings},
		{"GET /login", "/login", d.loginForm},
		{"POST /login", "/login", d.loginSubmit},
		{"GET /login/link", "/login/link", d.loginLinkForm},
		{"POST /login/link", "/login/link", d.loginLinkSubmit},
		{"POST /login/2fa", "/login/2fa", d.twoFactorLogin},
		{"POST /admin/users", "/admin/users", d.userCreate},
		{"POST /admin/users/{id}/invite", "/admin/users/{id}/invite", d.userInvite},
		{"POST /admin/users/{id}/email", "/admin/users/{id}/email", d.userEmailSet},
		{"GET /account/accept", "/account/accept", d.accountAcceptForm},
		{"POST /account/accept", "/account/accept", d.accountAcceptSubmit},
		{"GET /account/2fa/setup", "/account/2fa/setup", d.twoFactorSetupForm},
		{"POST /account/2fa/setup", "/account/2fa/setup", d.twoFactorSetupSubmit},
		{"POST /account/email", "/account/email", d.accountEmailRequest},
		{"GET /account/email/confirm", "/account/email/confirm", d.accountEmailConfirmForm},
		{"POST /account/email/confirm", "/account/email/confirm", d.accountEmailConfirmSubmit},
		{"POST /admin/users/{id}/export", "/admin/users/{id}/export", d.workspaceExport},
		{"GET /signup", "/signup", d.signupForm},
		{"POST /signup", "/signup", d.signupSubmit},
		{"GET /signup/verify", "/signup/verify", d.signupVerifyForm},
		{"POST /signup/verify", "/signup/verify", d.signupVerifySubmit},
		{"GET /admin/operations", "/admin/operations", d.operationsAdmin},
	}
}

type deps struct {
	pool   *pgxpool.Pool
	getenv func(string) string
	now    func() time.Time
}

// login is auth.require_login. hostweb.Login exempts the read-only-open paths
// itself. ok is false when the response is written.
func (d deps) login(w http.ResponseWriter, r *http.Request, at time.Time) (*session.Host, bool) {
	h, err := hostweb.Login(bare{w}, r, d.pool, d.getenv, at)
	if err != nil {
		serverError(w, err)
		return nil, false
	}
	return h, h != nil
}

// bare drops what http.Redirect adds to a GET redirect (Content-Type and a
// small HTML body): Starlette's RedirectResponse sends neither.
type bare struct{ http.ResponseWriter }

func (b bare) WriteHeader(code int) {
	if code >= 300 && code < 400 {
		b.Header()["Content-Type"] = nil
	}
	b.ResponseWriter.WriteHeader(code)
}

func (b bare) Write(p []byte) (int, error) {
	if loc := b.Header().Get("Location"); loc != "" && b.Header()["Content-Type"] == nil {
		return len(p), nil
	}
	return b.ResponseWriter.Write(p)
}

// current is auth.current_user (with workspace_user): the signed-in host or
// nil, without the require_login gates. ok is false after a 500.
func (d deps) current(w http.ResponseWriter, r *http.Request, at time.Time) (*session.Host, bool) {
	h, err := session.Load(r.Context(), d.pool, hostweb.Cookie(r, session.CookieName), at, d.getenv)
	if err != nil {
		serverError(w, err)
		return nil, false
	}
	return h, true
}

// form parses the body once; hostweb.CSRF may already have done it.
func form(r *http.Request) {
	if r.PostForm == nil {
		_ = r.ParseForm()
	}
}

// formLast is Starlette FormData.get: the last value of a repeated key.
func formLast(r *http.Request, key string) (string, bool) {
	form(r)
	vals, ok := r.PostForm[key]
	if !ok || len(vals) == 0 {
		return "", false
	}
	return vals[len(vals)-1], true
}

// formStr is admin_helpers.form_str: the stripped last value, or def.
func formStr(r *http.Request, key, def string) string {
	v, ok := formLast(r, key)
	if !ok || v == "" {
		return pyStrip(def)
	}
	return pyStrip(v)
}

// formHas is `key in form`.
func formHas(r *http.Request, key string) bool {
	form(r)
	_, ok := r.PostForm[key]
	return ok
}

// pySpace is str.isspace for one rune: Go's set plus U+001C..U+001F.
func pySpace(c rune) bool { return unicode.IsSpace(c) || (c >= 0x1c && c <= 0x1f) }

// pyStrip is str.strip().
func pyStrip(s string) string { return strings.TrimFunc(s, pySpace) }

// pyIsDigit is str.isdigit for ASCII input; any other rune reports false.
func pyIsDigit(s string) bool {
	if s == "" {
		return false
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

// flashFor is admin_helpers.flash: the key's text in the request language.
func flashFor(r *http.Request, key string) hostweb.Flash {
	return hostweb.Flash{Text: catalog.T(hostweb.Lang(r), key, nil), Key: key}
}

var none hostweb.Flash

type validationItem struct {
	Type  string   `json:"type"`
	Loc   []string `json:"loc"`
	Msg   string   `json:"msg"`
	Input string   `json:"input"`
}

// pathID is FastAPI's int path parameter: a 422 with pydantic's int_parsing
// detail when the segment is not an integer.
func pathID(w http.ResponseWriter, r *http.Request, name string) (int64, bool) {
	raw := r.PathValue("id")
	if n, err := strconv.ParseInt(strings.TrimSpace(raw), 10, 64); err == nil {
		return n, true
	}
	writeJSON(w, http.StatusUnprocessableEntity, map[string][]validationItem{"detail": {{
		Type: "int_parsing", Loc: []string{"path", name},
		Msg: "Input should be a valid integer, unable to parse string as an integer", Input: raw,
	}}})
	return 0, false
}

// writeJSON is Starlette's JSONResponse: compact, ensure_ascii=False.
func writeJSON(w http.ResponseWriter, status int, body any) {
	var b strings.Builder
	enc := json.NewEncoder(&b)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(body)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write([]byte(strings.TrimSuffix(b.String(), "\n")))
}

// httpError is an HTTPException(status) with its default detail.
func httpError(w http.ResponseWriter, status int) {
	writeJSON(w, status, map[string]string{"detail": http.StatusText(status)})
}

// emptyStatus is Starlette's Response(status_code=status): no body, no Content-Type.
func emptyStatus(w http.ResponseWriter, status int) {
	w.Header()["Content-Type"] = nil
	w.WriteHeader(status)
}

// redirect is RedirectResponse(location, 303) with the location kept as given.
func redirect(w http.ResponseWriter, location string) {
	w.Header().Set("Location", location)
	w.WriteHeader(http.StatusSeeOther)
}

func serverError(w http.ResponseWriter, err error) {
	log.Printf("web/auth: %v", err)
	http.Error(w, "Internal Server Error", http.StatusInternalServerError)
}

// gated is who require_login set as current actor and owner (db.set_current_actor,
// db.set_current_owner); nil after current_user alone, which sets neither.
type gated struct {
	h *session.Host
}

// audit is db.audit. Without an explicit owner the row takes the workspace
// require_login set; actor_user_id and impersonator_user_id come from it too.
func (d deps) audit(ctx context.Context, g *gated, at time.Time, action, detail, actor string, owner *int64) error {
	var actorID, impersonator *int64
	if g != nil {
		id := g.h.Account.ID
		actorID = &id
		if g.h.Impersonating {
			impersonator = &id
		}
		if owner == nil {
			ws := g.h.Workspace.ID
			owner = &ws
		}
	}
	_, err := d.pool.Exec(ctx, `INSERT INTO audit (at, actor, action, detail, owner_user_id, actor_user_id, impersonator_user_id)
		VALUES ($1, $2, $3, $4, $5, $6, $7)`, session.UTCNow(at), actor, action, detail, owner, actorID, impersonator)
	return err
}

func ptr(v int64) *int64 { return &v }

// remembers is auth.session_remembers: bool(payload.get("rm")).
func remembers(p map[string]any) bool {
	switch v := p["rm"].(type) {
	case nil:
		return false
	case bool:
		return v
	case int64:
		return v != 0
	case float64:
		return v != 0
	case string:
		return v != ""
	}
	return true
}

// clearCookie is response.delete_cookie(name, path="/", secure, httponly, samesite="lax").
func clearCookie(name string, secure bool) *http.Cookie {
	return &http.Cookie{Name: name, Value: "", Path: "/", MaxAge: -1, Expires: time.Unix(0, 0),
		HttpOnly: true, Secure: secure, SameSite: http.SameSiteLaxMode}
}

// attach is auth.attach_session for a fresh token.
func (d deps) attach(w http.ResponseWriter, userID, sv int64, opt session.IssueOptions, at time.Time) error {
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		return err
	}
	token, err := session.IssueSession(secret, userID, sv, opt, at)
	if err != nil {
		return err
	}
	http.SetCookie(w, session.SessionCookie(token, opt.Remember, hostweb.SecureCookies(d.getenv)))
	return nil
}
