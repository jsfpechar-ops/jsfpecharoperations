package auth

// Tests for the passkey routes (PasskeyRoutes) on Postgres. Each test gets its
// own database from testPool. The software authenticator in
// passkeys_authenticator_test.go answers the ceremonies.

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/secure"
)

const (
	pkTestSecret = "passkey-routes-test-secret-0123456789-abcdef"
	pkRPID       = "ubyhost.example.test"
	pkOrigin     = "https://ubyhost.example.test"
	pkCSRFNonce  = "passkey-routes-csrf-nonce"
	pkStamp      = "2001-01-01T00:00:00.000000+00:00"
	pkUA         = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15"
)

type pkHarness struct {
	t      *testing.T
	pool   *pgxpool.Pool
	ctx    context.Context
	now    time.Time
	mux    *http.ServeMux
	csrf   string
	alice  int64
	bob    int64
	aliceS string // a fresh session for alice
	bobS   string // a fresh session for bob
}

// newPkHarness seeds two hosts on a fresh database and mounts PasskeyRoutes.
func newPkHarness(t *testing.T) *pkHarness {
	t.Helper()
	pool := testPool(t)
	env := map[string]string{
		"UBYHOST_SECRET_KEY":      pkTestSecret,
		"UBYHOST_DEPLOYMENT":      "local",
		"UBYHOST_PUBLIC_BASE_URL": "https://ubyhost.example.test",
		"UBYHOST_APP_BASE_URL":    "https://app.ubyhost.example.test",
	}
	getenv := func(k string) string { return env[k] }
	now := time.Now()
	ctx := context.Background()
	loadSeed(t, ctx, pool, [][2]any{
		{"user_account", pkUser(1, "alice")},
		{"user_account", pkUser(2, "bob")},
	}, now)
	sum := sha256.Sum256([]byte(pkCSRFNonce))
	token, err := secure.NewTimedSerializer(pkTestSecret, "ubyhost-csrf").Dumps(map[string]any{"nonce": hex.EncodeToString(sum[:])}, now)
	if err != nil {
		t.Fatal(err)
	}
	h := &pkHarness{t: t, pool: pool, ctx: ctx, now: now, csrf: token, alice: 1, bob: 2}
	h.aliceS = sessionToken(t, pkTestSecret, map[string]int64{"uid": 1, "iat": -60}, now)
	h.bobS = sessionToken(t, pkTestSecret, map[string]int64{"uid": 2, "iat": -60}, now)
	h.mux = http.NewServeMux()
	for _, r := range PasskeyRoutes(pool, getenv, time.Now) {
		h.mux.HandleFunc(r.Pattern, r.Handler)
	}
	return h
}

func pkUser(id int64, name string) map[string]any {
	return map[string]any{
		"id": id, "username": name, "email": name + "@example.test", "active": 1, "role": "host",
		"session_version": 1, "password_hash": "", "must_change_password": 0, "created_at": pkStamp,
	}
}

// pkRequest is one POST. A non-nil form is sent url-encoded with the _csrf
// field (rename and delete); otherwise body is sent as JSON with the CSRF
// header (the ceremonies).
type pkRequest struct {
	path    string
	form    url.Values
	body    string
	session string
	noCSRF  bool
	ua      string
}

func (h *pkHarness) post(in pkRequest) *httptest.ResponseRecorder {
	h.t.Helper()
	ct := "application/json"
	body := in.body
	if in.form != nil {
		ct = "application/x-www-form-urlencoded"
		if !in.noCSRF {
			in.form.Set("_csrf", h.csrf)
		}
		body = in.form.Encode()
	}
	req := httptest.NewRequest(http.MethodPost, "http://testserver"+in.path, strings.NewReader(body))
	req.Header.Set("Content-Type", ct)
	var cookies []string
	if in.session != "" {
		cookies = append(cookies, "ubyhost_session="+in.session)
	}
	if !in.noCSRF {
		cookies = append(cookies, "ubyhost_csrf="+pkCSRFNonce)
		if in.form == nil {
			req.Header.Set("X-CSRF-Token", h.csrf)
		}
	}
	if len(cookies) > 0 {
		req.Header.Set("Cookie", strings.Join(cookies, "; "))
	}
	if in.ua != "" {
		req.Header.Set("User-Agent", in.ua)
	}
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	return rec
}

