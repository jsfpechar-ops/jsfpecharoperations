package auth

// GET/POST /signup and GET/POST /signup/verify (brief 1507), ported from
// App/app/routes/signup.py 24-174: the self sign-up form, the "check your
// e-mail" page, and the confirmation page that activates the account and
// signs it in. Every route answers 404 while UBYHOST_SIGNUP_ENABLED is off.
// The POSTs pass the host CSRF check first (signup.py's router is included
// from admin.router, so protect_host_post runs before the route body).

import (
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/signup"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/turnstile"
)

// SignupMethod is the audit detail method of a login by the sign-up link.
const SignupMethod = "signup_link"

var signupSeparators = regexp.MustCompile(`[._\-]+`)

// signupCut is s[:n] on a Python str (code points).
func signupCut(s string, n int) string {
	r := []rune(s)
	if len(r) > n {
		return string(r[:n])
	}
	return s
}

// signupSquash is " ".join(s.split()).
func signupSquash(s string) string { return strings.Join(strings.FieldsFunc(s, pySpace), " ") }

// signupWorkspaceFromEmail is _workspace_from_email: the local part without a
// +tag, separators as spaces, at most WorkspaceMax characters; the domain
// when nothing is left.
func signupWorkspaceFromEmail(email string) string {
	local, domain, _ := strings.Cut(email, "@")
	name, _, _ := strings.Cut(local, "+")
	name = signupSeparators.ReplaceAllString(name, " ")
	name = pyStrip(signupCut(signupSquash(name), signup.WorkspaceMax))
	if name != "" {
		return name
	}
	return signupCut(domain, signup.WorkspaceMax)
}

// signupSelection is signup_selection.clean as an ordered dict.
func signupSelection(params url.Values) [][2]string {
	clean := signup.CleanSelection(params)
	var out [][2]string
	for _, k := range []string{"plan", "interval", "ttlock", "apartments"} {
		if v, ok := clean[k]; ok {
			out = append(out, [2]string{k, v})
		}
	}
	return out
}

// signupHref is signup.signup_href(lang, {**attr, **selection}): the /signup
// address with the language, the attribution and the plan choices.
func signupHref(secret, lang string, attr map[string]string, selection [][2]string, nowMS int64) string {
	params := url.Values{}
	for k, v := range attr {
		params.Set(k, v)
	}
	for _, kv := range selection {
		params.Set(kv[0], kv[1])
	}
	minted := signup.Attribution(secret, params, true, nowMS)
	pairs := []string{"lang=" + url.QueryEscape(lang)}
	for _, k := range append(append([]string{}, signup.UTMKeys...), "click") {
		if v := minted[k]; v != "" {
			pairs = append(pairs, k+"="+url.QueryEscape(v))
		}
	}
	for _, kv := range signupSelection(params) {
		pairs = append(pairs, kv[0]+"="+url.QueryEscape(kv[1]))
	}
	return "/signup?" + strings.Join(pairs, "&")
}

// signupConsentLabel is signup.consent_label in the form language.
func signupConsentLabel(platform, lang string) signupConsentBox {
	key, link := "signup.ads_consent", signup.GooglePrivacyURL
	if platform == signup.Meta {
		key, link = "signup.meta_consent", signup.MetaPrivacyURL
	}
	cat := signupCatalog.Strings
	return signupConsentBox{Platform: platform, Field: signup.ConsentFields[platform],
		Text: cat.T(lang, key, nil), LinkLabel: cat.T(lang, key+"_link", nil), LinkURL: link}
}

// signupFormView is _form_context plus the template name: the hidden fields,
// one consent box per ad platform of a valid click, and the language switch
// target. The form language is resolve_language(request, default="cs").
func (d deps) signupFormView(r *http.Request, secret string, attr map[string]string, consents map[string]bool,
	selection url.Values, nowMS int64) signupView {
	lang := loginLanguage(r)
	sel := signupSelection(selection)
	v := signupView{Template: "signup.html", Attr: attr, Selection: sel,
		LangNext: signupHref(secret, lang, attr, sel, nowMS)}
	for _, p := range signup.ClickPlatforms(d.getenv, signup.ReadClick(secret, attr["click"], nowMS)) {
		box := signupConsentLabel(p, lang)
		box.Checked = consents[p]
		v.Boxes = append(v.Boxes, box)
	}
	return v
}

// signupForm is GET /signup (signup_form).
func (d deps) signupForm(w http.ResponseWriter, r *http.Request) {
	if !signup.Enabled(d.getenv) {
		httpError(w, http.StatusNotFound)
		return
	}
	at := d.now()
	h, ok := d.current(w, r, at)
	if !ok {
		return
	}
	if h != nil {
		redirect(w, "/")
		return
	}
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		serverError(w, err)
		return
	}
	q := r.URL.Query()
	v := d.signupFormView(r, secret, signup.Attribution(secret, q, true, at.UnixMilli()), nil, q, at.UnixMilli())
	if err := renderSignup(w, r, d.getenv, at, false, v); err != nil {
		serverError(w, err)
	}
}

