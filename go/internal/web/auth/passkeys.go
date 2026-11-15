package auth

// The passkey routes, ported from App/app/routes/passkeys.py (brief 1760).
// The two ceremonies are JSON endpoints called by static/passkeys.js with the
// CSRF token in the X-CSRF-Token header; rename and delete are plain forms.
// Every gate runs in Python's order: host CSRF, then the path parameter (422),
// then the route body. The routes are dormant until the paths are listed in
// UBYHOST_GO_PATHS (never before the tests and browser checks of brief 1761).

import (
	"context"
	_ "embed"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

//go:embed passkeys_i18n.json
var passkeyCatalogJSON []byte

// passkeyCatalog holds the passkeys.* and flash.passkeys.* strings, written
// from host_i18n.STRINGS by App/scripts/go_host_i18n.py.
var passkeyCatalog = hostweb.Load(passkeyCatalogJSON)

const passkeySecurityPath = "/settings/security#settings-security"

// PasskeyRoutes lists the passkey routes. POST /account/security-prompt/seen
// is already in Routes.
func PasskeyRoutes(pool *pgxpool.Pool, getenv func(string) string, now func() time.Time) []Route {
	x := deps{pool: pool, getenv: getenv, now: now}
	return []Route{
		{"POST /account/passkeys/options", "/account/passkeys/options", x.passkeyRegisterOptions},
		{"POST /account/passkeys", "/account/passkeys", x.passkeyRegister},
		{"POST /account/passkeys/{id}/rename", "/account/passkeys/{id}/rename", x.passkeyRename},
		{"POST /account/passkeys/{id}/delete", "/account/passkeys/{id}/delete", x.passkeyDelete},
		{"POST /login/passkey/options", "/login/passkey/options", x.passkeyLoginOptions},
		{"POST /login/passkey", "/login/passkey", x.passkeyLogin},
	}
}

func pkFlash(r *http.Request, key string) hostweb.Flash {
	return hostweb.Flash{Text: passkeyCatalog.T(hostweb.Lang(r), key, nil), Key: key}
}

// passkeyJSON is a JSONResponse with Cache-Control: no-store.
func passkeyJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Cache-Control", "no-store")
	writeJSON(w, status, body)
}

// passkeyFail is passkeys._error: {"error": text}.
func passkeyFail(w http.ResponseWriter, r *http.Request, key string, status int) {
	passkeyJSON(w, status, map[string]string{"error": passkeyCatalog.T(hostweb.Lang(r), key, nil)})
}

// passkeyOwner is passkeys._owner: the signed-in account managing its own
// passkeys, never a previewed one (an admin looking at a host's workspace must
// not add a way into that host's account). The account is nil when signed out
// or inactive; ok is false after a 500.
func (d deps) passkeyOwner(w http.ResponseWriter, r *http.Request, at time.Time) (*session.Host, *passkeyAccount, bool) {
	h, ok := d.current(w, r, at)
	if !ok {
		return nil, nil, false
	}
	if h == nil {
		return nil, nil, true
	}
	account, err := loadPasskeyAccount(r.Context(), d.pool, h.Account.ID)
	if err != nil {
		serverError(w, err)
		return nil, nil, false
	}
	return h, account, true
}

// passkeyBody is passkeys._body: a JSON object of at most 64 KiB, else {}.
func passkeyBody(r *http.Request) map[string]json.RawMessage {
	empty := map[string]json.RawMessage{}
	raw, err := io.ReadAll(io.LimitReader(r.Body, passkeyBodyMax+1))
	if err != nil || len(raw) == 0 || len(raw) > passkeyBodyMax {
		return empty
	}
	var data map[string]json.RawMessage
	if err := json.Unmarshal(raw, &data); err != nil || data == nil {
		return empty
	}
	return data
}

// rawObject returns the value when it is a JSON object (a Python dict).
func rawObject(m map[string]json.RawMessage, key string) ([]byte, bool) {
	v, ok := m[key]
	if !ok {
		return nil, false
	}
	var obj map[string]json.RawMessage
	if json.Unmarshal(v, &obj) != nil || obj == nil {
		return nil, false
	}
	return v, true
}

// rawString is str(data.get(key) or "") for the string case; other types give "".
func rawString(m map[string]json.RawMessage, key string) string {
	var s string
	if v, ok := m[key]; ok && json.Unmarshal(v, &s) == nil {
		return s
	}
	return ""
}