// pkOptions is the part of the creation options the tests read.
type pkOptions struct {
	Challenge string `json:"challenge"`
	RP        struct {
		ID   string `json:"id"`
		Name string `json:"name"`
	} `json:"rp"`
	User struct {
		ID string `json:"id"`
	} `json:"user"`
	AuthenticatorSelection struct {
		ResidentKey        string `json:"residentKey"`
		RequireResidentKey *bool  `json:"requireResidentKey"`
		UserVerification   string `json:"userVerification"`
	} `json:"authenticatorSelection"`
}

func (h *pkHarness) options(session string) (*httptest.ResponseRecorder, pkOptions) {
	h.t.Helper()
	rec := h.post(pkRequest{path: "/account/passkeys/options", session: session})
	var o pkOptions
	if rec.Code == http.StatusOK {
		if err := json.Unmarshal(rec.Body.Bytes(), &o); err != nil {
			h.t.Fatalf("options body: %v", err)
		}
	}
	return rec, o
}

func (h *pkHarness) register(session string, cred map[string]any, name string, ua string) *httptest.ResponseRecorder {
	h.t.Helper()
	raw, err := json.Marshal(map[string]any{"credential": cred, "name": name})
	if err != nil {
		h.t.Fatal(err)
	}
	return h.post(pkRequest{path: "/account/passkeys", body: string(raw), session: session, ua: ua})
}

// registerFor runs options then the authenticator's answer for the same
// challenge, as the browser does.
func (h *pkHarness) registerFor(session string, a *softAuthenticator, origin, rpID, name string) *httptest.ResponseRecorder {
	h.t.Helper()
	rec, o := h.options(session)
	if rec.Code != http.StatusOK {
		h.t.Fatalf("options: %d %s", rec.Code, rec.Body.String())
	}
	cred := a.Register(h.t, ceremonyInput{Challenge: o.Challenge, Origin: origin, RPID: rpID}, 3)
	return h.register(session, cred, name, pkUA)
}

func decodeError(t *testing.T, rec *httptest.ResponseRecorder) string {
	t.Helper()
	var out map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("body is not JSON: %q", rec.Body.String())
	}
	msg, _ := out["error"].(string)
	if msg == "" {
		t.Fatalf("no error text in %q", rec.Body.String())
	}
	return msg
}

func (h *pkHarness) assertNoCache(rec *httptest.ResponseRecorder) {
	h.t.Helper()
	if got := rec.Header().Get("Cache-Control"); got != "no-store" {
		h.t.Errorf("Cache-Control %q, want no-store", got)
	}
}

type pkAudit struct {
	Action string
	Actor  string
	Detail string
	Owner  *int64
}

func (h *pkHarness) audits() []pkAudit {
	h.t.Helper()
	rows, err := h.pool.Query(h.ctx, `SELECT action, COALESCE(actor, ''), COALESCE(detail, ''), owner_user_id FROM audit ORDER BY id`)
	if err != nil {
		h.t.Fatal(err)
	}
	defer rows.Close()
	var out []pkAudit
	for rows.Next() {
		var a pkAudit
		if err := rows.Scan(&a.Action, &a.Actor, &a.Detail, &a.Owner); err != nil {
			h.t.Fatal(err)
		}
		out = append(out, a)
	}
	return out
}

func (h *pkHarness) auditCount(action string) int {
	h.t.Helper()
	n := 0
	for _, a := range h.audits() {
		if a.Action == action {
			n++
		}
	}
	return n
}

func (h *pkHarness) passkeyCount(uid int64) int {
	h.t.Helper()
	var n int
	if err := h.pool.QueryRow(h.ctx, `SELECT COUNT(*) FROM passkey WHERE user_account_id = $1`, uid).Scan(&n); err != nil {
		h.t.Fatal(err)
	}
	return n
}

