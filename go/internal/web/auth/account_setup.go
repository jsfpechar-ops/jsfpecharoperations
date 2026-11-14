package auth

// The account setup pages of App/app/routes/admin_accounts.py (brief 1505):
// GET and POST /account/accept (account_accept_form 420-434,
// account_accept_submit 437-460) and GET and POST /account/2fa/setup
// (two_factor_setup_form 470-490, two_factor_setup_submit 493-538).

import (
	"context"
	"crypto/hmac"
	"crypto/sha1"
	"crypto/subtle"
	"encoding/base32"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/jackc/pgx/v5"
	"github.com/skip2/go-qrcode"
	unorm "golang.org/x/text/unicode/norm"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/clientip"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/session"
)

// acctDocuments is acceptance.DOCUMENTS, in order.
var acctDocuments = []string{"terms", "privacy", "dpa"}

// acctDoc is one row of _pending_doc_rows.
type acctDoc struct{ Key, Version, Href string }

type acctAcceptData struct {
	Docs  []acctDoc
	Next  string
	Error string
}

type acctSetupData struct {
	Moved         bool
	Error         string
	QRData        string
	TOTPURI       string
	GroupedSecret string // secret | batch(4) | map('join') | join(' ')
}

type acctRecoveryData struct{ Codes []string }