// rawTruthy is bool(data.get(key, def)) for JSON values.
func rawTruthy(m map[string]json.RawMessage, key string, def bool) bool {
	v, ok := m[key]
	if !ok {
		return def
	}
	var x any
	if json.Unmarshal(v, &x) != nil {
		return def
	}
	switch t := x.(type) {
	case nil:
		return false
	case bool:
		return t
	case float64:
		return t != 0
	case string:
		return t != ""
	case []any:
		return len(t) > 0
	case map[string]any:
		return len(t) > 0
	}
	return true
}

// cleanName is passkeys.clean_name: whitespace folded, 60 characters at most.
func cleanName(name, fallback string) string {
	text := strings.Join(strings.FieldsFunc(name, pySpace), " ")
	if utf8.RuneCountInString(text) > passkeyNameMax {
		text = string([]rune(text)[:passkeyNameMax])
	}
	if text == "" {
		return fallback
	}
	return text
}

// deviceLabel is device_label: a coarse device family from the User-Agent,
// never the full string.
func deviceLabel(userAgent, lang string) string {
	for _, d := range []struct {
		needles []string
		label   string
	}{
		{[]string{"iPhone"}, "iPhone"},
		{[]string{"iPad"}, "iPad"},
		{[]string{"Android"}, "Android"},
		{[]string{"Macintosh", "Mac OS X"}, "Mac"},
		{[]string{"Windows"}, "Windows"},
		{[]string{"CrOS"}, "Chromebook"},
		{[]string{"Linux"}, "Linux"},
	} {
		for _, n := range d.needles {
			if strings.Contains(userAgent, n) {
				return d.label
			}
		}
	}
	return passkeyCatalog.T(lang, "passkeys.default_name", nil)
}

// passkeyBackLocation is the Location hostweb.Back would send.
func passkeyBackLocation(r *http.Request, path string, msg, errFlash hostweb.Flash) string {
	rec := httptest.NewRecorder()
	hostweb.Back(rec, r, path, msg, errFlash)
	return rec.Header().Get("Location")
}

func (d deps) passkeyAudit(ctx context.Context, at time.Time, action, detail, actor string, owner *int64) error {
	return d.audit(ctx, nil, at, action, detail, actor, owner)
}

// passkeyBlocked is passkeys.options_blocked and failures_blocked for the
// scopes named: true when any budget of this connection is spent.
func (d deps) passkeyBlocked(r *http.Request, at time.Time, scopes ...string) (bool, error) {
	key := clientip.Key(r, d.getenv, "")
	for _, s := range scopes {
		limit := passkeyOptionsMax
		if s == passkeyFailScope {
			limit = passkeyFailMax
		}
		if b, err := session.RateBlocked(r.Context(), d.pool, s, key, limit, passkeyWindow, at); b || err != nil {
			return b, err
		}
	}
	return false, nil
}

func (d deps) passkeyRecord(r *http.Request, scope string, at time.Time) error {
	return session.RateRecord(r.Context(), d.pool, scope, clientip.Key(r, d.getenv, ""), at)
}

// passkeyRegisterOptions is passkey_register_options.
func (d deps) passkeyRegisterOptions(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	h, account, ok := d.passkeyOwner(w, r, at)
	if !ok {
		return
	}
	if account == nil {
		passkeyFail(w, r, "passkeys.error.signed_out", http.StatusUnauthorized)
		return
	}
	wa := passkeyConfig(d.getenv)
	if wa == nil {
		passkeyFail(w, r, "passkeys.error.unavailable", http.StatusConflict)
		return
	}
	if !session.IsFresh(h.Payload, 0, at) {
		passkeyFail(w, r, "auth.error.recent_login", http.StatusForbidden)
		return
	}
	n, err := passkeyCount(r.Context(), d.pool, account.ID)
	if err != nil {
		serverError(w, err)
		return
	}
	if n >= passkeyMax {
		passkeyFail(w, r, "passkeys.error.too_many", http.StatusConflict)
		return
	}
	blocked, err := d.passkeyBlocked(r, at, passkeyOptionsScope)
	if err != nil {
		serverError(w, err)
		return
	}
	if blocked {
		passkeyFail(w, r, "passkeys.error.rate_limited", http.StatusTooManyRequests)
		return
	}
	if err := d.passkeyRecord(r, passkeyOptionsScope, at); err != nil {
		serverError(w, err)
		return
	}
	options, err := registrationOptions(r.Context(), d.pool, wa, account, at)
	if err != nil {
		serverError(w, err)
		return
	}
	passkeyJSON(w, http.StatusOK, options)
}