// signupInput is what signup_submit reads from the form.
type signupInput struct {
	Attr      map[string]string
	Email     string // mail.normalise_email(form_str(email))
	RawEmail  string // form_str(email)[:254]
	Workspace string
	Consents  map[string]bool
	Marketing bool
	Accept    bool
	Lang      string
}

// readSignupForm is the top of signup_submit. The form is parsed already.
func (d deps) readSignupForm(r *http.Request, secret string, nowMS int64) signupInput {
	attr := signup.Attribution(secret, r.PostForm, false, nowMS)
	in := signupInput{
		Attr:      attr,
		Email:     normaliseEmail(formStr(r, "email", "")),
		RawEmail:  signupCut(formStr(r, "email", ""), 254),
		Workspace: signupSquash(formStr(r, "workspace", "")),
		Consents:  map[string]bool{},
		Marketing: formStr(r, "marketing_opt_in", "") == "1",
		Accept:    formStr(r, "accept", "") == "1",
		Lang:      loginLanguage(r),
	}
	for _, p := range signup.ClickPlatforms(d.getenv, signup.ReadClick(secret, attr["click"], nowMS)) {
		in.Consents[p] = formStr(r, signup.ConsentFields[p], "") == "1"
	}
	return in
}

// check is the validation after the rate limit: the error key, its status
// and field, or "" when the form may register. It fills in a missing
// workspace name from the address, as Python does before the length check.
func (in *signupInput) check() (key string, status int, field string) {
	if in.Email == "" {
		return "signup.error.email", http.StatusBadRequest, "email"
	}
	if in.Workspace == "" {
		in.Workspace = signupWorkspaceFromEmail(in.Email)
	}
	if utf8.RuneCountInString(in.Workspace) > signup.WorkspaceMax {
		return "signup.error.workspace", http.StatusBadRequest, "workspace"
	}
	if !in.Accept {
		return "signup.error.accept", http.StatusUnprocessableEntity, "accept"
	}
	return "", 0, ""
}

// againView is again(): the form once more with the error and what was typed.
func (d deps) againView(r *http.Request, secret string, in signupInput, key string, status int, field string, nowMS int64) signupView {
	v := d.signupFormView(r, secret, in.Attr, in.Consents, r.PostForm, nowMS)
	v.Status, v.Error, v.ErrorField = status, key, field
	v.Email, v.Workspace, v.MarketingOptIn = in.RawEmail, in.Workspace, in.Marketing
	return v
}

// signupRegisterInput is the keyword arguments signup_submit hands to register.
func signupRegisterInput(r *http.Request, in signupInput, getenv func(string) string) signup.RegisterInput {
	return signup.RegisterInput{
		Email: in.Email, Workspace: in.Workspace, Attr: in.Attr, Consents: in.Consents,
		OnboardingOptOut: !in.Marketing, Lang: in.Lang, Selection: r.PostForm,
		IP: clientip.Host(r, getenv), UserAgent: r.Header.Get("User-Agent"),
	}
}

// signupSubmit is POST /signup (signup_submit): CSRF, 404 when off,
// Turnstile (403), the hourly budgets per address and IP (429, recorded
// before any other check), then the field checks (400, 400, 422) and
// register. The same "check your e-mail" page whatever register found.
func (d deps) signupSubmit(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	if !signup.Enabled(d.getenv) {
		httpError(w, http.StatusNotFound)
		return
	}
	form(r)
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		serverError(w, err)
		return
	}
	ctx, nowMS := r.Context(), at.UnixMilli()
	in := d.readSignupForm(r, secret, nowMS)
	again := func(key string, status int, field string) {
		signupSignedIn, ok := d.signupSignedIn(w, r, at)
		if !ok {
			return
		}
		if err := renderSignup(w, r, d.getenv, at, signupSignedIn, d.againView(r, secret, in, key, status, field, nowMS)); err != nil {
			serverError(w, err)
		}
	}
	token, _ := formLast(r, "cf-turnstile-response")
	passed, err := turnstile.Verifier{Pool: d.pool, Getenv: d.getenv, Now: d.now}.Verify(ctx, r, token, "host_signup")
	if err != nil {
		serverError(w, err)
		return
	}
	if !passed {
		again("signup.error.turnstile", http.StatusForbidden, "")
		return
	}
	ipKey := clientip.Key(r, d.getenv, "")
	limited, err := signup.RateLimited(ctx, d.pool, ipKey, in.Email, at)
	if err != nil {
		serverError(w, err)
		return
	}
	if limited {
		again("signup.error.rate_limited", http.StatusTooManyRequests, "")
		return
	}
	if err := signup.RecordAttempt(ctx, d.pool, ipKey, in.Email, at); err != nil {
		serverError(w, err)
		return
	}
	if key, status, field := in.check(); key != "" {
		again(key, status, field)
		return
	}
	if _, err := signup.Register(ctx, d.pool, d.getenv, signupRegisterInput(r, in, d.getenv), at); err != nil {
		serverError(w, err)
		return
	}
	signupSignedIn, ok := d.signupSignedIn(w, r, at)
	if !ok {
		return
	}
	if err := renderSignup(w, r, d.getenv, at, signupSignedIn, signupView{Template: "signup_sent.html", Email: in.Email}); err != nil {
		serverError(w, err)
	}
}