// insertPasskey adds a stored passkey row directly (for the management tests).
func (h *pkHarness) insertPasskey(uid int64, credID, name string) int64 {
	h.t.Helper()
	var id int64
	err := h.pool.QueryRow(h.ctx, `INSERT INTO passkey (user_account_id, credential_id, public_key, sign_count, transports, name, backed_up, created_at)
		VALUES ($1, $2, 'cHVibGlj', 0, NULL, $3, 0, $4) RETURNING id`, uid, credID, name, pkStamp).Scan(&id)
	if err != nil {
		h.t.Fatal(err)
	}
	return id
}

func (h *pkHarness) passkeyName(id int64) (string, bool) {
	h.t.Helper()
	var name string
	err := h.pool.QueryRow(h.ctx, `SELECT name FROM passkey WHERE id = $1`, id).Scan(&name)
	if err != nil {
		return "", false
	}
	return name, true
}

// pkText is the text of a passkey flash key in the default language, which
// is what a request without a language cookie gets.
func pkText(key string) string {
	return passkeyCatalog.T(hostweb.DefaultLanguage, key, nil)
}

// location parses a Location header and returns its path, query and fragment.
func location(t *testing.T, rec *httptest.ResponseRecorder) *url.URL {
	t.Helper()
	u, err := url.Parse(rec.Header().Get("Location"))
	if err != nil {
		t.Fatalf("bad Location %q", rec.Header().Get("Location"))
	}
	return u
}

func b64Decode(t *testing.T, s string) []byte {
	t.Helper()
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimRight(s, "="))
	if err != nil {
		t.Fatalf("not base64url: %q", s)
	}
	return raw
}

// --- options ---------------------------------------------------------------

func TestPasskeyOptionsSignedOut(t *testing.T) {
	h := newPkHarness(t)
	rec, _ := h.options("")
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("status %d, want 401", rec.Code)
	}
	decodeError(t, rec)
	h.assertNoCache(rec)
	if n := h.passkeyCount(h.alice); n != 0 {
		t.Errorf("passkey rows %d", n)
	}
}

func TestPasskeyOptionsStaleSession(t *testing.T) {
	h := newPkHarness(t)
	stale := sessionToken(t, pkTestSecret, map[string]int64{"uid": 1, "iat": -601}, h.now)
	rec, _ := h.options(stale)
	if rec.Code != http.StatusForbidden {
		t.Fatalf("status %d, want 403", rec.Code)
	}
	decodeError(t, rec)
	h.assertNoCache(rec)
	var n int
	_ = h.pool.QueryRow(h.ctx, `SELECT COUNT(*) FROM webauthn_challenge`).Scan(&n)
	if n != 0 {
		t.Errorf("challenge rows %d, want 0", n)
	}
}

func TestPasskeyRoutesNeedCSRF(t *testing.T) {
	h := newPkHarness(t)
	rec := h.post(pkRequest{path: "/account/passkeys/options", session: h.aliceS, noCSRF: true})
	if rec.Code == http.StatusOK {
		t.Fatalf("options without CSRF returned 200")
	}
	cred := newSoftAuthenticator(t).Register(t, ceremonyInput{Challenge: "AAAA", Origin: pkOrigin, RPID: pkRPID}, 0)
	raw, _ := json.Marshal(map[string]any{"credential": cred})
	rec = h.post(pkRequest{path: "/account/passkeys", body: string(raw), session: h.aliceS, noCSRF: true})
	if rec.Code == http.StatusOK {
		t.Fatalf("register without CSRF returned 200")
	}
	if n := h.passkeyCount(h.alice); n != 0 {
		t.Errorf("passkey rows %d, want 0", n)
	}
}