// passkeyRegister is passkey_register.
func (d deps) passkeyRegister(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	h, account, ok := d.passkeyOwner(w, r, at)
	if !ok {
		return
	}
	if account == nil {
		passkeyFail(w, r, "passkeys.error.signed_out", http.StatusUnauthorized)
		return
	}
	if !session.IsFresh(h.Payload, 0, at) {
		passkeyFail(w, r, "auth.error.recent_login", http.StatusForbidden)
		return
	}
	data := passkeyBody(r)
	credential, isObject := rawObject(data, "credential")
	if !isObject {
		passkeyFail(w, r, "passkeys.error.failed", http.StatusBadRequest)
		return
	}
	wa := passkeyConfig(d.getenv)
	if wa == nil {
		passkeyFail(w, r, "passkeys.error.failed", http.StatusBadRequest)
		return
	}
	lang := hostweb.Lang(r)
	name := cleanName(rawString(data, "name"), deviceLabel(r.Header.Get("User-Agent"), lang))
	ctx := r.Context()
	passkeyID, err := registerPasskey(ctx, d.pool, wa, account, credential, name, at)
	if err != nil {
		var pe *passkeyError
		if !errors.As(err, &pe) {
			serverError(w, err)
			return
		}
		if err := d.passkeyAudit(ctx, at, "passkey_add_failed", "reason="+pe.reason, account.Username, ptr(account.ID)); err != nil {
			serverError(w, err)
			return
		}
		key := "passkeys.error.failed"
		if pe.reason == "too_many" {
			key = "passkeys.error.too_many"
		}
		passkeyFail(w, r, key, http.StatusBadRequest)
		return
	}
	// A second way in counts as "secured": the one-time prompt is done.
	if _, err := d.pool.Exec(ctx, `UPDATE user_account SET two_factor_prompted_at = $1 WHERE id = $2 AND two_factor_prompted_at IS NULL`,
		session.UTCNow(at), account.ID); err != nil {
		serverError(w, err)
		return
	}
	if err := d.passkeyAudit(ctx, at, "passkey_added", "passkey="+itoa(passkeyID), account.Username, ptr(account.ID)); err != nil {
		serverError(w, err)
		return
	}
	outboxID, err := mail.QueuePasskeyAdded(ctx, d.pool, d.getenv, account.ID, account.Email, passkeyID, name, at)
	if err != nil {
		serverError(w, err)
		return
	}
	if outboxID != 0 {
		pool, getenv := d.pool, d.getenv
		acctBackground(func() { _ = acctSendNow(context.Background(), pool, getenv, outboxID) })
	}
	returnTo := safeLocalPath(rawString(data, "return_to"), passkeySecurityPath)
	target := passkeyBackLocation(r, returnTo, pkFlash(r, "flash.passkeys.added"), none)
	passkeyJSON(w, http.StatusOK, map[string]string{"redirect": target})
}

// passkeyRename is passkey_rename.
func (d deps) passkeyRename(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	id, ok := pathID(w, r, "passkey_id")
	if !ok {
		return
	}
	_, account, ok := d.passkeyOwner(w, r, at)
	if !ok {
		return
	}
	if account == nil {
		redirect(w, "/login")
		return
	}
	name := cleanName(formStr(r, "name", ""), "")
	if name != "" {
		tag, err := d.pool.Exec(r.Context(), `UPDATE passkey SET name = $1 WHERE id = $2 AND user_account_id = $3`, name, id, account.ID)
		if err != nil {
			serverError(w, err)
			return
		}
		if tag.RowsAffected() != 1 {
			name = ""
		}
	}
	if name == "" {
		hostweb.Back(w, r, passkeySecurityPath, none, pkFlash(r, "flash.passkeys.not_found"))
		return
	}
	if err := d.passkeyAudit(r.Context(), at, "passkey_renamed", "passkey="+itoa(id), account.Username, ptr(account.ID)); err != nil {
		serverError(w, err)
		return
	}
	hostweb.Back(w, r, passkeySecurityPath, pkFlash(r, "flash.passkeys.renamed"), none)
}