// signupSignedIn is "current_user is set" for render(): the shell language and
// the "not you" form. ok is false after a 500.
func (d deps) signupSignedIn(w http.ResponseWriter, r *http.Request, at time.Time) (bool, bool) {
	h, ok := d.current(w, r, at)
	return h != nil, ok
}

// signupVerifyView is signup_verify.html's context.
func signupVerifyView(token string, expired bool, errKey string, status int) signupView {
	if expired {
		return signupView{Template: "signup_verify.html", Expired: true, Status: http.StatusGone, LangNext: "/signup"}
	}
	next := "/signup"
	if token != "" {
		next = "/signup/verify?t=" + token
	}
	return signupView{Template: "signup_verify.html", Token: token, Error: errKey, Status: status, LangNext: next}
}

// signupVerifyForm is GET /signup/verify (signup_verify_form): 410 for a
// link that is forged, expired, superseded or already used.
func (d deps) signupVerifyForm(w http.ResponseWriter, r *http.Request) {
	if !signup.Enabled(d.getenv) {
		httpError(w, http.StatusNotFound)
		return
	}
	at := d.now()
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		serverError(w, err)
		return
	}
	token := signupQuery(r, "t")
	account, err := signup.PendingAccount(r.Context(), d.pool, secret, token, at)
	if err != nil {
		serverError(w, err)
		return
	}
	signupSignedIn, ok := d.signupSignedIn(w, r, at)
	if !ok {
		return
	}
	if err := renderSignup(w, r, d.getenv, at, signupSignedIn, signupVerifyView(token, account == nil, "", 0)); err != nil {
		serverError(w, err)
	}
}

// signupVerifySubmit is POST /signup/verify (signup_verify_submit): 429
// while the address has 20 bad links in 15 minutes, 410 (and one more bad
// link) when the account cannot be activated, else the session cookie, the
// login language, the audit row and a 303 to "/". No device cookie and no
// "remember me".
func (d deps) signupVerifySubmit(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	if !signup.Enabled(d.getenv) {
		httpError(w, http.StatusNotFound)
		return
	}
	ctx := r.Context()
	token := formStr(r, "t", "")
	ipKey := clientip.Key(r, d.getenv, "")
	page := func(v signupView) {
		signupSignedIn, ok := d.signupSignedIn(w, r, at)
		if !ok {
			return
		}
		if err := renderSignup(w, r, d.getenv, at, signupSignedIn, v); err != nil {
			serverError(w, err)
		}
	}
	blocked, err := session.LinkConsumeBlocked(ctx, d.pool, ipKey, at)
	if err != nil {
		serverError(w, err)
		return
	}
	if blocked {
		page(signupVerifyView(token, false, "signup.verify.locked", http.StatusTooManyRequests))
		return
	}
	secret, err := secure.LoadSecret(d.getenv)
	if err != nil {
		serverError(w, err)
		return
	}
	account, err := signup.PendingAccount(ctx, d.pool, secret, token, at)
	if err != nil {
		serverError(w, err)
		return
	}
	activated := false
	if account != nil {
		if activated, err = signup.Activate(ctx, d.pool, d.getenv, account, at); err != nil {
			serverError(w, err)
			return
		}
	}
	if !activated {
		if err := session.LinkRecordConsumeFailure(ctx, d.pool, ipKey, at); err != nil {
			serverError(w, err)
			return
		}
		page(signupVerifyView("", true, "", 0))
		return
	}
	var username string
	var sv int64
	if err := d.pool.QueryRow(ctx, `SELECT username, session_version FROM user_account WHERE id = $1`, account.ID).
		Scan(&username, &sv); err != nil {
		serverError(w, err)
		return
	}
	// The audit row before the cookies, so a failed write sets none
	// (Python's response is discarded on the same error).
	if err := d.audit(ctx, nil, at, ActionLogin, "method="+SignupMethod, username, ptr(account.ID)); err != nil {
		serverError(w, err)
		return
	}
	if err := d.attach(w, account.ID, sv, session.IssueOptions{}, at); err != nil {
		serverError(w, err)
		return
	}
	keepLoginLanguage(w, r, d.getenv)
	redirect(w, "/")
}