func TestPasskeyOptionsShape(t *testing.T) {
	h := newPkHarness(t)
	rec, o := h.options(h.aliceS)
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body.String())
	}
	h.assertNoCache(rec)
	if o.RP.ID != pkRPID {
		t.Errorf("rp.id %q, want %q", o.RP.ID, pkRPID)
	}
	if got := len(b64Decode(t, o.Challenge)); got < 16 {
		t.Errorf("challenge is %d bytes", got)
	}
	sel := o.AuthenticatorSelection
	if sel.ResidentKey != "required" || sel.RequireResidentKey == nil || !*sel.RequireResidentKey {
		t.Errorf("residentKey %q requireResidentKey %v, want required", sel.ResidentKey, sel.RequireResidentKey)
	}
	if sel.UserVerification != "required" {
		t.Errorf("userVerification %q, want required", sel.UserVerification)
	}

	var handle *string
	if err := h.pool.QueryRow(h.ctx, `SELECT webauthn_user_handle FROM user_account WHERE id = $1`, h.alice).Scan(&handle); err != nil {
		t.Fatal(err)
	}
	if handle == nil || *handle == "" {
		t.Fatal("webauthn_user_handle not written")
	}
	if o.User.ID != *handle {
		t.Errorf("user.id %q does not match stored handle", o.User.ID)
	}

	var (
		purpose string
		owner   *int64
		used    *string
	)
	err := h.pool.QueryRow(h.ctx, `SELECT purpose, user_account_id, used_at FROM webauthn_challenge WHERE challenge_hash = $1`,
		challengeHash(b64Decode(t, o.Challenge))).Scan(&purpose, &owner, &used)
	if err != nil {
		t.Fatalf("no challenge row for the issued challenge: %v", err)
	}
	if purpose != "register" || owner == nil || *owner != h.alice || used != nil {
		t.Errorf("challenge row purpose=%q owner=%v used=%v", purpose, owner, used)
	}
}

// --- registration ----------------------------------------------------------

func TestPasskeyRegisterHappyPath(t *testing.T) {
	h := newPkHarness(t)
	a := newSoftAuthenticator(t)
	rec := h.registerFor(h.aliceS, a, pkOrigin, pkRPID, "Laptop")
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body.String())
	}
	h.assertNoCache(rec)
	var out map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	u, err := url.Parse(out["redirect"])
	if err != nil {
		t.Fatal(err)
	}
	if u.Path != "/settings/security" || u.Fragment != "settings-security" || u.Query().Get("msg") != pkText("flash.passkeys.added") {
		t.Errorf("redirect %q", out["redirect"])
	}

	var (
		credID, name, transports string
		signCount, backedUp      int64
		publicKey                string
	)
	err = h.pool.QueryRow(h.ctx, `SELECT credential_id, name, sign_count, backed_up, transports, public_key FROM passkey WHERE user_account_id = $1`, h.alice).
		Scan(&credID, &name, &signCount, &backedUp, &transports, &publicKey)
	if err != nil {
		t.Fatalf("passkey row: %v", err)
	}
	if credID != a.ID() {
		t.Errorf("credential_id %q, want %q", credID, a.ID())
	}
	if name != "Laptop" || signCount != 3 || backedUp != 0 || transports != "internal" || publicKey == "" {
		t.Errorf("row name=%q sign_count=%d backed_up=%d transports=%q", name, signCount, backedUp, transports)
	}

	var used *string
	if err := h.pool.QueryRow(h.ctx, `SELECT used_at FROM webauthn_challenge WHERE purpose = 'register'`).Scan(&used); err != nil {
		t.Fatal(err)
	}
	if used == nil {
		t.Error("challenge not spent")
	}

	var prompted *string
	if err := h.pool.QueryRow(h.ctx, `SELECT two_factor_prompted_at FROM user_account WHERE id = $1`, h.alice).Scan(&prompted); err != nil {
		t.Fatal(err)
	}
	if prompted == nil {
		t.Error("two_factor_prompted_at not set")
	}

	added := h.audits()
	if h.auditCount("passkey_added") != 1 || h.auditCount("passkey_add_failed") != 0 {
		t.Fatalf("audit rows %+v", added)
	}
	for _, a := range added {
		if a.Action == "passkey_added" && (a.Actor != "alice" || a.Owner == nil || *a.Owner != h.alice || !strings.HasPrefix(a.Detail, "passkey=")) {
			t.Errorf("passkey_added row %+v", a)
		}
	}
}