// acctPending is acceptance.pending: the documents whose current version
// the account has not accepted, in DOCUMENTS order.
func (d deps) acctPending(ctx context.Context, userID int64) ([]string, error) {
	versions := session.CurrentVersions(d.getenv)
	rows, err := d.pool.Query(ctx, `SELECT document, version FROM legal_acceptance WHERE user_account_id = $1`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	accepted := map[[2]string]bool{}
	for rows.Next() {
		var doc, version string
		if err := rows.Scan(&doc, &version); err != nil {
			return nil, err
		}
		accepted[[2]string{doc, version}] = true
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	var out []string
	for _, doc := range acctDocuments {
		if !accepted[[2]string{doc, versions[doc]}] {
			out = append(out, doc)
		}
	}
	return out, nil
}

// acctDocRows is _pending_doc_rows.
func (d deps) acctDocRows(docs []string) []acctDoc {
	versions := session.CurrentVersions(d.getenv)
	out := make([]acctDoc, len(docs))
	for i, doc := range docs {
		out[i] = acctDoc{Key: doc, Version: versions[doc], Href: "/" + doc}
	}
	return out
}

// acctRecord is acceptance.record(user_id, docs, "clickwrap", request): one
// row per document (idempotent) with the visitor address and user agent, and
// the legal_accepted audit row (ids and versions only).
func (d deps) acctRecord(ctx context.Context, r *http.Request, g *gated, userID int64, docs []string, at time.Time) error {
	versions := session.CurrentVersions(d.getenv)
	ua := r.Header.Get("User-Agent")
	if utf8.RuneCountInString(ua) > 300 {
		ua = string([]rune(ua)[:300])
	}
	ip := clientip.Host(r, d.getenv)
	actor := "host"
	var name string
	err := d.pool.QueryRow(ctx, `SELECT username FROM user_account WHERE id = $1`, userID).Scan(&name)
	if err == nil {
		actor = name
	} else if !errors.Is(err, pgx.ErrNoRows) {
		return err
	}
	stamp := session.UTCNow(at)
	var detail []string
	for _, doc := range acctDocuments {
		if !contains(docs, doc) {
			continue
		}
		if _, err := d.pool.Exec(ctx, `INSERT INTO legal_acceptance
			(user_account_id, document, version, accepted_at, method, ip, user_agent)
			VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (user_account_id, document, version) DO NOTHING`,
			userID, doc, versions[doc], stamp, "clickwrap", ip, ua); err != nil {
			return err
		}
		detail = append(detail, doc+"_v"+versions[doc])
	}
	if len(detail) == 0 {
		return nil
	}
	return d.audit(ctx, g, at, "legal_accepted", strings.Join(detail, " ")+" method=clickwrap", actor, ptr(userID))
}

// acctLogin is require_login on a path in _ACCEPTANCE_EXEMPT_PATHS (and in
// the read-only-open prefixes): hostweb.Login sends every pending account to
// /account/accept, so a signed-in, unexpired session passes here directly;
// a signed-out or expired one gets hostweb.Login's answer. ok is false when
// the response is written.
func (d deps) acctLogin(w http.ResponseWriter, r *http.Request, at time.Time) (*gated, bool) {
	h, ok := d.current(w, r, at)
	if !ok {
		return nil, false
	}
	if h != nil && !h.ImpersonationExpired {
		return &gated{h}, true
	}
	h, ok = d.login(w, r, at)
	if !ok {
		return nil, false
	}
	return &gated{h}, true
}

// accountAcceptForm is account_accept_form (GET /account/accept).
func (d deps) accountAcceptForm(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	g, ok := d.acctLogin(w, r, at)
	if !ok {
		return
	}
	docs, err := d.acctPending(r.Context(), g.h.Account.ID)
	if err != nil {
		serverError(w, err)
		return
	}
	next := safeLocalPath(acctLastQuery(r, "next"), "/")
	if len(docs) == 0 {
		redirect(w, locationQuote(next))
		return
	}
	d.acctPageOr500(w, r, acctPage{Name: "account_accept", TitleKey: "account.accept.title", SignedIn: true,
		Data: acctAcceptData{Docs: d.acctDocRows(docs), Next: next}}, at)
}

// accountAcceptSubmit is account_accept_submit (POST /account/accept).
func (d deps) accountAcceptSubmit(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	g, ok := d.acctLogin(w, r, at)
	if !ok {
		return
	}
	ctx := r.Context()
	next := safeLocalPath(formStr(r, "next", ""), "/")
	docs, err := d.acctPending(ctx, g.h.Account.ID)
	if err != nil {
		serverError(w, err)
		return
	}
	if len(docs) == 0 {
		redirect(w, locationQuote(next))
		return
	}
	if formStr(r, "accept", "") != "1" {
		d.acctPageOr500(w, r, acctPage{Name: "account_accept", TitleKey: "account.accept.title", SignedIn: true,
			Status: http.StatusUnprocessableEntity,
			Data:   acctAcceptData{Docs: d.acctDocRows(docs), Next: next, Error: "auth.error.accept_required"}}, at)
		return
	}
	if err := d.acctRecord(ctx, r, g, g.h.Account.ID, docs, at); err != nil {
		serverError(w, err)
		return
	}
	redirect(w, locationQuote(next))
}

// acctPageOr500 renders the page, or answers 500 when that fails.
func (d deps) acctPageOr500(w http.ResponseWriter, r *http.Request, p acctPage, at time.Time) {
	if err := d.acctRender(w, r, p, at); err != nil {
		// A cookie set before the page (the re-issued session) must not
		// survive the 500, as Python discards the whole response.
		w.Header().Del("Set-Cookie")
		serverError(w, err)
	}
}

// acctDecrypt is db.decrypt_secret: "" for no value, and for a value no
// data key opens.
func (d deps) acctDecrypt(enc *string, at time.Time) string {
	if enc == nil || *enc == "" {
		return ""
	}
	keys, err := secure.LoadDataKeys(d.getenv)
	if err != nil {
		return ""
	}
	plain, err := keys.Decrypt(*enc, 0, at)
	if err != nil {
		return ""
	}
	return string(plain)
}

// acctQRData is _totp_qr_data: the otpauth URI as a PNG data URI. Python's
// qrcode.make draws error correction M, 10 pixels per module and a
// four-module border; go-qrcode draws the same layout (the PNG bytes differ).
func acctQRData(uri string) (string, error) {
	q, err := qrcode.New(uri, qrcode.Medium)
	if err != nil {
		return "", err
	}
	png, err := q.PNG(-10)
	if err != nil {
		return "", err
	}
	return "data:image/png;base64," + base64.StdEncoding.EncodeToString(png), nil
}

// acctGroup is secret | batch(4) | map('join') | join(' ').
func acctGroup(secret string) string {
	r := []rune(secret)
	var parts []string
	for i := 0; i < len(r); i += 4 {
		j := i + 4
		if j > len(r) {
			j = len(r)
		}
		parts = append(parts, string(r[i:j]))
	}
	return strings.Join(parts, " ")
}

// acctTOTPAt is pyotp.TOTP(secret).at(step * 30): HOTP-SHA1, six digits.
func acctTOTPAt(secret string, step int64) (string, error) {
	if pad := len(secret) % 8; pad != 0 {
		secret += strings.Repeat("=", 8-pad)
	}
	key, err := base32.StdEncoding.DecodeString(strings.ToUpper(secret))
	if err != nil {
		return "", err
	}
	var msg [8]byte
	binary.BigEndian.PutUint64(msg[:], uint64(step))
	mac := hmac.New(sha1.New, key)
	mac.Write(msg[:])
	sum := mac.Sum(nil)
	off := sum[len(sum)-1] & 0xf
	code := binary.BigEndian.Uint32(sum[off:off+4]) & 0x7fffffff
	return fmt.Sprintf("%06d", code%1000000), nil
}

// acctTOTPVerify is pyotp.TOTP(secret).verify(code, valid_window=1): the
// code of the step before, at or after now, compared after NFKC as
// utils.strings_equal does. No replay watermark: setup has none.
func acctTOTPVerify(secret, code string, now time.Time) bool {
	got := unorm.NFKC.String(code)
	step := now.Unix() / 30
	for _, s := range []int64{step - 1, step, step + 1} {
		want, err := acctTOTPAt(secret, s)
		if err != nil {
			return false
		}
		if subtle.ConstantTimeCompare([]byte(got), []byte(want)) == 1 {
			return true
		}
	}
	return false
}

// acctSetupGates are the shared gates of the two setup routes: signed out to
// /login, an enabled authenticator back to Settings, a login older than ten
// minutes back to Security. account is nil when the response is written.
func (d deps) acctSetupGates(w http.ResponseWriter, r *http.Request, at time.Time) (*session.Host, *session.LoginAccount) {
	h, ok := d.current(w, r, at)
	if !ok {
		return nil, nil
	}
	if h == nil {
		redirect(w, "/login")
		return nil, nil
	}
	account, err := session.AccountByID(r.Context(), d.pool, h.Account.ID)
	if err != nil || account == nil {
		serverError(w, errOr(err))
		return nil, nil
	}
	if account.TOTPEnabled != 0 {
		hostweb.Back(w, r, "/settings", acctFlash(r, "flash.accounts.twofa_enabled", nil), none)
		return nil, nil
	}
	if !session.IsFresh(h.Payload, 0, at) {
		hostweb.Back(w, r, securityPath, none, acctFlash(r, "auth.error.recent_login", nil))
		return nil, nil
	}
	return h, account
}

// acctFlash is admin_helpers.flash(request, key, **params) from the account catalog.
func acctFlash(r *http.Request, key string, params map[string]any) hostweb.Flash {
	return hostweb.Flash{Text: acctCatalog.T(hostweb.Lang(r), key, params), Key: key}
}

// twoFactorSetupForm is two_factor_setup_form (GET /account/2fa/setup):
// the staged secret, or a new one staged now, as a QR code and a key.
func (d deps) twoFactorSetupForm(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	h, account := d.acctSetupGates(w, r, at)
	if account == nil {
		return
	}
	secret := d.acctDecrypt(account.TOTPSecretEnc, at)
	if secret == "" {
		secret = session.NewTOTPSecret()
		if err := session.StageTOTP(r.Context(), d.pool, d.getenv, account.ID, secret); err != nil {
			serverError(w, err)
			return
		}
	}
	uri := session.TOTPURI(secret, h.Account.Username)
	qr, err := acctQRData(uri)
	if err != nil {
		serverError(w, err)
		return
	}
	d.acctPageOr500(w, r, acctPage{Name: "two_factor_setup", TitleKey: "account.2fa.setup_title", SignedIn: true,
		Data: acctSetupData{Moved: acctLastQuery(r, "moved") == "1", QRData: qr, TOTPURI: uri, GroupedSecret: acctGroup(secret)}}, at)
}

// twoFactorSetupSubmit is two_factor_setup_submit (POST /account/2fa/setup):
// a good code switches the authenticator on, shows the recovery codes once
// and re-issues the session (same login time, same remember choice).
func (d deps) twoFactorSetupSubmit(w http.ResponseWriter, r *http.Request) {
	at := d.now()
	if !hostweb.CSRF(w, r, d.getenv, at) {
		return
	}
	h, account := d.acctSetupGates(w, r, at)
	if account == nil {
		return
	}
	remember := remembers(h.Payload)
	code := strings.ReplaceAll(formStr(r, "code", ""), " ", "")
	secret := d.acctDecrypt(account.TOTPSecretEnc, at)
	if secret == "" || !acctTOTPVerify(secret, code, at) {
		data := acctSetupData{Error: "auth.error.setup_code_invalid", GroupedSecret: acctGroup(secret)}
		if secret != "" {
			data.TOTPURI = session.TOTPURI(secret, account.Username)
			qr, err := acctQRData(data.TOTPURI)
			if err != nil {
				serverError(w, err)
				return
			}
			data.QRData = qr
		}
		d.acctPageOr500(w, r, acctPage{Name: "two_factor_setup", TitleKey: "account.2fa.setup_title", SignedIn: true,
			Status: http.StatusBadRequest, Data: data}, at)
		return
	}
	ctx := r.Context()
	codes := session.NewRecoveryCodes(8)
	if err := session.EnableTOTP(ctx, d.pool, d.getenv, account.ID, secret, codes); err != nil {
		serverError(w, err)
		return
	}
	var sv int64
	if err := d.pool.QueryRow(ctx, `SELECT session_version FROM user_account WHERE id = $1`, account.ID).Scan(&sv); err != nil {
		serverError(w, err)
		return
	}
	if err := d.audit(ctx, nil, at, "two_factor_enabled", "", account.Username, ptr(account.ID)); err != nil {
		serverError(w, err)
		return
	}
	iat := session.IssuedAt(h.Payload)
	if err := d.attach(w, account.ID, sv, session.IssueOptions{Remember: remember, IssuedAt: &iat}, at); err != nil {
		serverError(w, err)
		return
	}
	d.acctPageOr500(w, r, acctPage{Name: "two_factor_recovery", TitleKey: "account.2fa.recovery_title", SignedIn: true,
		NoLangSwitch: true, Data: acctRecoveryData{Codes: codes}}, at)
}