// passkeyDelete is passkey_delete.
func (d deps) passkeyDelete(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	id, ok := pathID(w, r, "passkey_id")
	if !ok {
		return
	}
	h, account, ok := d.passkeyOwner(w, r, at)
	if !ok {
		return
	}
	if account == nil {
		redirect(w, "/login")
		return
	}
	if !session.IsFresh(h.Payload, 0, at) {
		hostweb.Back(w, r, passkeySecurityPath, none, pkFlash(r, "auth.error.recent_login"))
		return
	}
	var gone int64
	err := d.pool.QueryRow(r.Context(), `DELETE FROM passkey WHERE id = $1 AND user_account_id = $2 RETURNING id`, id, account.ID).Scan(&gone)
	if errors.Is(err, pgx.ErrNoRows) {
		hostweb.Back(w, r, passkeySecurityPath, none, pkFlash(r, "flash.passkeys.not_found"))
		return
	}
	if err != nil {
		serverError(w, err)
		return
	}
	if err := d.passkeyAudit(r.Context(), at, "passkey_removed", "passkey="+itoa(id), account.Username, ptr(account.ID)); err != nil {
		serverError(w, err)
		return
	}
	hostweb.Back(w, r, passkeySecurityPath, pkFlash(r, "flash.passkeys.removed"), none)
}

// passkeyLoginOptions is passkey_login_options.
func (d deps) passkeyLoginOptions(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	wa := passkeyConfig(d.getenv)
	if wa == nil {
		passkeyFail(w, r, "passkeys.error.unavailable", http.StatusConflict)
		return
	}
	blocked, err := d.passkeyBlocked(r, at, passkeyOptionsScope, passkeyFailScope)
	if err != nil {
		serverError(w, err)
		return
	}
	if blocked {
		passkeyFail(w, r, "passkeys.error.rate_limited", http.StatusTooManyRequests)
		return
	}
	if err := d.passkeyRecord(r, passkeyOptionsScope, at); err != nil {
		serverError(w, err)
		return
	}
	options, err := authenticationOptions(r.Context(), d.pool, wa, at)
	if err != nil {
		serverError(w, err)
		return
	}
	passkeyJSON(w, http.StatusOK, options)
}

// passkeyLogin is passkey_login.
func (d deps) passkeyLogin(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	ctx := r.Context()
	blocked, err := d.passkeyBlocked(r, at, passkeyFailScope)
	if err != nil {
		serverError(w, err)
		return
	}
	if blocked {
		passkeyFail(w, r, "passkeys.error.rate_limited", http.StatusTooManyRequests)
		return
	}
	data := passkeyBody(r)
	credential, isObject := rawObject(data, "credential")
	if !isObject {
		if err := d.passkeyRecord(r, passkeyFailScope, at); err != nil {
			serverError(w, err)
			return
		}
		passkeyFail(w, r, "passkeys.error.login_failed", http.StatusBadRequest)
		return
	}
	var (
		account *passkeyAccount
		row     *passkeyRow
	)
	if wa := passkeyConfig(d.getenv); wa == nil {
		err = failed("unavailable")
	} else {
		account, row, err = authenticatePasskey(ctx, d.pool, wa, credential, at)
	}
	if err != nil {
		var pe *passkeyError
		if !errors.As(err, &pe) {
			serverError(w, err)
			return
		}
		if err := d.passkeyRecord(r, passkeyFailScope, at); err != nil {
			serverError(w, err)
			return
		}
		if pe.reason == "sign_count" && account != nil && row != nil {
			// Probably a cloned authenticator: tell the owner's audit log.
			err = d.passkeyAudit(ctx, at, "passkey_clone_suspected", "passkey="+itoa(row.ID), account.Username, ptr(account.ID))
		} else {
			err = d.passkeyAudit(ctx, at, "passkey_login_failed", "reason="+pe.reason, "anonymous", nil)
		}
		if err != nil {
			serverError(w, err)
			return
		}
		passkeyFail(w, r, "passkeys.error.login_failed", http.StatusUnauthorized)
		return
	}
	login, err := session.AccountByID(ctx, d.pool, account.ID)
	if err != nil || login == nil {
		if err == nil {
			err = errors.New("passkey account vanished")
		}
		serverError(w, err)
		return
	}
	remember := rawTruthy(data, "remember", true)
	location, err := d.startSession(w, r, login, remember, rawString(data, "next"), MethodPasskey(row.ID), ActionLogin, at)
	if err != nil {
		serverError(w, err)
		return
	}
	passkeyJSON(w, http.StatusOK, map[string]string{"redirect": location})
}