func TestPasskeyRegisterDeviceLabelFromUserAgent(t *testing.T) {
	h := newPkHarness(t)
	a := newSoftAuthenticator(t)
	rec, o := h.options(h.aliceS)
	if rec.Code != http.StatusOK {
		t.Fatalf("options %d", rec.Code)
	}
	cred := a.Register(t, ceremonyInput{Challenge: o.Challenge, Origin: pkOrigin, RPID: pkRPID}, 0)
	rec = h.register(h.aliceS, cred, "  ", pkUA)
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body.String())
	}
	var name string
	if err := h.pool.QueryRow(h.ctx, `SELECT name FROM passkey WHERE credential_id = $1`, a.ID()).Scan(&name); err != nil {
		t.Fatal(err)
	}
	if name != "Mac" {
		t.Errorf("name %q, want Mac", name)
	}
}

func TestPasskeyRegisterReplay(t *testing.T) {
	h := newPkHarness(t)
	a := newSoftAuthenticator(t)
	rec, o := h.options(h.aliceS)
	if rec.Code != http.StatusOK {
		t.Fatalf("options %d", rec.Code)
	}
	cred := a.Register(t, ceremonyInput{Challenge: o.Challenge, Origin: pkOrigin, RPID: pkRPID}, 0)
	if rec := h.register(h.aliceS, cred, "First", pkUA); rec.Code != http.StatusOK {
		t.Fatalf("first register %d: %s", rec.Code, rec.Body.String())
	}
	rec = h.register(h.aliceS, cred, "Again", pkUA)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("replay status %d, want 400", rec.Code)
	}
	decodeError(t, rec)
	if n := h.passkeyCount(h.alice); n != 1 {
		t.Errorf("passkey rows %d, want 1", n)
	}
	if h.auditCount("passkey_add_failed") != 1 {
		t.Errorf("audit %+v", h.audits())
	}
}

// TestPasskeyRegisterRejections: each answer that proves nothing is a 400, a
// passkey_add_failed audit row with its reason, and no stored passkey.
func TestPasskeyRegisterRejections(t *testing.T) {
	cases := []struct {
		name   string
		reason string
		run    func(h *pkHarness, a *softAuthenticator) *httptest.ResponseRecorder
	}{
		{"challenge of another user", "challenge", func(h *pkHarness, a *softAuthenticator) *httptest.ResponseRecorder {
			_, o := h.options(h.bobS)
			cred := a.Register(h.t, ceremonyInput{Challenge: o.Challenge, Origin: pkOrigin, RPID: pkRPID}, 0)
			return h.register(h.aliceS, cred, "x", pkUA)
		}},
		{"wrong origin", "invalid", func(h *pkHarness, a *softAuthenticator) *httptest.ResponseRecorder {
			return h.registerFor(h.aliceS, a, "https://evil.example.test", pkRPID, "x")
		}},
		{"wrong rpId", "invalid", func(h *pkHarness, a *softAuthenticator) *httptest.ResponseRecorder {
			return h.registerFor(h.aliceS, a, pkOrigin, "evil.example.test", "x")
		}},
		{"expired challenge", "challenge", func(h *pkHarness, a *softAuthenticator) *httptest.ResponseRecorder {
			rec, o := h.options(h.aliceS)
			if rec.Code != http.StatusOK {
				h.t.Fatalf("options %d", rec.Code)
			}
			if _, err := h.pool.Exec(h.ctx, `UPDATE webauthn_challenge SET expires_at = $1`, pkStamp); err != nil {
				h.t.Fatal(err)
			}
			cred := a.Register(h.t, ceremonyInput{Challenge: o.Challenge, Origin: pkOrigin, RPID: pkRPID}, 0)
			return h.register(h.aliceS, cred, "x", pkUA)
		}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			h := newPkHarness(t)
			rec := c.run(h, newSoftAuthenticator(t))
			if rec.Code != http.StatusBadRequest {
				t.Fatalf("status %d, want 400: %s", rec.Code, rec.Body.String())
			}
			decodeError(t, rec)
			if n := h.passkeyCount(h.alice); n != 0 {
				t.Errorf("passkey rows %d, want 0", n)
			}
			var got string
			for _, a := range h.audits() {
				if a.Action == "passkey_add_failed" {
					got = a.Detail
				}
			}
			if got != "reason="+c.reason {
				t.Errorf("audit detail %q, want reason=%s", got, c.reason)
			}
		})
	}
}

func TestPasskeyRegisterLimitTen(t *testing.T) {
	h := newPkHarness(t)
	for i := 0; i < 9; i++ {
		h.insertPasskey(h.alice, "cred-"+string(rune('a'+i)), "k")
	}
	rec, o := h.options(h.aliceS)
	if rec.Code != http.StatusOK {
		t.Fatalf("options at 9 passkeys: %d", rec.Code)
	}
	h.insertPasskey(h.alice, "cred-tenth", "k")
	a := newSoftAuthenticator(t)
	cred := a.Register(t, ceremonyInput{Challenge: o.Challenge, Origin: pkOrigin, RPID: pkRPID}, 0)
	rec = h.register(h.aliceS, cred, "Eleventh", pkUA)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("register at 10 passkeys: %d, want 400", rec.Code)
	}
	decodeError(t, rec)
	rec, _ = h.options(h.aliceS)
	if rec.Code != http.StatusConflict {
		t.Fatalf("options at 10 passkeys: %d, want 409", rec.Code)
	}
	decodeError(t, rec)
	if n := h.passkeyCount(h.alice); n != 10 {
		t.Errorf("passkey rows %d, want 10", n)
	}
}

func TestPasskeyRegisterDuplicateCredential(t *testing.T) {
	h := newPkHarness(t)
	a := newSoftAuthenticator(t)
	if rec := h.registerFor(h.aliceS, a, pkOrigin, pkRPID, "First"); rec.Code != http.StatusOK {
		t.Fatalf("first register %d: %s", rec.Code, rec.Body.String())
	}
	rec := h.registerFor(h.aliceS, a, pkOrigin, pkRPID, "Second")
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("duplicate status %d, want 400: %s", rec.Code, rec.Body.String())
	}
	decodeError(t, rec)
	if n := h.passkeyCount(h.alice); n != 1 {
		t.Errorf("passkey rows %d, want 1", n)
	}
	last := h.audits()
	if got := last[len(last)-1]; got.Action != "passkey_add_failed" || got.Detail != "reason=duplicate" {
		t.Errorf("last audit %+v, want passkey_add_failed reason=duplicate", got)
	}
}

// --- rename and delete -----------------------------------------------------

func TestPasskeyRenameOwn(t *testing.T) {
	h := newPkHarness(t)
	id := h.insertPasskey(h.alice, "own-cred", "Old")
	rec := h.post(pkRequest{path: "/account/passkeys/" + itoa(id) + "/rename", form: url.Values{"name": {"  Work   key "}}, session: h.aliceS})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status %d", rec.Code)
	}
	u := location(t, rec)
	if u.Path != "/settings/security" || u.Fragment != "settings-security" || u.Query().Get("msg") != pkText("flash.passkeys.renamed") {
		t.Errorf("Location %q", rec.Header().Get("Location"))
	}
	if name, _ := h.passkeyName(id); name != "Work key" {
		t.Errorf("name %q, want %q", name, "Work key")
	}
	if h.auditCount("passkey_renamed") != 1 {
		t.Errorf("audit %+v", h.audits())
	}
}

func TestPasskeyRenameForeignOrEmpty(t *testing.T) {
	h := newPkHarness(t)
	own := h.insertPasskey(h.alice, "own-cred", "Mine")
	bobs := h.insertPasskey(h.bob, "bob-cred", "Bobs")
	for _, c := range []struct {
		name string
		id   int64
		form url.Values
	}{
		{"other user's passkey", bobs, url.Values{"name": {"Hijacked"}}},
		{"empty name", own, url.Values{"name": {"   "}}},
	} {
		rec := h.post(pkRequest{path: "/account/passkeys/" + itoa(c.id) + "/rename", form: c.form, session: h.aliceS})
		if rec.Code != http.StatusSeeOther {
			t.Fatalf("%s: status %d", c.name, rec.Code)
		}
		if got := location(t, rec).Query().Get("err"); got != pkText("flash.passkeys.not_found") {
			t.Errorf("%s: msg %q", c.name, got)
		}
	}
	if name, _ := h.passkeyName(bobs); name != "Bobs" {
		t.Errorf("bob's passkey renamed to %q", name)
	}
	if name, _ := h.passkeyName(own); name != "Mine" {
		t.Errorf("own passkey renamed to %q on empty name", name)
	}
}

func TestPasskeyRenameBadID(t *testing.T) {
	h := newPkHarness(t)
	rec := h.post(pkRequest{path: "/account/passkeys/abc/rename", form: url.Values{"name": {"x"}}, session: h.aliceS})
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status %d, want 422", rec.Code)
	}
}

func TestPasskeyDeleteOwn(t *testing.T) {
	h := newPkHarness(t)
	id := h.insertPasskey(h.alice, "own-cred", "Mine")
	rec := h.post(pkRequest{path: "/account/passkeys/" + itoa(id) + "/delete", form: url.Values{}, session: h.aliceS})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status %d", rec.Code)
	}
	if got := location(t, rec).Query().Get("msg"); got != pkText("flash.passkeys.removed") {
		t.Errorf("msg %q", got)
	}
	if n := h.passkeyCount(h.alice); n != 0 {
		t.Errorf("passkey rows %d, want 0", n)
	}
	var found bool
	for _, a := range h.audits() {
		if a.Action == "passkey_removed" && a.Detail == "passkey="+itoa(id) && a.Actor == "alice" {
			found = true
		}
	}
	if !found {
		t.Errorf("no passkey_removed audit row: %+v", h.audits())
	}
}

func TestPasskeyDeleteNeedsFreshSession(t *testing.T) {
	h := newPkHarness(t)
	id := h.insertPasskey(h.alice, "own-cred", "Mine")
	stale := sessionToken(t, pkTestSecret, map[string]int64{"uid": 1, "iat": -601}, h.now)
	rec := h.post(pkRequest{path: "/account/passkeys/" + itoa(id) + "/delete", form: url.Values{}, session: stale})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status %d", rec.Code)
	}
	if got := location(t, rec).Query().Get("err"); got != pkText("auth.error.recent_login") {
		t.Errorf("err %q", got)
	}
	if _, ok := h.passkeyName(id); !ok {
		t.Error("passkey deleted on a stale session")
	}
	if h.auditCount("passkey_removed") != 0 {
		t.Error("passkey_removed audit on a stale session")
	}
}

func TestPasskeyDeleteForeign(t *testing.T) {
	h := newPkHarness(t)
	bobs := h.insertPasskey(h.bob, "bob-cred", "Bobs")
	rec := h.post(pkRequest{path: "/account/passkeys/" + itoa(bobs) + "/delete", form: url.Values{}, session: h.aliceS})
	if rec.Code != http.StatusSeeOther {
		t.Fatalf("status %d", rec.Code)
	}
	if got := location(t, rec).Query().Get("err"); got != pkText("flash.passkeys.not_found") {
		t.Errorf("msg %q", got)
	}
	if _, ok := h.passkeyName(bobs); !ok {
		t.Error("bob's passkey was deleted by alice")
	}
}

func TestPasskeyManageSignedOut(t *testing.T) {
	h := newPkHarness(t)
	id := h.insertPasskey(h.alice, "own-cred", "Mine")
	for _, path := range []string{
		"/account/passkeys/" + itoa(id) + "/rename",
		"/account/passkeys/" + itoa(id) + "/delete",
	} {
		rec := h.post(pkRequest{path: path, form: url.Values{"name": {"x"}}})
		if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != "/login" {
			t.Errorf("%s: status %d Location %q, want 303 /login", path, rec.Code, rec.Header().Get("Location"))
		}
	}
	if name, ok := h.passkeyName(id); !ok || name != "Mine" {
		t.Errorf("passkey changed while signed out: %q %v", name, ok)
	}
}
